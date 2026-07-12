import curses
import locale
import sys
import os
import unicodedata

# 全局直排符号映射字典
VERTICAL_MAP = {
    '（': '︵', '）': '︶', '(': '︵', ')': '︶',
    '《': '︽', '》': '︾', '〈': '︿', '〉': '﹀',
    '【': '︻', '】': '︼', '[': '︻', ']': '︼',
    '“': '﹁', '”': '﹂', '‘': '﹃', '’': '﹄',
    '「': '﹁', '」': '﹂', '『': '﹃', '』': '﹄',
    '—': '︱', '_': '︳', '…': '︙'
}
for i in range(10): VERTICAL_MAP[str(i)] = chr(ord('０') + i)
for i in range(26):
    VERTICAL_MAP[chr(ord('a') + i)] = chr(ord('ａ') + i)
    VERTICAL_MAP[chr(ord('A') + i)] = chr(ord('Ａ') + i)


class Paragraph:
    def __init__(self, chars):
        self.chars = chars
        self.is_dirty = True     # 预先打好的脏标记
        self.cached_grid = []    # 二维网格
        self.cached_l2v = {}     # 局部 l2v
        self.cached_v2l = {}     # 局部 v2l
        self.last_max_h = 0      # 视窗高度缓存

def update_paragraph_layout(para, max_h):
    """计算并缓存单个段落排版 ，仅在 dirty 或高度改变时重算"""
    if not para.is_dirty and para.last_max_h == max_h:
        return

    grid, l2v, v2l = [], {}, {}
    if max_h <= 0:
        para.cached_grid, para.cached_l2v, para.cached_v2l = grid, l2v, v2l
        para.is_dirty = False
        return

    FORBIDDEN_START = {
        '，', '。', '！', '？', '：', '；', '”', '’', '）', '》', '】', '…', '、',
        ',', '.', '!', '?', ':', ';', '"', "'", ')', '>', ']'
    }
    FORBIDDEN_END = {
        '（', '《', '〈', '【', '“', '‘',
        '(', '<', '[', '{'
    }

    stream = [(char, c_idx) for c_idx, char in enumerate(para.chars)]
    stream.append(('\n', len(para.chars)))

    new_grid, new_col = [], []
    for i, (char, c_idx) in enumerate(stream):
        new_col.append((char, c_idx))
        real_chars = sum(1 for x in new_col if x[0] != '\n')

        if char == '\n':
            new_grid.append(new_col)
            new_col = []
        elif real_chars >= max_h:
            next_tuple = stream[i + 1] if i + 1 < len(stream) else None
            next_char = next_tuple[0] if next_tuple else ''

            # 默认截断点在当前列的最末尾
            split_idx = len(new_col)

            if next_char in FORBIDDEN_START:
                split_idx -= 1

            # 核心回溯检查
            # 上半截的结尾是 FORBIDDEN_END
            # 下半截的开头是 FORBIDDEN_START
            while split_idx > 0:
                end_char = new_col[split_idx - 1][0]
                start_char = new_col[split_idx][0] if split_idx < len(new_col) else next_char

                if end_char in FORBIDDEN_END or start_char in FORBIDDEN_START:
                    split_idx -= 1
                else:
                    break

            if split_idx <= 0:
                split_idx = max(1, len(new_col) - 1)

            new_grid.append(new_col[:split_idx])
            new_col = new_col[split_idx:]

    if new_col: new_grid.append(new_col)
    if not new_grid: new_grid = [[('\n', 0)]]

    for col_idx, col in enumerate(new_grid):
        final_col = []
        for row_idx, (char, c_idx) in enumerate(col):
            final_col.append(char)
            l2v[c_idx] = (col_idx, row_idx)
            v2l[(col_idx, row_idx)] = c_idx
        grid.append(final_col)

    para.cached_grid = grid
    para.cached_l2v = l2v
    para.cached_v2l = v2l
    para.last_max_h = max_h
    para.is_dirty = False

