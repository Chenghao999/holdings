# 功能清单（FEATURES）

## v1.0（CLI）

### 交易管理

- 新增交易（`add`），支持 `--fee` 参数。
- 删除交易（`remove`），需二次确认。
- 对账单批量导入（`import`）：`--broker` 指定券商格式或按表头自动识别，
  `--fee-column` 映射费用列；编码自动探测（UTF-8 / GBK / UTF-16），不用先转码。
- 导入时**认得出但不入账**的行（分红派息 / 送股转增 / 配股 / 银证转账 / 利息）
  逐行列出行号与原因，不静默跳过；取值认不出的仍然整批拒绝。
  `--strict` 时整批不写、退出码 5（详见 [USER_GUIDE](USER_GUIDE.md) 第 5 节）。
- 导入**幂等**：同一份文件导两遍、或逐月导出的月份之间有重叠时，重复的行默认
  报出行号且一笔不写（`--dedupe skip` 跳过、`off` 放行）。
  判重按券商流水号，没有则按全字段指纹。
- 多组合 / 多账户区分（`--group`）。

### 持仓与计算

- 持仓明细查询（`list`），支持按盈亏率等字段降序排序。
- 移动加权平均成本核算，买入费用摊入成本、卖出保持成本价。
- 持仓盈亏与收益率计算。
- 写入前按历史持仓校验交易（卖出不得超持有），非法交易拒绝落库。

### 数据同步

- 拉取 A 股（akshare，失败降级 yfinance）、美股 / 国际黄金（yfinance）价格。
- 5 分钟缓存防重复请求；单标的失败不影响其余标的。

> **降级链路的真实范围**：A 股可选 akshare → yfinance，美股当前只有 yfinance
> 一个源，黄金由代码选路（国内代码走 A 股链路，`GC=F` 走国际金价）。
> 数据源顺序读 `data_sources.priority`，重试次数读 `sync.retry_count`
> （每个源各自计），取价有超时保护（`sync.timeout_seconds`，默认每个标的 10 秒）。
> 黄金不参与优先级配置，原因见 [CONFIG_SPEC](CONFIG_SPEC.md)。

### 报表与可视化

- 综合报表（`report`）：持仓表格 + 费用汇总（`--verbose` 追加费用分项表与配置占比表）。
- 终端界面（`tui`，可选依赖）：持仓与报表两屏，与 CLI 同源。
- 资产快照：`snapshot` 记录（含备注），`snapshots` 查看。
- 净值曲线图导出（`chart`，生成交互式 HTML，需 `holdings-cli[chart]`）。

## v1.0 支持的市场与资产类型

| 市场 | 数据源 | 说明 |
|------|---------|------|
| A 股 | akshare（降级 yfinance） | 股票与 ETF 均按 A 股行情拉取 |
| 美股 | yfinance | |
| 黄金 | akshare（国内现货 / 黄金ETF `518880`，降级 `GC=F`） | |

> `AssetType` 枚举定义了 `stock` / `etf` / `gold` 三种，但**当前没有区分 ETF 的入口**：
> `add` 按市场推断，市场为「黄金」时记 `gold`，其余一律记 `stock`。
> 需要标注 ETF 时请直接改库，或等后续版本提供显式参数。

## v2.0（界面层，进行中）

- ✅ Textual TUI 终端仪表盘（[B-15](BACKLOG.md#b-15)）。
- ✅ FastAPI 网页只读看板（[B-20](BACKLOG.md#b-20)）——持仓 / 报表 / 净值曲线三页，
  写入功能待写入闸门接入后再做。
- 多账户管理（[B-21](BACKLOG.md#b-21)）。
- 券商对账单导入：按券商解析，模块化增加新的证券公司（[B-27](BACKLOG.md#b-27) 起 7 项）。
- 拖拽导入 CSV、系统托盘刷新。
- PySide6 桌面应用（跨平台打包）——形态待定（[B-22](BACKLOG.md#b-22)）。

## 非目标（v1.0 明确不做）

- 自动下单 / 交易接口。
- 多币种复杂汇率换算。
- 社交分享。

## 命令能力总览

| 命令 | 能力 |
|------|------|
| `holdings init` | 初始化数据库与配置 |
| `holdings add` | 新增交易（含费用） |
| `holdings list` | 查看持仓明细（可按列排序） |
| `holdings import` | 对账单导入（按格式解析；整批事务；未入账的行逐行报出；重复的行查出来） |
| `holdings sync` | 同步最新价格 |
| `holdings report` | 生成综合报表 |
| `holdings snapshot` | 记录资产快照 |
| `holdings chart` | 生成净值曲线图 |
| `holdings remove` | 删除交易 |
| `holdings check` | 检查运行环境依赖 |