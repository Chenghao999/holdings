# 功能清单（FEATURES）

## v1.0（CLI）

### 交易管理

- 新增交易（`add`），支持 `--fee` 参数。
- 删除交易（`remove`），需二次确认。
- CSV 批量导入（`import`），支持费用列映射（`--fee-column`）。
- 多组合 / 多账户区分（`--group`）。

### 持仓与计算

- 持仓明细查询（`list`），支持按盈亏率等字段排序。
- 移动加权平均成本核算，费用计入成本。
- 持仓盈亏与收益率计算。

### 数据同步

- 拉取 A 股（akshare）、美股 / 国际黄金（yfinance）价格。
- 三级降级容错与 5 分钟缓存防封禁。

### 报表与可视化

- 综合报表（`report`）：持仓表格 + 配置占比柱状图 + 费用汇总。
- 资产快照（`snapshot`）。
- 净值曲线图导出（`chart`，生成交互式 HTML）。

## v1.0 支持的市场与资产类型

| 市场 | 资产类型 | 数据源 |
|------|---------|--------|
| A 股 | stock / etf | akshare（降级 yfinance） |
| 美股 | stock / etf | yfinance |
| 黄金 | gold | akshare（国内现货 / 黄金ETF `518880`，降级 `GC=F`） |

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
| `holdings list` | 查看持仓明细 |
| `holdings import` | CSV 批量导入 |
| `holdings sync` | 同步最新价格 |
| `holdings report` | 生成综合报表 |
| `holdings snapshot` | 记录资产快照 |
| `holdings chart` | 生成净值曲线图 |
| `holdings remove` | 删除交易 |