def build_global_layout(document, max_h):
    """组装全局网格与坐标映射"""
    global_grid = []
    global_l2v = {}
    global_v2l = {}
    if max_h <= 0: return global_grid, global_l2v, global_v2l

    current_col_offset = 0

    for p_idx, para in enumerate(document):
        update_paragraph_layout(para, max_h)

        global_grid.extend(para.cached_grid)

        # 注入全局列偏移
        for c_idx, (l_col, l_row) in para.cached_l2v.items():
            real_col = current_col_offset + l_col
            global_l2v[(p_idx, c_idx)] = (real_col, l_row)

        for (l_col, l_row), c_idx in para.cached_v2l.items():
            real_col = current_col_offset + l_col
            global_v2l[(real_col, l_row)] = (p_idx, c_idx)

        current_col_offset += len(para.cached_grid)

    return global_grid, global_l2v, global_v2l


# 文件与状态管理
def load_document(filename):
    document = []
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for para in f.read().split('\n'):
                document.append(Paragraph(list(para.replace('\r', ''))))
    return document if document else [Paragraph([])]

def save_document(document, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join("".join(para.chars) for para in document))

def save_undo_snapshot(document, cur_col, cur_row, undo_stack):
    if len(undo_stack) > 100: undo_stack.pop(0)
    doc_copy = [Paragraph(para.chars[:]) for para in document]
    undo_stack.append((doc_copy, cur_col, cur_row))


