# holdings

**中文** | [English](README.en.md)

[![CI](https://github.com/Chenghao999/holdings/actions/workflows/ci.yml/badge.svg)](https://github.com/Chenghao999/holdings/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![Stars](https://img.shields.io/github/stars/Chenghao999/holdings?label=stars)](https://github.com/Chenghao999/holdings/stargazers)
[![最后提交](https://img.shields.io/github/last-commit/Chenghao999/holdings?label=%E6%9C%80%E5%90%8E%E6%8F%90%E4%BA%A4)](https://github.com/Chenghao999/holdings/commits/main)

> **本地优先的持仓记账工具。** 把支付宝、券商 APP 里散落的资产汇成一本账，并回答
> 「我跑赢沪深 300 了吗」。命令行、终端仪表盘、网页只读看板三种界面共用同一套服务层，
> 数据全部落在一个 SQLite 文件里。

![holdings 演示](docs/demo/holdings.gif)

## 为什么不是又一个记账 APP

- **数据只在你机器上。** 全量存于一个 SQLite 文件，没有账号、没有云同步；项目里没有
  一行上传或埋点代码，备份就是拷走那个文件。
- **分散的账合成一本。** A 股 / 美股 / 黄金在同一张表里比盈亏，成本口径统一：移动加权
  平均，买入费用摊入成本，卖出保持成本价；现金分红摊薄成本，送转摊薄成本价。
- **回答的是「跑赢了吗」，不是「今天涨了多少」。**
  `holdings benchmark --against 沪深300` 先按快照上记的净入金剔除出入金（时间加权），
  再与指数比同期收益——不剔除的话，一笔入金会被算成跑赢。
- **对账单调得动。** 编码自动探测（UTF-8 / GBK / UTF-16），不用先转码；重复行按券商
  流水号判重，同一份导两遍账不会翻倍；**认得出但不能入账的行**（配股、银证转账、
  利息）逐行给出原因，不静默跳过。
- **给开发者做的。** `pip` 装、纯命令行、CSV / JSON 进出、统一退出码便于脚本判断；
  765 条用例，行覆盖率门槛 95% 卡在 CI 里。

## 快速开始

### 1. 安装

包还没传上 PyPI（[BACKLOG B-35](docs/BACKLOG.md)，卡在账号上），现在从源码装：

```bash
pip install 'holdings-cli[data] @ git+https://github.com/Chenghao999/holdings.git'
```

`[data]` 是行情同步那两组依赖（akshare / yfinance），装上才能 `holdings sync` 拉价。
只想记账、不联网取价的话去掉 `[data]` 就够；另有 `[chart]`（净值曲线）/ `[web]`
（网页看板）/ `[tui]`（终端仪表盘）三组按需加，可叠加：

```bash
pip install 'holdings-cli[data,web] @ git+https://github.com/Chenghao999/holdings.git'
```

> 上传 PyPI 之后这里会换成 `pip install 'holdings-cli[data]'`。

### 2. 上手

```bash
# 初始化项目（在当前位置创建数据库与 config.yaml）
holdings init

# 添加一笔交易（含手续费）
holdings add --symbol 600519 --market A股 --type BUY --qty 100 --price 1680.5 --fee 5.0

# 同步最新价格
holdings sync --market 全部

# 查看当前持仓（按盈亏率降序）
holdings list --sort 盈亏率

# 记录一份资产快照（记满两条之后就能 holdings benchmark --against 沪深300）
holdings snapshot --total 158000 --equity 120000 --cash 38000

# 备份账本（导出的标准 CSV 能被 holdings import 读回来）
holdings export --out ledger.csv

# 打开网页看板（只读，需要 pip install 'holdings-cli[web]'）
holdings web
```

还没 `sync` 时，盈亏列显示 `—` 而不是 `-100%`——「没有行情」和「血亏」在表里得能区分开。

命令出错时统一以 `错误（N）：…` 的格式输出到 stderr，并按错误类型返回退出码
（`1` 网络 / 数据源、`2` 数据不存在、`3` 配置错误、`4` 数据库错误、`5` 参数或数据非法、
`6` 缺少依赖），便于脚本判断。完整含义见[错误码规范](docs/ERROR_HANDLING.md)。

完整安装与使用步骤见 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)。

## 演示说明

上面的 GIF 是用 [`docs/demo/demo.sh`](docs/demo/demo.sh) 录的，样例库由
[`docs/demo/setup.sh`](docs/demo/setup.sh) 生成。**其中的行情是预置的样例数字**
（等价于「已经 `sync` 过」的状态），不是真实拉取——真实 `sync` 走公网数据源、
以分钟计、会因限流失败，录进演示只能是两分钟的报错刷屏。复现方式见
[`docs/demo/`](docs/demo/)。

## 核心特性

- 多市场持仓追踪：A 股 / 美股 / 黄金。
- 移动加权平均成本法；手续费与托管费可逐笔记录并单独汇总。
- 本地 SQLite 存储，单文件便携。
- 价格自动同步：A 股优先 akshare、失败降级 yfinance，美股 / 国际黄金走 yfinance，
  带 5 分钟缓存防重复请求；单标的失败不影响其余标的，且输出里带**底层的真因**
  （是没装包、网络不通，还是代码写错），不用猜。
- 持仓盈亏报表、净值快照、交互式净值曲线。
- 对账单导入：`--broker` 指定格式或按表头自动识别，逐行报告认不出的行。
- 基准对比：组合的时间加权收益 vs 指数同期收益。
- 导出：账本 / 持仓表 / 快照 → CSV 或 JSON。
- 三种界面共用同一套服务层：CLI（`holdings …`）、终端仪表盘（`holdings tui`）、
  网页只读看板（`holdings web`），各自按需安装。
- 分层架构由 CI 里的守卫用例盯着（`cli` 不许越过 `services` 直接碰存储、界面层不许
  含 SQL 与网络请求），不是文档里的承诺。

## 项目文档

- [架构与模块隔离规范](docs/ARCHITECTURE.md)
- [项目愿景与范围](docs/VISION.md)
- [用户故事与用例](docs/USER_STORIES.md)
- [功能清单](docs/FEATURES.md)
- [数据库设计说明](docs/SCHEMA.md)
- [错误码与异常处理规范](docs/ERROR_HANDLING.md)
- [配置项字典](docs/CONFIG_SPEC.md)
- [开发者贡献指南](CONTRIBUTING.md)
- [代码风格与 Git 提交规范](docs/CODING_STANDARDS.md)
- [测试策略](docs/TESTING_STRATEGY.md)
- [用户手册（CLI 命令大全）](docs/USER_GUIDE.md)
- [常见问题（FAQ）](docs/FAQ.md)
- [详细开发路线图](docs/ROADMAP.md)
- [待办清单](docs/BACKLOG.md)
- [变更日志](CHANGELOG.md)

## 开源协议

MIT，见 [LICENSE](LICENSE)。
