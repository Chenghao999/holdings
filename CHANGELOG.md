# 变更日志（CHANGELOG）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/) 格式，并使用 [Semantic Versioning](https://semver.org/) 进行版本管理。

## [Unreleased]

### Added
- **`report` 新增绩效行**（[BACKLOG B-02](docs/BACKLOG.md)）：从 `snapshots` 表算最大回撤、
  年化收益与夏普，接进 `holdings report` 的输出。新增 `services/report_service.py`
  负责口径判定，`portfolio/metrics.py` 的 `periods_per_year` / `return_series` 负责折算。
  - **算不出来时显示 `—`，不显示 0**：单条快照算出的「回撤 0.00%」看着像结论，
    实际只是没有第二个点；`metrics.py` 此前 0% 覆盖，也从未被任何命令调用过。
  - **夏普不再默认「入参是日收益」**：`sharpe_ratio` 原先硬编码 `sqrt(252)`，
    任何人把快照收益直接喂进去都会得到一个乘了 15.87 的假数。现改为必填
    `periods_per_year`，并新增 `periods_per_year()` 由快照间隔反推采样频率——
    间隔不规律（变异系数 > 25%，例如漏记一周）时返回 `None`，报表显示 `—`。
  - 年化收益用首末快照的**真实天数**折算，并设 30 天最小跨度：
    相隔一天的两次快照能外推出天文数字的年化收益，那是数学上成立、决策上无用的数。

### Fixed

**加载配置会改写全局默认值**
- `load_config()` 此前用 `dict(DEFAULT_CONFIG)` 复制默认配置——**浅拷贝**。
  嵌套的 `data_sources` / `sync` 仍是同一批对象，`_deep_merge` 会顺着它们
  就地改到模块级的 `DEFAULT_CONFIG` 上。后果是「加载过一份配置」这件事本身
  改变了此后所有加载得到的默认值：同一进程内先读 A 再读 B，B 拿到的默认值
  已经被 A 污染过。CLI 每次只跑一条命令所以看不出来，GUI 与测试里立刻现形。
  现改为 `copy.deepcopy()`，并加了两条回归用例。

**`sync` 会被不响应的数据源挂死**
- 全项目此前**没有任何网络超时**：`akshare` 与 `yfinance` 都没有可用的超时手段
  （akshare 压根没有该参数），上游一旦卡住，`holdings sync` 会无限期等待，
  用户只能 Ctrl-C。现新增 `data/resilience.call_with_timeout`，在守护线程里执行
  取价并按 `sync.timeout_seconds` 放弃等待，该标的记为失败、退出码 1。
  超时是**每个标的**的预算；`0` 或负数表示不限时。
- 超时的语义是「放弃等待」而不是「取消请求」：Python 没有安全的线程取消机制，
  被放弃的请求仍会在后台跑完。守护线程保证它不会拖住进程退出——这正是这套
  方案能成立的关键，`tests/test_resilience.py` 对这一点有专门断言。
- `sync.timeout_seconds` 与 `sync.retry_count` 此前都是「改了不起作用」的配置项，
  现均真正生效：重试次数读配置（默认 1 次重试 = 共 2 次尝试）。顺带修掉退避的
  位置——原先 `sleep` 写在 `except` 末尾，最后一次失败后还要白等 0.5 秒才降级。
- `default_market` 同样接通：`sync` 未显式指定 `--market` 时取该值。
  取值非法（如写成不存在的市场）会按参数校验失败报错并返回退出码 5，
  而不是悄悄按「全部」跑——静默回落会让用户以为配置生效了。
  至此 4 个死配置项只剩 `data_sources.priority`；`CONFIG_SPEC.md` / `FAQ.md` /
  `FEATURES.md` 的标注同步更新。

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
- `list --sort 盈亏率` 此前**静默失效**：中文表头被直接拿去和 DataFrame 的英文列名
  （`profit_rate`）比较，永不匹配，于是既不排序也不报错——文档与 README 都写了这个
  示例，用户以为排了序，拿到的其实是原始顺序。现建立中英列名映射，并用
  `click.Choice` 校验取值，非法字段名返回退出码 5 而不是静默通过。
- `holdings chart` 缺 plotly 时抛的是裸 `RuntimeError`，绕过退出码映射且只提示
  「未安装 plotly」。现改为 `MissingDependencyError`（退出码 1），并给出可执行的
  `pip install 'holdings[chart]'`。

