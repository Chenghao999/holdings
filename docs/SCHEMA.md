# 数据库设计说明（SCHEMA）

> 本文档详细说明 `holdings` 的数据库表结构、字段约束与索引策略。底层使用内置 `sqlite3`，数据存储于 `data/holdings.db`。

## 实体关系总览

```text
transactions (交易记录)         1 ── N  按 symbol 关联  asset_meta (资产信息)
  ├── trade_type: BUY / SELL / FEE
  └── portfolio_group: 组合分组

snapshots (每日快照)
  └── snapshot_date UNIQUE

price_cache (价格缓存)
  └── symbol PRIMARY KEY
```

四张表职责：

| 表 | 职责 |
|----|------|
| `transactions` | 核心流水，记录每笔买卖与费用，支持多组合分组 |
| `snapshots` | 净值曲线数据源，记录任意时间点总资产快照 |
| `asset_meta` | 资产基础信息与名称缓存，含年化管理费率 |
| `price_cache` | 最新价格缓存，配合 5 分钟过期策略减少网络请求 |

## 建表 SQL

```sql
-- 1. 交易记录表（支持多账户/组合，且包含费用字段）
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_group TEXT DEFAULT '默认',   -- 未来GUI支持多账户（如：养老金、压岁钱）
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,                 -- 'A股' / '美股' / '黄金'
    asset_type TEXT NOT NULL,             -- 'stock' / 'etf' / 'gold'
    trade_date TEXT NOT NULL,
    trade_type TEXT NOT NULL,             -- 'BUY' / 'SELL' / 'FEE'
    quantity REAL NOT NULL,               -- 对于FEE类型，quantity填0
    price REAL NOT NULL,                  -- 对于FEE类型，price填0
    fee REAL DEFAULT 0,                   -- 统一费用字段（佣金、印花税、托管费等）
    notes TEXT
);

-- 2. 每日快照表（净值曲线数据源）
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL UNIQUE,
    total_value REAL NOT NULL,
    cash_balance REAL DEFAULT 0,
    equity_value REAL NOT NULL,
    gold_value REAL NOT NULL,
    note TEXT,                             -- 备注，不传存 NULL（不是空串）
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 3. 资产基础信息表（名称缓存）
CREATE TABLE asset_meta (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    market TEXT,
    currency TEXT DEFAULT 'CNY',
    annual_management_fee REAL DEFAULT 0,  -- 年化管理费率（如基金托管费），用于参考
    updated_at TEXT
);

-- 4. 价格缓存表
CREATE TABLE price_cache (
    symbol TEXT PRIMARY KEY,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'CNY',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT                           -- 'akshare' / 'yfinance'
);

-- 索引优化
CREATE INDEX idx_trans_symbol ON transactions(symbol);
CREATE INDEX idx_trans_date ON transactions(trade_date);
CREATE INDEX idx_cache_time ON price_cache(update_time);
```

## 字段约束与语义说明

### transactions

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `portfolio_group` | TEXT | DEFAULT '默认' | 组合分组，预留多账户支持 |
| `symbol` | TEXT | NOT NULL | 资产代码，如 `600519`、`518880`、`GC=F` |
| `market` | TEXT | NOT NULL | `A股` / `美股` / `黄金` |
| `asset_type` | TEXT | NOT NULL | `stock` / `etf` / `gold` |
| `trade_date` | TEXT | NOT NULL | 交易日，格式 `YYYY-MM-DD` |
| `trade_type` | TEXT | NOT NULL | `BUY` / `SELL` / `FEE` |
| `quantity` | REAL | NOT NULL | 数量，`FEE` 类型填 0 |
| `price` | REAL | NOT NULL | 单价，`FEE` 类型填 0 |
| `fee` | REAL | DEFAULT 0 | 统一费用字段（佣金、印花税、托管费） |
| `notes` | TEXT | - | 备注 |

### trade_type 的三种语义

