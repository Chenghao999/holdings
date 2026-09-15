# 测试策略（TESTING_STRATEGY）

> 明确「哪些必须测」「哪些可以 Mock」，保证核心计算逻辑的正确性。

## 测试框架

- `pytest` + `pytest-cov`。
- 目标：核心计算模块覆盖率优先。

## 必须测试（核心业务逻辑）

| 模块 | 必须覆盖的用例 |
|------|---------------|
| `portfolio/calculator.py` | 加权平均成本（含费用归集）、买入/卖出/FEE 处理、盈亏与收益率计算 |
| `portfolio/allocator.py` | 资产配置占比计算 |
| `portfolio/metrics.py` | 年化收益、最大回撤、夏普比率 |

### 优先级最高：加权平均成本

使用**假数据**做纯单元测试，验证：

1. 买入时费用计入成本：
   `新成本 = (旧数量×旧成本 + 新数量×新价 + 新费用) / (旧数量 + 新数量)`
2. 卖出时数量减少、成本价不变。
3. `trade_type='FEE'` 不改变数量与成本，仅累计费用。

## 可以 Mock（外部依赖）

| 模块 | Mock 方式 |
|------|-----------|
| `data/fetcher.py` 网络请求 | 使用 `responses` 库模拟 API 返回 |
| akshare / yfinance 数据源 | Mock 其返回的行情数据，不实际联网 |

## 测试类型划分

| 类型 | 说明 |
|------|------|
| 单元测试 | `portfolio/` 计算逻辑，`storage/` DAO 逻辑（内存 SQLite） |
| 集成测试（可选） | CLI 命令端到端（如 `add` → `list`），可用临时数据库 |
| Mock 测试 | `data/` 数据获取层，模拟网络响应 |

## 测试目录约定

```text
tests/
├── test_calculator.py       # 核心：加权平均成本
└── test_fetcher_mock.py     # 数据源 mock
```

## 覆盖率目标

- `portfolio/calculator.py`：**≥ 90%**（关键在于费用与卖出边界）。
- 数据获取层：以 mock 覆盖降级与重试路径，不追求行覆盖率。