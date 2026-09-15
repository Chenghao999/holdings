# 变更日志（CHANGELOG）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/) 格式，并使用 [Semantic Versioning](https://semver.org/) 进行版本管理。

## [Unreleased]

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