| 值 | 语义 | 对数量/成本影响 |
|----|------|----------------|
| `BUY` | 买入 | 数量增加，费用计入成本 |
| `SELL` | 卖出 | 数量减少，成本价不变 |
| `FEE` | 定期/独立费用 | 不改变数量与成本，仅影响现金余额，报表单独列示 |

> **这张表也是本列的取值全集**：对账单里的分红 / 送转 / 配股 / 银证转账 / 利息
> **不会**写进 `transactions`，因此不会出现在这一列里——`import` 把它们逐行报出来
> 但不入账（[B-27](BACKLOG.md#b-27)，分类表见 [USER_GUIDE](USER_GUIDE.md) 第 5 节）。
> 也就是说，库里看到 `trade_type` 只有这三种，不是导入漏了，是设计如此。

### snapshots 字段说明

- `snapshot_date` 唯一：同一天只保留一份快照，重复写入报错而不是覆盖。
- `note`：`holdings snapshot --note "…"` 写的备注。不传存 `NULL`——「没写备注」
  与「写了个空备注」在查询与展示上是两回事。

> **补列迁移**：`note` 是后加的列，而 `CREATE TABLE IF NOT EXISTS` 对**已经存在**
> 的表完全不生效，老库不会自己长出这一列。`storage/db.py` 的 `_migrate()` 用
> `PRAGMA table_info` 探测后 `ALTER TABLE` 补上，判定「这一列在不在」而不是查
> 版本号——这个库由用户直接拿着用，不会有谁去维护 schema_version。

### asset_meta 字段说明

| 字段 | 说明 |
|------|------|
| `symbol` | 主键，标的代码；重复写入是**覆盖**而不是插第二条 |
| `name` | 标的名称，`holdings list` 的名称列取自这里；没有记录时回落显示代码 |
| `market` | 市场（当前仅记录，不参与计算） |
| `currency` | 币种，默认 `CNY` |
| `annual_management_fee` | 年化管理费率（%），**仅作参考展示，不直接参与单笔成本计算** |

> ⚠️ **`annual_management_fee` 不参与任何成本计算。** 真实费用通过
> `transactions.fee` 逐笔记录（`holdings add --fee`）。
> `holdings report` 会印一行「年化管理费率合计 x%（仅供参考，未计入成本）」，
> 那只是「你填过的费率加起来是多少」。
>
> **不要把它做成「按持仓天数自动计提管理费」**：那会让 `holdings list` 的成本价
> 随日历漂移，与 `portfolio/calculator.py` 的移动加权平均成本法直接冲突。
> `tests/test_meta_cmd.py::test_the_rate_changes_nothing_about_the_numbers`
> 守着这条——录入费率前后，成本价与盈亏必须逐项相等。

录入方式见 [USER_GUIDE 的第 4 节](USER_GUIDE.md)。

## 价格缓存过期策略

- 同一 `symbol` 在 `price_cache` 中若 `update_time` 距今 **不足 5 分钟**，直接返回缓存，不发起网络请求。
- 缓存时间可通过配置项 `cache_ttl_seconds` 调整（见 [CONFIG_SPEC.md](CONFIG_SPEC.md)）。
- `source` 字段记录数据来源，便于排查降级链路。
- **`currency` 决定这个标的进不进汇总**：非 `CNY` 的标的不与人民币相加，
  汇总里排除、行内由行情推出来的数字显示 `—`，现价带上币种。基准货币是
  `services/portfolio_service.BASE_CURRENCY`（[B-19](BACKLOG.md#b-19)）。
  注意 `asset_meta.currency` **不参与**这个判断——它是用户对标的的备注，
  而这里是行情本身带来的事实（`US_STOCK` 的报价就是美元）。

## 索引策略

| 索引 | 作用 |
|------|------|
| `idx_trans_symbol` | 加速按标的查询交易 |
| `idx_trans_date` | 加速按交易日范围查询 |
| `idx_cache_time` | 加速判断缓存是否过期 |