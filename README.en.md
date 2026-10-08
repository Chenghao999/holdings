# holdings

**English** | [中文](README.md)

[![CI](https://github.com/Chenghao999/holdings/actions/workflows/ci.yml/badge.svg)](https://github.com/Chenghao999/holdings/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)

> **A local-first portfolio tracker for the command line.** It consolidates holdings
> scattered across Alipay and brokerage apps into a single ledger, and answers
> *"am I beating the CSI 300?"*. A CLI, a terminal dashboard and a read-only web
> board share one service layer, and everything lives in one SQLite file.

![holdings demo](docs/demo/holdings.gif)

> The tool targets **China's markets** (A-shares, ETFs, domestic gold; quotes via
> akshare / yfinance), so its output and documentation are in Chinese — the demo
> above included. This file is the English entry point.

## Why not just another budgeting app

- **Your data stays on your machine.** Everything lives in a single SQLite file —
  no account, no cloud sync. There is not one line of upload or telemetry code in
  the project; backing up means copying that file.
- **One ledger for scattered accounts.** A-shares, US stocks and gold are compared
  in one table under a single cost convention: moving weighted average, buy fees
  amortised into cost, sell price leaves cost untouched; cash dividends dilute cost,
  bonus issues dilute cost per share.
- **It answers "am I winning?", not "what did I gain today".**
  `holdings benchmark --against 沪深300` strips deposits and withdrawals first
  (time-weighted, using the net inflow recorded on each snapshot) and only then
  compares against the index — otherwise a single deposit reads as outperformance.
- **Broker statements are handled properly.** Auto-detected encoding
  (UTF-8 / GBK / UTF-16), duplicate rows deduplicated by broker reference number
  (importing the same file twice does not double the ledger), and rows it can
  recognise but not post — rights issues, bank transfers, interest — are reported
  line by line with a reason instead of being silently skipped.
- **Built for developers.** Install with `pip`, drive it from a shell, move data
  in and out as CSV / JSON, and branch on a documented set of exit codes.
  765 test cases, with a 95% line-coverage gate enforced in CI.

## Quick start

### 1. Install

The package is not on PyPI yet (see [BACKLOG B-35](docs/BACKLOG.md) — it is waiting
on an account), so install from source:

```bash
pip install 'holdings-cli[data] @ git+https://github.com/Chenghao999/holdings.git'
```

`[data]` pulls the two quote-sync dependencies (akshare / yfinance) needed by
`holdings sync`. Drop it if you only want to keep the books offline. Three more
extras exist and can be combined: `[chart]` (net-worth curve), `[web]` (web board),
`[tui]` (terminal dashboard):

```bash
pip install 'holdings-cli[data,web] @ git+https://github.com/Chenghao999/holdings.git'
```

> Once it is on PyPI this becomes `pip install 'holdings-cli[data]'`.

### 2. Use it

```bash
# Create the database and config.yaml in the current directory
holdings init

# Record a trade (with commission)
holdings add --symbol 600519 --market A股 --type BUY --qty 100 --price 1680.5 --fee 5.0

# Fetch the latest prices
holdings sync --market 全部

# Show current holdings, sorted by return
holdings list --sort 盈亏率

# Record a snapshot (two or more unlock holdings benchmark --against 沪深300)
holdings snapshot --total 158000 --equity 120000 --cash 38000

# Back the ledger up as CSV that holdings import can read back
holdings export --out ledger.csv

# Open the read-only web board (needs pip install 'holdings-cli[web]')
holdings web
```

Before the first `sync`, the P&L column shows `—` rather than `-100%`: "no quote
yet" and "down 100%" have to be distinguishable in the table.

Errors are printed to stderr as `错误（N）：…` with an exit code by category
(`1` network / data source, `2` record not found, `3` config, `4` database,
`5` invalid argument or data, `6` missing dependency), so scripts can branch on
them. See [ERROR_HANDLING.md](docs/ERROR_HANDLING.md) for the full contract.

Full install and usage instructions: [docs/USER_GUIDE.md](docs/USER_GUIDE.md) (Chinese).

## About the demo

The GIF above was recorded with [`docs/demo/demo.sh`](docs/demo/demo.sh), against a
sample database built by [`docs/demo/setup.sh`](docs/demo/setup.sh). **The quotes in
it are preset sample numbers** (equivalent to "already synced") — a real `sync`
goes out to public data sources, takes minutes and fails on rate limits, which would
only record two minutes of error output.

## Features

- Multi-market positions: A-shares, US stocks, gold.
- Moving weighted average cost; commissions and custody fees recorded per trade and
  summarised separately.
- Local SQLite storage — a single portable file.
- Automatic quote sync: akshare with yfinance as fallback for A-shares, yfinance for
  US stocks and international gold, with a 5-minute cache; one failing symbol does not
  affect the others, and failures report the **underlying cause** (missing package,
  network, or a bug) instead of a canned "data source unavailable".
- Holdings and P&L reports, net-worth snapshots, interactive net-worth curve.
- Broker statement import, reporting every row it cannot post.
- Benchmark comparison: time-weighted portfolio return vs the index over the same period.
- Export: ledger / holdings / snapshots → CSV or JSON.
- Three front ends over one service layer: CLI, terminal dashboard (`holdings tui`),
  read-only web board (`holdings web`), installed as needed.
- The layered architecture is enforced by guard tests in CI (the CLI may not reach
  past the service layer into storage; UI layers may hold no SQL and no network
  calls) — it is not a promise in a document.

## Documentation

Chinese-first; the entry points most useful to an English reader are:

- [Architecture](docs/ARCHITECTURE.md)
- [Feature list](docs/FEATURES.md)
- [Database schema](docs/SCHEMA.md)
- [Error codes](docs/ERROR_HANDLING.md)
- [Configuration reference](docs/CONFIG_SPEC.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
