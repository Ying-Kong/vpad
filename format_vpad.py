import sys
import json
import zipfile
import hashlib
import time
import tempfile
import shutil
from pathlib import Path


def _calc_state_hash(workspace):
    """必须和 core_vpad.py 里的哈希算法保持绝对一致"""
    h = hashlib.sha256()
    # 严格按照 work.txt -> config.json -> state.json 的顺序联合哈希
    for filename in ["work.txt", "config.json", "state.json"]:
        f_path = workspace / filename
        if f_path.exists():
            with open(f_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        else:
            h.update(b"MISSING")
    return h.hexdigest()


def create_vpad_from_txt(txt_path, vpad_out_path=None):
    source_file = Path(txt_path).resolve()

    if not source_file.exists():
        print(f"找不到源文件: {source_file}")
        sys.exit(1)

    if vpad_out_path is None:
        # 默认在同级目录生成同名的 .vpad
        vpad_out_path = source_file.with_suffix(".vpad")
    else:
        vpad_out_path = Path(vpad_out_path).resolve()

    workspace = Path(tempfile.mkdtemp(prefix="vpad_format_"))
    try:
        # 读取 TXT 内容
        content = source_file.read_text(encoding="utf-8")

        # origin.txt 源文件
        f_origin = workspace / "origin.txt"
        f_origin.write_text(content, encoding="utf-8")

        # work.txt 工作副本
        f_bak = workspace / "work.txt"
        f_bak.write_text(content, encoding="utf-8")

        # 初始 config
        # 这里可以设定你的默认排版习惯，比如缩进、行距等
        f_config = workspace / "config.json"
        default_config = {
            "indent": 2,
            "auto_space_after_enter": True
        }
        f_config.write_text(json.dumps(default_config), encoding="utf-8")

        # 初始光标状态 (0, 0)
        f_json = workspace / "state.json"
        f_json.write_text(json.dumps({"p_idx": 0, "c_idx": 0}), encoding="utf-8")

        f_hash = workspace / "state_hash"
        new_hash = _calc_state_hash(workspace)
        current_time = str(int(time.time()))
        f_hash.write_text(f"{current_time}|{new_hash}", encoding="utf-8")

        with zipfile.ZipFile(vpad_out_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            for file_path in [f_origin, f_config, f_bak, f_json, f_hash]:
                zipf.write(file_path, arcname=file_path.name)

        print(f"Successfully created vpad file: {vpad_out_path}")

    except Exception as e:
        print(f"格式化失败 {e}")
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)

def main():
    if len(sys.argv) < 2:
        print("用法：vpad-pack <文本文件.txt>")
        sys.exit(1)
    input_txt = sys.argv[1]
    create_vpad_from_txt(input_txt)


if __name__ == "__main__":
    main()

