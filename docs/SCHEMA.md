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

### asset_meta 字段说明

- `annual_management_fee`：年化管理费率（如基金托管费），用于参考展示，不直接参与单笔成本计算。真实费用通过 `transactions.fee` 逐笔记录。

## 价格缓存过期策略

- 同一 `symbol` 在 `price_cache` 中若 `update_time` 距今 **不足 5 分钟**，直接返回缓存，不发起网络请求。
- 缓存时间可通过配置项 `cache_ttl_seconds` 调整（见 [CONFIG_SPEC.md](CONFIG_SPEC.md)）。
- `source` 字段记录数据来源，便于排查降级链路。

## 索引策略

| 索引 | 作用 |
|------|------|
| `idx_trans_symbol` | 加速按标的查询交易 |
| `idx_trans_date` | 加速按交易日范围查询 |
| `idx_cache_time` | 加速判断缓存是否过期 |