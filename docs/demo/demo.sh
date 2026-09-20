#!/usr/bin/env bash
# 演示的内容脚本：README 里那张 GIF 就是把这个脚本录下来得到的。
#
#   brew install asciinema agg
#   bash docs/demo/setup.sh                 # 造样例库（默认 /tmp/holdings-demo）
#   HOLDINGS_BIN=.venv/bin/holdings \
#     asciinema rec --overwrite -c "bash docs/demo/demo.sh" docs/demo/holdings.cast
#   agg --cols 110 --rows 30 --font-size 18 --speed 1.2 \
#     docs/demo/holdings.cast docs/demo/holdings.gif
#
# 为什么不用 vhs：它靠 headless Chrome 渲染终端，本机 Chrome 起不来
# （`--headless --dump-dom about:blank` 挂死），连 vhs 自带的示例 tape 都出不了文件。
# asciinema + agg 不依赖浏览器。
#
# 录制时终端是 80 列的 pty，会让 `list` 退化成简表（B-07 的窄终端分档），
# 所以这里先 stty 撑到 110 列；转 GIF 时 agg 的 --cols 必须跟着改成 110，
# 否则边框字符会错位。
set -euo pipefail

DEMO_DIR="${1:-/tmp/holdings-demo}"

# 演示里出现的命令要就是 `holdings …`——GIF 上显示一串绝对路径很难看。
# HOLDINGS_BIN 给的是可执行文件的路径时，把它的目录放进 PATH，其余照旧。
HOLDINGS_BIN="${HOLDINGS_BIN:-holdings}"
case "$HOLDINGS_BIN" in
  */*) export PATH="$(cd "$(dirname "$HOLDINGS_BIN")" && pwd):$PATH" ;;
esac

cd "$DEMO_DIR"
stty cols 110 rows 30 2>/dev/null || true
printf '\033[2J\033[H' # 清屏，让 GIF 从干净的一屏开始

# 逐字敲出来。用多字节安全的切片（需要 UTF-8 locale），
# 否则命令里的中文会被按字节切开、显示成乱码。
case "${LC_ALL:-${LANG:-}}" in
  *UTF-8* | *utf8*) ;;
  *) export LC_ALL=en_US.UTF-8 ;;
esac

type_line() {
  printf '\033[1;32m$\033[0m '
  local i
  for ((i = 0; i < ${#1}; i++)); do
    printf '%s' "${1:i:1}"
    sleep 0.012
  done
  printf '\n'
  sleep 0.4
}

step() {
  type_line "$1"
  eval "$1"
  sleep "${2:-1.6}"
}

# 只读的日常视图：持仓 → 报表。
step "holdings list" 2.8
step "holdings report --verbose" 4.5

# 写一笔，再回到 list，让「账本变了」这件事在同一个画面里看得到。
step "holdings add --symbol 600036 --market A股 --type BUY --qty 100 --price 42.00 --fee 5.00 --notes 补仓" 2.0
step "holdings list" 2.8

step "holdings snapshots" 3.2

# 命中缓存、瞬间返回。真实拉取要两分钟且会失败，不适合录进来（详见 setup.sh）。
step "holdings sync" 1.8
step "holdings chart --output networth.html" 2.2
