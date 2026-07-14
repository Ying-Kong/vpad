# vpad

## 中文介绍

vpad 是一个专为中日韩（CJK）文本设计的终端交互式竖排阅读环境和轻量级编辑器。

它采用类似 Vim 的键盘交互逻辑，专注于在终端环境中提供符合 CJK 排版习惯的竖排文本阅读与编辑体验。

vpad 并不是为了替代 Vim，而是作为 Vim 的补充：

- vpad 负责 CJK 竖排显示、阅读体验以及轻量修改；
- Vim 负责复杂文本处理，例如正则替换、宏操作、大规模编辑等。

通过结合两者，用户可以在保持终端工作流的同时，获得更适合中文、日文等 CJK 长文本处理的体验。


### 1. CJK 竖排显示
- 支持中文、日文等 CJK 文本的竖排显示；
- 遵循 CJK 文字排版习惯；
- 支持竖排文本阅读；
- 处理部分竖排标点规则。


### 2. Vim 风格交互
- 模仿 Vim 的键盘操作逻辑；
- 支持熟悉的光标移动方式；
- 无需鼠标即可完成阅读和简单编辑。


### 3. 轻量文本编辑
vpad 提供基础编辑能力：
- 文本插入与删除；
- 光标定位；
- 简单文本修改；
- CJK 标点与字符输入修正。

#### :!vim % 允许直接切换入Vim,在 Vim 内，:wq 退出后会回到 vpad
对于复杂文本操作：
- 正则表达式批量处理；
- 宏录制；
- 大规模文本修改；
可以直接交由 Vim 完成。


### 4. 终端界面
- 本地运行；
- 无需网络；
- 低资源占用；
- 无 UI 运行;

## Design Philosophy
vpad 的目标不是成为一个通用文本编辑器，它专注于解决一个特定问题：

> 无论是界面端的笔记软件，还是终端的编辑器，现代文本工具大多围绕字母文字横排设计，vpad 在终端环境中，为 CJK 长文本提供自然的竖排阅读和轻量编辑体验。

## Use Cases
vpad 适用于：

- 中文小说阅读与修改；
- 日文轻小说文本处理；
- 终端环境下的沉浸式阅读；
- 喜爱竖版阅读的 Linux 用户的轻量写作工具。


## Vim Integration

vpad 不试图重新实现 Vim 的高级编辑能力，对于复杂文本处理，可以直接调用 Vim：

- 正则替换；
- 宏操作；
- 批量修改；
- 高级编辑。
vpad + Vim 提供了一种 vpad → CJK 竖排阅读与轻编辑，Vim → 高级文本处理的组合工作流。

# English Introduction

vpad is a terminal-based vertical reading environment and lightweight editor designed specifically for CJK (Chinese, Japanese, and Korean) text.

It provides a Vim-like keyboard interaction model and focuses on delivering a natural vertical writing and reading experience for CJK long-form text in terminal environments.

vpad is not intended to replace Vim. Instead, it works together with Vim:

- vpad focuses on CJK vertical layout, reading experience, and lightweight editing;
- Vim handles advanced text processing such as regular expressions, macros, and large-scale modifications.

By combining both tools, users can maintain a terminal-based workflow while gaining a better environment for CJK text processing.

### 使用图实例
<img width="1260" height="1328" alt="image" src="https://github.com/user-attachments/assets/d06bbf7f-c3af-449c-b8ea-5d6aac9d0efd" />