# 渲染辅助
def get_active_bounds(grid, cur_c, cur_r):
    if not grid: return (0, 0), (0, 0)
    para_boundaries, start_col = [], 0

    for c, col in enumerate(grid):
        if col and col[-1] == '\n':
            para_boundaries.append((start_col, c))
            start_col = c + 1
    if start_col < len(grid):
        para_boundaries.append((start_col, len(grid) - 1))
    if not para_boundaries:
        return (0, 0), (len(grid) - 1, len(grid[-1]) - 1 if grid[-1] else 0)

    c = max(0, min(cur_c, len(grid) - 1))
    current_p_idx = 0
    for i, (start, end) in enumerate(para_boundaries):
        if start <= c <= end:
            current_p_idx = i
            break

    chunk_start_idx = max(0, min((current_p_idx // 3) * 3, len(para_boundaries) - 1))
    chunk_end_idx = min(chunk_start_idx + 2, len(para_boundaries) - 1)

    start_c, start_r = para_boundaries[chunk_start_idx][0], 0
    end_c = max(0, min(para_boundaries[chunk_end_idx][1], len(grid) - 1))
    end_r = len(grid[end_c]) - 1 if grid[end_c] else 0

    return (start_c, start_r), (end_c, end_r)

def is_active_char(col_idx, row_idx, start_c, start_r, end_c, end_r):
    if col_idx < start_c or col_idx > end_c: return False
    if col_idx == start_c and row_idx < start_r: return False
    if col_idx == end_c and row_idx > end_r: return False
    return True

def render_status_bar(stdscr, max_y, max_x, text, attr):
    display_str, current_w = "", 0
    for char in text:
        cw = 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
        if current_w + cw > max_x - 1: break
        display_str += char
        current_w += cw
    display_str += " " * max(0, max_x - 1 - current_w)
    try:
        stdscr.addstr(max_y - 1, 0, display_str, attr)
    except curses.error:
        pass


def main(stdscr):
    locale.setlocale(locale.LC_ALL, '')
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, -1, -1)
    curses.init_pair(2, 237 if curses.COLORS >= 256 else curses.COLOR_BLACK, -1)
    stdscr.keypad(True)
    stdscr.nodelay(False)
    stdscr.scrollok(False)

    filename = sys.argv[1] if len(sys.argv) > 1 else "untitled.txt"
    document = load_document(filename)

    cur_col, cur_row, desired_row, camera_col = 0, 0, 0, 0
    current_mode, last_mode = "NORMAL", None
    status_msg, status_timer = "", 0
    undo_stack, g_pressed = [], False
    l2v, v2l = {}, {}

    while True:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        usable_height = max_y - 1
        col_width = 3

        if usable_height <= 0 or max_x <= 4:
            stdscr.refresh()
            continue

        text_grid, l2v, v2l = build_global_layout(document, usable_height)

        if (cur_col, cur_row) not in v2l:
            if v2l:
                cur_col = min(cur_col, len(text_grid) - 1)
                cur_row = min(cur_row, len(text_grid[cur_col]) - 1 if text_grid[cur_col] else 0)
            else:
                cur_col, cur_row = 0, 0

        max_visible_cols = (max_x - 4) // col_width
        if cur_col < camera_col:
            camera_col = cur_col
        elif cur_col > camera_col + max_visible_cols:
            camera_col = cur_col - max_visible_cols
        camera_col = max(0, min(camera_col, len(text_grid) - 1))

        if status_msg and status_timer > 0:
            info_str = f" {status_msg} "
            status_timer -= 1
        else:
            mode_str = "[NORMAL]" if current_mode == "NORMAL" else "[INSERT]"
            info_str = f" {mode_str} {filename} | 视窗({cur_col},{cur_row}) | [u]撤销 [F2]保存 "

        render_status_bar(stdscr, max_y, max_x, info_str,
                          curses.A_REVERSE | curses.A_BOLD if current_mode == "INSERT" else curses.A_REVERSE)

        bounds = get_active_bounds(text_grid, cur_col, cur_row)
        for col_idx, column in enumerate(text_grid):
            if col_idx < camera_col: continue
            x_pos = max_x - 4 - ((col_idx - camera_col) * col_width)
            if x_pos < 0: break

            row_idx_render = 0
            for char in column:
                if char == '\n': continue
                if row_idx_render >= usable_height: break

                is_active = is_active_char(col_idx, row_idx_render, *bounds[0], *bounds[1])
                attr = curses.A_BOLD | curses.color_pair(1) if is_active else curses.color_pair(2)
                try:
                    stdscr.addstr(row_idx_render, x_pos, VERTICAL_MAP.get(char, char), attr)
                except curses.error:
                    pass
                row_idx_render += 1

        cursor_x = max_x - 4 - ((cur_col - camera_col) * col_width)
        if 0 <= cursor_x < max_x and 0 <= cur_row < usable_height:
            try:
                stdscr.move(cur_row, cursor_x)
            except curses.error:
                pass

        if current_mode != last_mode:
            try:
                curses.curs_set(2 if current_mode == "NORMAL" else 1)
            except:
                pass
            last_mode = current_mode

        stdscr.refresh()
        try:
            char = stdscr.get_wch()
        except curses.error:
            continue

        if isinstance(char, int) and char == curses.KEY_F2:
            save_document(document, filename)
            status_msg, status_timer = f"[成功保存至 {filename}]", 3
            continue

        def move_cursor(d_col, d_row, is_absolute=False):
            nonlocal cur_col, cur_row, desired_row
            if is_absolute:
                cur_col, cur_row = d_col, d_row
            else:
                if d_row > 0:
                    if cur_row < len(text_grid[cur_col]) - (1 if text_grid[cur_col] and text_grid[cur_col][-1] == '\n' else 0):
                        cur_row += 1
                    elif cur_col < len(text_grid) - 1:
                        cur_col += 1
                        cur_row = 0
                elif d_row < 0:
                    if cur_row > 0:
                        cur_row -= 1
                    elif cur_col > 0:
                        cur_col -= 1
                        cur_row = len(text_grid[cur_col]) - 1
                if d_col > 0:
                    if cur_col < len(text_grid) - 1: cur_col += 1; cur_row = desired_row
                elif d_col < 0:
                    if cur_col > 0: cur_col -= 1; cur_row = desired_row
            desired_row = cur_row

        if current_mode == "NORMAL":
            reset_g_flag = char != 'g'
            if isinstance(char, str):
                if char in ('i', 'a', 'I', 'A'):
                    save_undo_snapshot(document, cur_col, cur_row, undo_stack)
                    current_mode = "INSERT"
                elif ord(char) == 27:
                    save_document(document, filename)
                    break
                elif char == 'j': move_cursor(0, 1)
                elif char == 'k': move_cursor(0, -1)
                elif char == 'h': move_cursor(1, 0)
                elif char == 'l': move_cursor(-1, 0)
                elif char == 'u':
                    if undo_stack:
                        doc_snap, cur_col, cur_row = undo_stack.pop()
                        document = [Paragraph(para.chars[:]) for para in doc_snap]
                        desired_row, status_msg, status_timer = cur_row, "[已还原上一步修改]", 2
                elif char == 'g':
                    if g_pressed: move_cursor(0, 0, True); g_pressed = False
                    else: g_pressed = True
                elif char == 'G':
                    target_c = len(text_grid) - 1
                    target_r = max(0, len(text_grid[target_c]) - (1 if text_grid[target_c] and text_grid[target_c][-1] == '\n' else 0))
                    move_cursor(target_c, target_r, True)
            elif isinstance(char, int):
                if char == curses.KEY_DOWN: move_cursor(0, 1)
                elif char == curses.KEY_UP: move_cursor(0, -1)
                elif char == curses.KEY_LEFT: move_cursor(1, 0)
                elif char == curses.KEY_RIGHT: move_cursor(-1, 0)
                elif char == curses.KEY_NPAGE: move_cursor(min(len(text_grid) - 1, cur_col + max_visible_cols), cur_row, True)
                elif char == curses.KEY_PPAGE: move_cursor(max(0, cur_col - max_visible_cols), cur_row, True)
            if reset_g_flag: g_pressed = False

        elif current_mode == "INSERT":
            if isinstance(char, int):
                if char in (curses.KEY_BACKSPACE, 127): char = '\b'
                elif char == curses.KEY_DOWN: move_cursor(0, 1)
                elif char == curses.KEY_UP: move_cursor(0, -1)
                elif char == curses.KEY_LEFT: move_cursor(1, 0)
                elif char == curses.KEY_RIGHT: move_cursor(-1, 0)

            if isinstance(char, str):
                if ord(char) == 27:
                    current_mode = "NORMAL"
                elif char in ('\n', '\r', '\b', '\x7f') or ord(char) >= 32:
                    logical_pos = v2l.get((cur_col, cur_row))
                    if logical_pos:
                        p_idx, c_idx = logical_pos
                        save_undo_snapshot(document, cur_col, cur_row, undo_stack)

                        if char in ('\n', '\r'):
                            # 拆分段落
                            new_para_chars = document[p_idx].chars[c_idx:]
                            document[p_idx].chars = document[p_idx].chars[:c_idx]
                            document[p_idx].is_dirty = True
                            document.insert(p_idx + 1, Paragraph(new_para_chars))
                            expected_logical = (p_idx + 1, 0)
                        elif char in ('\b', '\x7f'):
                            if c_idx > 0:
                                del document[p_idx].chars[c_idx - 1]
                                document[p_idx].is_dirty = True
                                expected_logical = (p_idx, c_idx - 1)
                            elif p_idx > 0:
                                # 合并段落
                                prev_len = len(document[p_idx - 1].chars)
                                document[p_idx - 1].chars.extend(document[p_idx].chars)
                                document[p_idx - 1].is_dirty = True
                                del document[p_idx]
                                expected_logical = (p_idx - 1, prev_len)
                            else:
                                expected_logical = (0, 0)
                        else:
                            # 插入字符
                            document[p_idx].chars.insert(c_idx, char)
                            document[p_idx].is_dirty = True
                            expected_logical = (p_idx, c_idx + 1)

                        text_grid, l2v, v2l = build_global_layout(document, usable_height)
                        cur_col, cur_row = l2v.get(expected_logical, (cur_col, cur_row))
                        desired_row = cur_row

if __name__ == "__main__":
    os.environ.setdefault('TERM', 'xterm-256color')
    curses.wrapper(main)