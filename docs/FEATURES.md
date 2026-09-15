# 功能清单（FEATURES）

## v1.0（CLI）

### 交易管理

- 新增交易（`add`），支持 `--fee` 参数。
- 删除交易（`remove`），需二次确认。
- CSV 批量导入（`import`），支持费用列映射（`--fee-column`）。
- 多组合 / 多账户区分（`--group`）。

### 持仓与计算

- 持仓明细查询（`list`），支持按盈亏率等字段降序排序。
- 移动加权平均成本核算，买入费用摊入成本、卖出保持成本价。
- 持仓盈亏与收益率计算。
- 写入前按历史持仓校验交易（卖出不得超持有），非法交易拒绝落库。

### 数据同步

- 拉取 A 股（akshare，失败降级 yfinance）、美股 / 国际黄金（yfinance）价格。
- 5 分钟缓存防重复请求；单标的失败不影响其余标的。

> **降级链路的真实范围**：仅 A 股有 akshare → yfinance 的降级；美股只有
> yfinance 单一数据源，黄金走 A 股链路或 yfinance 的 `GC=F`。取价有超时保护
> （`sync.timeout_seconds`，默认每个标的 10 秒），重试次数读 `sync.retry_count`。
> **降级顺序仍硬编码在 `data/` 层**，`data_sources.priority` 尚未接线。
> 相关配置项见 [CONFIG_SPEC](CONFIG_SPEC.md)。

### 报表与可视化

- 综合报表（`report`）：持仓表格 + 费用汇总（`--verbose` 追加费用分项表与配置占比表）。
- 资产快照（`snapshot`）。
- 净值曲线图导出（`chart`，生成交互式 HTML，需 `holdings[chart]`）。

## v1.0 支持的市场与资产类型

| 市场 | 数据源 | 说明 |
|------|---------|------|
| A 股 | akshare（降级 yfinance） | 股票与 ETF 均按 A 股行情拉取 |
| 美股 | yfinance | |
| 黄金 | akshare（国内现货 / 黄金ETF `518880`，降级 `GC=F`） | |

> `AssetType` 枚举定义了 `stock` / `etf` / `gold` 三种，但**当前没有区分 ETF 的入口**：
> `add` 按市场推断，市场为「黄金」时记 `gold`，其余一律记 `stock`。
> 需要标注 ETF 时请直接改库，或等后续版本提供显式参数。

## v2.0（GUI / TUI，规划中）

- Textual TUI 终端仪表盘。
- Streamlit / FastAPI 数据看板。
- 拖拽导入 CSV、可视化图表、系统托盘刷新。
- PySide6 桌面应用（跨平台打包）。

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
| `holdings import` | CSV 批量导入（整批事务） |
| `holdings sync` | 同步最新价格 |
| `holdings report` | 生成综合报表 |
| `holdings snapshot` | 记录资产快照 |
| `holdings chart` | 生成净值曲线图 |
| `holdings remove` | 删除交易 |
| `holdings check` | 检查运行环境依赖 |