#!/usr/bin/env bash
# 生成录制演示用的样例库（docs/demo/demo.tape 会用它）。
#
# 为什么不用真实数据：`holdings sync` 走公网数据源，耗时以分钟计、会因限流
# 或标的停牌而失败，录进 GIF 就是一段两分钟的报错刷屏。所以这里造一份样例库，
# **行情缓存直接预置**（等价于「用户已经 sync 过」的正常状态），录制的就只剩
# 快而确定的那部分命令。
#
# 预置的价格是**编造的样例数字**，只为了让表格里有数；它们不是任何一天的真实行情。
#
# 用法：bash docs/demo/setup.sh [目标目录]   （默认 /tmp/holdings-demo）
set -euo pipefail

DEMO_DIR="${1:-/tmp/holdings-demo}"
HOLDINGS="${HOLDINGS_BIN:-holdings}"

rm -rf "$DEMO_DIR"
mkdir -p "$DEMO_DIR"
cd "$DEMO_DIR"

# 演示库在自己目录下，靠 CWD 的 config.yaml 定位，与用户的 ~/.holdings 无关。
"$HOLDINGS" init

# 一笔完整的账本：买入、加仓、卖出（展示移动加权平均成本）、费用。
"$HOLDINGS" add --symbol 600519 --market A股 --type BUY \
  --qty 100 --price 1680 --date 2026-03-02 --notes "首笔建仓"
"$HOLDINGS" add --symbol 518880 --market 黄金 --type BUY \
  --qty 2000 --price 5.42 --date 2026-03-02
"$HOLDINGS" add --symbol 600036 --market A股 --type BUY \
  --qty 500 --price 38.50 --date 2026-05-11
"$HOLDINGS" add --symbol 600036 --market A股 --type SELL \
  --qty 200 --price 44.20 --fee 8.84 --date 2026-07-08
"$HOLDINGS" add --symbol 600036 --market A股 --type FEE \
  --qty 0 --price 0 --fee 5.00 --date 2026-07-08 --notes "佣金"
# 一个外币标的：演示 B-19 的口径（不计入人民币汇总，如实说明）。
"$HOLDINGS" add --symbol AAPL --market 美股 --type BUY \
  --qty 30 --price 200 --date 2026-04-10

# 标的名称与管理费率（`list` 的名称列取自这里）。
"$HOLDINGS" meta --symbol 600519 --name "贵州茅台" --fee-rate 0.5
"$HOLDINGS" meta --symbol 518880 --name "黄金ETF"
"$HOLDINGS" meta --symbol 600036 --name "招商银行"
"$HOLDINGS" meta --symbol AAPL --name "Apple"

# 快照：净值曲线与绩效（回撤 / 年化）都从这组数来。
"$HOLDINGS" snapshot --total 268000 --equity 168000 --gold 100000 --date 2026-03-02 --note "建仓完成"
"$HOLDINGS" snapshot --total 291500 --equity 191500 --gold 100000 --date 2026-04-01 --note "月度定投第1期"
"$HOLDINGS" snapshot --total 246800 --equity 146800 --gold 100000 --date 2026-05-04 --note "大盘回调"
"$HOLDINGS" snapshot --total 274300 --equity 174300 --gold 100000 --date 2026-06-01 --note "月度定投第2期"
"$HOLDINGS" snapshot --total 283900 --equity 183900 --gold 100000 --date 2026-07-01 --note "月度定投第3期"

# 预置行情缓存。写入时间用 CURRENT_TIMESTAMP（UTC，与 price_cache_dao 的
# 新鲜度判断一致），使 sync 在缓存有效期内跳过网络请求。
python3 - "data/holdings.db" <<'PY'
import sqlite3
import sys

rows = [
    # symbol, price, currency, source
    ("600519", 1257.12, "CNY", "akshare"),
    ("518880", 6.85, "CNY", "akshare"),
    ("600036", 44.20, "CNY", "akshare"),
    ("AAPL", 336.13, "USD", "yfinance"),
]
conn = sqlite3.connect(sys.argv[1])
conn.executemany(
    "INSERT INTO price_cache (symbol, price, currency, update_time, source) "
    "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?) "
    "ON CONFLICT(symbol) DO UPDATE SET price=excluded.price, "
    "currency=excluded.currency, update_time=CURRENT_TIMESTAMP, source=excluded.source",
    rows,
)
conn.commit()
conn.close()
print(f"样例库已生成：{sys.argv[1]}（含 {len(rows)} 条预置行情缓存，为编造的样例数字）")
PY
