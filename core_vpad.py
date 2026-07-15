import os
import json
import zipfile
import hashlib
import shutil
import tempfile
import time
from pathlib import Path

__all__ = ['VpadSandbox']
class VpadSandbox:
    def __init__(self, vpad_file_path):
        self.vpad_file = Path(vpad_file_path).resolve()
        self.workspace = Path(tempfile.mkdtemp(prefix="vpad_workspace_"))

        # 严格定义的 6 个状态实体
        self.f_origin = self.workspace / "origin.txt"
        self.f_config = self.workspace / "config.json"
        self.f_tmp = self.workspace / "work.tmp"
        self.f_bak = self.workspace / "work.txt"
        self.f_json = self.workspace / "state.json"
        self.f_hash = self.workspace / "state_hash"  # 更名为 state_hash

        self.is_mounted = False
        self.tmp_sync_counter = 0

    def _calc_state_hash(self):
        """逻辑状态哈希：保护工作副本、环境配置和游标坐标"""
        h = hashlib.sha256()
        for f_path in [self.f_bak, self.f_config, self.f_json]:
            if f_path.exists():
                with open(f_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
            else:
                h.update(b"MISSING")
        return h.hexdigest()

    def _update_state_hash(self):
        """统一的 Hash 刷新协议，防止状态死锁"""
        new_hash = self._calc_state_hash()
        current_time = str(int(time.time()))
        self.f_hash.write_text(f"{current_time}|{new_hash}", encoding="utf-8")

    def _safe_extract(self, zip_ref):
        """防止 ZIP 路径穿越攻击"""
        for member in zip_ref.namelist():
            # 强化防御：排除任何可能的目录逃逸
            if '..' not in member and not member.startswith('/') and not member.startswith('\\'):
                zip_ref.extract(member, self.workspace)

    def _repair_from_origin(self):
        """基线修复协议"""
        if self.f_origin.exists():
            shutil.copy(self.f_origin, self.f_bak)
            self.f_json.write_text(json.dumps({"p_idx": 0, "c_idx": 0, "repaired": True}), encoding="utf-8")
            return True
        return False

    def mount(self):
        if not self.vpad_file.exists():
            raise FileNotFoundError(f"找不到文件: {self.vpad_file}")

        with zipfile.ZipFile(self.vpad_file, 'r') as zip_ref:
            self._safe_extract(zip_ref)

        hash_failed = False
        if self.f_bak.exists() and self.f_hash.exists():
            current_hash = self._calc_state_hash()
            hash_content = self.f_hash.read_text("utf-8").strip().split('|')
            if len(hash_content) == 2 and current_hash != hash_content[1]:
                hash_failed = True

        if self.f_origin.exists():
            os.chmod(self.f_origin, 0o444)

        repaired = False
        if not self.f_bak.exists() or hash_failed:
            if not self._repair_from_origin():
                raise ValueError("灾难性损坏：bak 校验失败且丢失 origin 基线。")
            repaired = True

        recovered_from_tmp = False
        if not repaired and self.f_tmp.exists() and self.f_tmp.stat().st_size > 0:
            if self.f_tmp.stat().st_mtime > self.f_bak.stat().st_mtime:
                os.replace(self.f_tmp, self.f_bak)
                recovered_from_tmp = True

        json_state = {"p_idx": 0, "c_idx": 0}
        if self.f_json.exists():
            try:
                json_state = json.loads(self.f_json.read_text("utf-8"))
            except:
                pass

        # 记录恢复痕迹
        state_changed = False
        if recovered_from_tmp:
            json_state["recovered_from_tmp"] = True
            state_changed = True
        if repaired:
            json_state["repaired_from_origin"] = True
            state_changed = True

        if state_changed:
            self.f_json.write_text(json.dumps(json_state), encoding="utf-8")
            # 【修复问题1与2】自愈完成后，必须重新盖戳，打破 Hash 死锁循环
            self._update_state_hash()

        self.is_mounted = True

        config_data = {}
        if self.f_config.exists():
            config_data = json.loads(self.f_config.read_text("utf-8"))

        return config_data, json_state

    def sync_to_tmp(self, full_text_list, force=False):
        """运行时快照"""
        self.tmp_sync_counter += 1
        if force or self.tmp_sync_counter >= 20:
            with open(self.f_tmp, "w", encoding="utf-8") as f:
                f.write("\n".join("".join(para.chars) for para in full_text_list))
                f.flush()
                os.fsync(f.fileno())
            self.tmp_sync_counter = 0

    def get_bak_path(self):
        return str(self.f_bak)

    def sync_after_vim(self):
        """
        【修复问题4】Vim 退出同步协议。
        不再接收外部坐标，仅负责更新系统状态戳，接纳新物理文件。
        """
        if not self.is_mounted: return
        # 强制归零逻辑坐标（因为全文结构已不可知）
        self.f_json.write_text(json.dumps({"p_idx": 0, "c_idx": 0}), encoding="utf-8")
        # 刷新全局 Hash
        self._update_state_hash()

    def commit_and_pack(self, full_text_list, current_p_idx, current_c_idx):
        """
        【修复问题5】强制封装。
        不依赖外部 UI 调用，内部自行解决 tmp 到 bak 的绝对同步。
        """
        if not self.is_mounted: return

        # 1. 强制生成最新 tmp
        self.sync_to_tmp(full_text_list, force=True)

        # 2. 原子替换
        if self.f_tmp.exists():
            os.replace(self.f_tmp, self.f_bak)

        # 3. 状态更新与盖戳
        self.f_json.write_text(json.dumps({"p_idx": current_p_idx, "c_idx": current_c_idx}), encoding="utf-8")
        self._update_state_hash()

        # 4. 打包落盘
        temp_vpad = self.vpad_file.with_suffix(".vpad.swp")
        try:
            with zipfile.ZipFile(temp_vpad, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
                for f_path in [self.f_origin, self.f_config, self.f_bak, self.f_json, self.f_hash]:
                    if f_path.exists():
                        zipf.write(f_path, arcname=f_path.name)

            with open(temp_vpad, 'a') as f:
                os.fsync(f.fileno())

            os.replace(temp_vpad, self.vpad_file)
        except Exception as e:
            if temp_vpad.exists(): temp_vpad.unlink()
            raise RuntimeError(f"打包失败: {e}")

    def cleanup(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)