### Changed
- 新增 `chart` 可选依赖组（`plotly`）。此前 plotly 只挂在 `gui` extra 里，
  只装 `holdings[data]` 的用户跑 `holdings chart` 会缺依赖，安装提示还要求连
  PySide6 一起装——画一张净值曲线不该需要 GUI 框架。
- 从 `dev` extra 移除 `responses`：全项目零引用（见 [TESTING_STRATEGY](docs/TESTING_STRATEGY.md)）。

### Docs
- 全量核对文档与代码，修掉一批「文档承诺、代码没有」的陈述：
  - 「三级降级 + 超时重试」名不副实：只有 A 股有 akshare→yfinance 的降级与 1 次重试，
    美股是 yfinance 单一数据源，且**全项目没有任何网络超时设置**。
    README / FEATURES / ROADMAP / FAQ 均已改为准确描述。
  - `CONFIG_SPEC.md` 标注出 4 个**尚未生效**的配置项（`default_market`、
    `data_sources.priority`、`sync.timeout_seconds`、`sync.retry_count`）——
    此前文档把它们写成生效的行为，FAQ 甚至建议用户去调 `sync.retry_count` 排查网络问题，
    而那个值根本没有代码读取。
  - `CONFIG_SPEC.md` 修正 `save_config()`（不存在，实为 `Config.save()`）、
    「文件不存在时自动生成配置」（实际不落盘）、字段取值校验（尚未实现）三处描述。
  - `USER_GUIDE.md` 补上此前完全没写的第 10 个命令 `holdings check`；
    修正 `add` 的「支持交互式输入」（不存在）、`snapshot --note "…"` 这个跑不通的示例
    （`--total` 才是必填，且 `--note` 只回显不入库）、`report` 的「配置占比柱状图」
    （实际是表格）、`chart --start`（预留参数，尚未生效）；新增退出码一览表。
  - `TESTING_STRATEGY.md` 更新为真实的测试文件树与用例数，改正不存在的
    `test_fetcher_mock.py`，补上实测覆盖率（全项目 67%，`calculator.py` 99%，
    `metrics.py` 0%）与低于目标的区域。
  - `FEATURES.md` 补上 `check` 命令行；说明 `AssetType` 的 `etf` 目前没有录入入口。
  - `ARCHITECTURE.md` 目录树按实际文件重写；新增「铁律当前执行情况」一节，
    如实记下铁律 3（`cli` 只经 `services`）被 `snapshot` / `remove` 两处违反，
    `init` 作为引导命令属合理例外。
- 新增 [`docs/BACKLOG.md`](docs/BACKLOG.md)：**待办清单的唯一权威来源**。
  收录体检剩余的 9 项发现、体检后新发现的问题（窄终端表格截断、三处零引用死代码）
  与已知能力缺口，共 12 项（B-01~B-12），每项给出优先级 / 位置 / 现状 /
  要做什么 / **完成判据**，并标注了动手前必须先看的约束
  （如 `annual_management_fee` 不得改为自动计提、`sharpe_ratio` 的 `sqrt(252)`
  与不规律快照间隔冲突）。`ROADMAP.md` 的 v1.0.0 勾选项改为指向该文件的条目编号，
  不再重复维护一份会走样的平行清单。

### Added
- `holdings/exceptions.py`：统一的异常基类与退出码契约。
- `MissingDependencyError`：可选依赖缺失（如画图缺 plotly），退出码 1，
  与「数据源不可用」区分开——重试没有意义，必须给出安装命令。
- `services/trade_service.py`：交易写入闸门（`add_transaction` / `add_transactions`）。
- `storage/transaction_dao.add_many()`：单事务批量写入，支持整批回滚。
- `chart` 可选依赖组（见「Changed」）。
- 测试从 56 个增至 112 个，新增 `test_validation.py`、`test_trade_service.py`、
  `test_import_cmd.py`、`test_config.py`、`test_list_cmd.py`、`test_cli_errors.py`；
  此前零覆盖的 `utils/` 与 `cli/` 错误路径开始有测试，退出码契约与排序契约被逐条锁住。
- 随着 B-02 接线，测试增至 **159 个**，新增 `test_metrics.py`（31 个用例，覆盖空序列 /
  单点 / 全涨 / 全跌 / 已知回撤 / 采样口径）与 `test_report_cmd.py`；
  全项目行覆盖率 **67% → 76%**，`metrics.py` **0% → 100%**。

### Planned
- 逐项清掉 [`docs/BACKLOG.md`](docs/BACKLOG.md) 的 B-01~B-12。
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
