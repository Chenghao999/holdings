# 变更日志（CHANGELOG）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/) 格式，并使用 [Semantic Versioning](https://semver.org/) 进行版本管理。

## [Unreleased]

### Fixed

**错误处理链路此前完全不生效**
- `pyproject.toml` 的 console script 指向裸 click group `cli` 而非 `main`，导致
  `docs/ERROR_HANDLING.md` 定义的退出码 1/2/3/4 与 `错误（N）：` 前缀对已安装用户
  全部失效——用户看到的是裸 traceback、退出码恒为 1。现改为 `holdings.cli.main:main`。
  **已安装旧版本的用户需重新 `pip install` 才会生成新的启动脚本。**
- 新增 `holdings/exceptions.py`，`HoldingsError` 作为统一基类；`ConfigError` /
  `DatabaseError` / `DataSourceUnavailableError` / `SymbolNotFoundError` 改为继承它，
  并新增 `TradeValidationError`（退出码 5）。入口按基类统一映射，新增异常无需改入口。
- `config.yaml` 存在 YAML 语法错误时抛的是 PyYAML 的 `ParserError`，绕过退出码 3；
  现转为 `ConfigError`，且提示只保留一行出错位置与原因，不再刷屏。

**账本可能被写入坏数据**
- **卖出数量超过当时持有量**：`calculator` 不校验，数量与总成本会双双变成负数，
  而汇总按「数量 <= 0」跳过该持仓，于是错误悄悄留在总成本里、持仓却看不见。
  现新增 `calculator.check_trade`，并在 `services/trade_service.py` 的写入闸门中
  对**合并历史后的完整序列**做严格重放校验——补录往日交易也能按当时的持仓判定。
- **买入数量非正 / 费用或单价为负**：此前一律接受，`--qty 0 --fee 10` 会产生
  「累计费用里有钱、列表里没有对应持仓」的孤儿费用。现一并拒绝。
- **CSV 导入**：此前每行各自 commit，中途失败会留下半批数据且不报行号；
  现改为整批校验、单事务写入（`transaction_dao.add_many`），任一行非法则一笔不写，
  并指出出错行号。同时补上表头校验（缺列、`--fee-column` 指向不存在的列）。
  此前 `--fee-column` 指向不存在的列会静默按 0 计费。

**其它**
- `add` / `sync` 的 `--market`、`--type` 改用 `click.Choice`，`--date` 改用回调校验，
  非法取值不再抛裸 `ValueError`，统一返回退出码 5。
- `sync` 在全部标的同步失败时返回退出码 1（此前恒为 0，脚本无法据此判断），
  并提示缺失的数据源依赖。
- `storage/db.py` 的 `connect()` 在建表失败时关闭连接，不再泄漏句柄；
  数据库目录创建失败包装为 `DatabaseError`。

### Added
- `holdings/exceptions.py`：统一的异常基类与退出码契约。
- `services/trade_service.py`：交易写入闸门（`add_transaction` / `add_transactions`）。
- `storage/transaction_dao.add_many()`：单事务批量写入，支持整批回滚。
- 测试从 56 个增至 104 个，新增 `test_validation.py`、`test_trade_service.py`、
  `test_import_cmd.py`、`test_config.py`、`test_cli_errors.py`；
  此前零覆盖的 `utils/` 与 `cli/` 错误路径开始有测试，退出码契约被逐条锁住。

### Planned
- **v1.0.0（2027 Q2）**：补齐单元测试覆盖率，稳定 CLI 交互与错误码；录制演示 GIF。
- **v2.0.0（2027 Q4）**：基于 Textual 的 TUI 仪表盘预览版。

## [0.1.0] - 2026-09-15

首个可用版本。CLI 骨架、加权成本算法与数据同步链路已跑通，存储层为纯本地 SQLite。

### Added

**数据模型与存储层**
- `models`：`Transaction` / `Snapshot` DTO 与 `MarketType` / `AssetType` / `TradeType` 枚举。
- `storage/db.py`：SQLite 连接管理、建表与索引迁移（`transactions` / `snapshots` / `asset_meta` / `price_cache`）。
- `storage` DAO：`transaction_dao`、`snapshot_dao`、`price_cache_dao`，统一以 `DatabaseError` 收口数据库异常。

**核心算法**
- `portfolio/calculator.py`：移动加权平均成本法，买入费用摊入成本、卖出保持成本价、`FEE` 独立计费；提供 `summarize` 与 `fee_breakdown`。
- `portfolio/allocator.py`：按资产类型的配置占比计算。
- `portfolio/metrics.py`：净值与收益指标。

**服务层**
- `services/portfolio_service.py`：持仓汇总，返回纯数据对象供 CLI / 未来 GUI 渲染。
- `services/sync_service.py`：价格同步编排，带 TTL 缓存跳过与单标的失败隔离。
- `services/chart_service.py`：净值曲线数据准备。

**数据接入**
- `data/fetcher.py`：数据源工厂，A 股 / 美股 / 黄金三市场分发，同时提供同步与异步入口。
- akshare → yfinance 三级降级与超时重试；akshare / yfinance 懒加载，未安装时仅在实际调用时抛错。

**CLI（10 个子命令）**
- `holdings init`：创建数据库与默认 `config.yaml`。
- `holdings add`：新增交易，支持 `--fee`（佣金、印花税、托管费）与 `--group`。
- `holdings list`：持仓明细，支持按盈亏率排序与组合筛选。
- `holdings import`：CSV 批量导入，支持费用列映射。
- `holdings sync`：拉取最新价格，支持按市场筛选。
- `holdings report`：综合报表，`--verbose` 显示费用分项与配置占比。
- `holdings snapshot`：记录总资产快照。
- `holdings chart`：生成交互式净值曲线 HTML。
- `holdings remove`：删除交易记录（二次确认）。
- `holdings check`：检查运行环境依赖是否齐全。

**文档**
- 项目愿景与范围（`docs/VISION.md`）、用户故事（`docs/USER_STORIES.md`）、功能清单（`docs/FEATURES.md`）。
- 数据库设计（`docs/SCHEMA.md`）、错误码与异常处理规范（`docs/ERROR_HANDLING.md`）、配置项字典（`docs/CONFIG_SPEC.md`）。
- 架构与模块隔离规范（`docs/ARCHITECTURE.md`）、代码风格与 Git 提交规范（`docs/CODING_STANDARDS.md`）、测试策略（`docs/TESTING_STRATEGY.md`）。
- 用户手册（`docs/USER_GUIDE.md`）、常见问题（`docs/FAQ.md`）、开发路线图（`docs/ROADMAP.md`）、贡献指南（`CONTRIBUTING.md`）。

**工程化**
- GitHub Actions CI：Python 3.10 / 3.12 / 3.13 矩阵跑 `pytest` 与 `ruff check` / `ruff format --check`。
- `pytest` 单元测试覆盖加权成本算法、storage DAO 与 services 层（网络请求全部 mock，不触网）。

## [0.0.0] - 规划阶段

### Added
- 确立项目愿景、技术栈与三层架构。
- 明确数据库设计（含手续费与基金托管费支持）。
- 定义 CLI 命令设计与 GUI 扩展策略。
