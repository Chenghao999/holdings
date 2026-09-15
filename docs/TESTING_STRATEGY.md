# 测试策略（TESTING_STRATEGY）

> 明确「哪些必须测」「哪些可以 Mock」，保证核心计算逻辑的正确性。

## 测试框架

- `pytest` + `pytest-cov`。
- 目标：核心计算模块覆盖率优先。

## 必须测试（核心业务逻辑）

| 模块 | 必须覆盖的用例 | 当前覆盖 |
|------|---------------|---------|
| `portfolio/calculator.py` | 加权平均成本（含费用归集）、买入/卖出/FEE 处理、盈亏与收益率计算 | ✅ 99% |
| `portfolio/allocator.py` | 资产配置占比计算 | ✅ 100% |
| `portfolio/metrics.py` | 年化收益、最大回撤、夏普比率 | ❌ 0%（模块尚未被任何命令调用） |
| `storage/` DAO | 增删改查、事务回滚、约束冲突 | ✅ 80%~100% |
| `services/` 编排层 | 汇总、同步缓存、写入闸门 | ✅ 98%~100% |

### 优先级最高：加权平均成本

使用**假数据**做纯单元测试，验证：

1. 买入时费用计入成本：
   `新成本 = (旧数量×旧成本 + 新数量×新价 + 新费用) / (旧数量 + 新数量)`
2. 卖出时数量减少、成本价不变。
3. `trade_type='FEE'` 不改变数量与成本，仅累计费用。
4. **卖出数量超过当时持有量必须被拒绝**（此前会把数量与总成本算成负数）。

## 可以 Mock（外部依赖）

| 模块 | Mock 方式 |
|------|-----------|
| `data/` 数据源 | 不实际联网。当前 `tests/test_data.py` 只验证导入链与工厂分发；**具体的网络降级路径尚无测试**，可用 `unittest.mock` 打桩 `akshare` / `yfinance` 模块 |

> `responses`（HTTP 层打桩库）此前声明在 `dev` extra 里但全项目零引用，
> 已从 `pyproject.toml` 移除；需要时再加。

## 测试类型划分

| 类型 | 说明 |
|------|------|
| 单元测试 | `portfolio/` 计算逻辑，`storage/` DAO 逻辑（临时文件 SQLite） |
| 集成测试 | CLI 命令端到端（`import` → 落库、`add` → 校验、退出码契约） |
| Mock 测试 | `data/` 数据获取层（待补） |

## 测试目录约定

```text
tests/
├── conftest.py            # 共享夹具：db_path、make_tx
├── test_calculator.py     # 核心：加权平均成本
├── test_validation.py     # 交易领域校验（check_trade）
├── test_allocator.py
├── test_storage.py        # DAO + 建表
├── test_trade_service.py  # 写入闸门与乱序补录
├── test_services.py       # 汇总 / 同步 / 图表数据
├── test_data.py           # 数据源工厂与导入链（不触网）
├── test_config.py         # 配置加载与 YAML 错误
├── test_cli_errors.py     # 退出码契约（需通过 main()，见下）
├── test_import_cmd.py     # CSV 整批事务与表头校验
└── test_list_cmd.py       # --sort 排序契约
```

> **`test_cli_errors.py` 必须走 `main()`**：`CliRunner` 会绕过 `main()` 里的
> 异常→退出码映射层，测不到 `pyproject.toml` 入口点是否指向 `main`。
> 该文件给 `sys.argv` 打桩后直接调用 `main()`。

## 覆盖率目标

- `portfolio/calculator.py`：**≥ 90%**（关键在于费用与卖出边界）— 当前 **99%**。
- 全项目行覆盖率：当前 **67%**（`python -m pytest --cov=holdings`）。
- 明确低于目标的区域：`portfolio/metrics.py`（0%）、`cli/renderers/`（15%~0%）、
  `utils/deps.py`（0%）、`data/` 三个 fetcher（18%~29%）。
  其中 `metrics.py` 的 0% 是「模块还没被接上」的直接后果，接线后应同步补测。
