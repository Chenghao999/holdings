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
| `portfolio/metrics.py` | 年化收益、最大回撤、夏普比率、采样口径判断 | ✅ 100% |
| `storage/` DAO | 增删改查、事务回滚、约束冲突 | ✅ 80%~100% |
| `services/` 编排层 | 汇总、绩效指标、同步缓存、写入闸门、表格契约（`holdings_cell` / 两条提示语） | ✅ 98%~100% |

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
| `data/` 数据源 | 不实际联网。`tests/test_data.py` 覆盖导入链、工厂分发、降级链路（重试次数、退避、降级时机、优先级顺序）与三个 fetcher 各自的解析分支（含缺依赖与未找到）；手法是 `monkeypatch.setitem(sys.modules, "akshare", 假模块)` |
| 网络超时 | `tests/test_resilience.py` 用**永不置位的事件**模拟不响应的上游（而不是 `sleep(N)`，整个文件不产生真实等待），断言按预算放弃、异常类型原样透传、守护线程不拖住进程退出 |

> `responses`（HTTP 层打桩库）此前声明在 `dev` extra 里但全项目零引用，
> 已从 `pyproject.toml` 移除；需要时再加。

## 测试类型划分

| 类型 | 说明 |
|------|------|
| 单元测试 | `portfolio/` 计算逻辑，`storage/` DAO 逻辑（临时文件 SQLite） |
| 结构测试 | `test_layering.py`：用 AST 扫源码，守分层铁律与「UI 可复用」；`test_packaging.py`：用 `git check-ignore` / `git ls-files` 守「该提交的文件真的提交了」——这两类约束用运行时断言测不出来 |
| 集成测试 | CLI 命令端到端（`import` → 落库、`add` → 校验、退出码契约） |
| Mock 测试 | `data/` 数据获取层（伪造 `akshare` / `yfinance` 模块，不触网） |
| 界面测试 | `test_tui.py` 用 Textual 的 `app.run_test()` headless 跑真实渲染；`test_web.py` 用 FastAPI 的 `TestClient` 直接打请求（不起真服务器——那只多出端口冲突这一种偶发失败）。`textual` / `fastapi` / `jinja2` / `httpx` 都在 `dev` extra 里 |

## 测试目录约定

```text
tests/
├── conftest.py            # 共享夹具：db_path、make_tx
├── test_calculator.py     # 核心：加权平均成本
├── test_validation.py     # 交易领域校验（check_trade）
├── test_allocator.py
├── test_metrics.py        # 回撤 / 年化 / 夏普与采样口径
├── test_storage.py        # 四个 DAO + 建表 + 补列迁移
├── test_trade_service.py  # 写入闸门与乱序补录
├── test_services.py       # 汇总 / 绩效指标 / 同步 / 图表
├── test_data.py           # 数据源：工厂、降级链路、重试、优先级、解析分支（不触网）
├── test_resilience.py     # 网络超时：sync 不被不响应的数据源挂死
├── test_config.py         # 配置加载、YAML 错误与字段取值校验
├── test_cli_errors.py     # 退出码契约（需通过 main()，见下）
├── test_import_cmd.py     # CSV 整批事务与表头校验
├── test_list_cmd.py       # --sort 排序契约
├── test_sync_cmd.py       # --market 默认值来自 default_market
├── test_report_cmd.py     # 绩效行：算不出来时必须显示 —，不是 0
├── test_snapshot_cmd.py   # 快照备注的写入、读取与列在不在
├── test_unpriced.py       # 没有行情时显示 —，不显示 −100%
├── test_multi_currency.py # 外币计价的标的不与人民币混加
├── test_narrow_terminal.py # 窄终端下代码列完整可见
├── test_chart_cmd.py      # --start 真的筛日期；空区间报错而非空白图
├── test_meta_cmd.py       # meta 录入/查看/删除；费率不影响成本与盈亏
├── test_check_cmd.py      # check 的报错前缀与两种模式退出码一致
├── test_formatter.py      # 数值显示：— 的语义、ratio 与 percent 不可互换
├── test_deps.py           # 依赖检测：缺包判定与 check 命令的依据
├── test_layering.py       # 分层铁律：核心层零输出、零终端依赖、依赖方向
├── test_packaging.py      # 源码树与分发包完整性：源码没被 .gitignore 吞掉、模板已入库
├── test_tui.py            # TUI：headless 跑真实界面；缺 textual 时的退出码
└── test_web.py            # Web 看板：三页的取值与提示语；缺依赖时的退出码、默认只绑本机
```

> **`test_cli_errors.py` 必须走 `main()`**：`CliRunner` 会绕过 `main()` 里的
> 异常→退出码映射层，测不到 `pyproject.toml` 入口点是否指向 `main`。
> 该文件给 `sys.argv` 打桩后直接调用 `main()`。

## 覆盖率目标

- `portfolio/calculator.py`：**≥ 90%**（关键在于费用与卖出边界）— 当前 **99%**。
- 全项目行覆盖率：当前 **96%**（400 个用例）；`data/` 层 **98%**
  （`python -m pytest --cov=holdings`）。门槛 `fail_under = 95`，达不到
  `pytest` 直接返回非零——数值与理由见下面的「CI 里跑什么」。
- 新增层不拉后腿：`web/app.py` **100%**——看板的每个分支（三个页面、缺 plotly、
  日期筛空、日期不合法）都有用例走到。
- 明确低于目标的区域：`cli/renderers/chart_renderer.py`（67%，漏的那一行是
  `figure.write_html()`——用例都止步于「该不该产图」，没有一条真的把文件写出来过）、
  `cli/renderers/table_renderer.py` 与 `cli/commands/init.py`（均 93%，前者是费用表与
  占比表的空分支，后者是缺必需依赖时的警告分支）。
  [BACKLOG](BACKLOG.md) 的 B-07 / B-09 / B-10 修掉的那几处已不在列
  （`cli/commands/sync.py` 由 22% 升至 95%）。

---

## CI 里跑什么

`.github/workflows/ci.yml` 分三个作业，各自证明一件**另外两个证明不了**的事
（来历见 [BACKLOG B-24](BACKLOG.md)）：

| 作业 | 证明什么 | 少了它，什么会漏过去 |
|------|----------|----------------------|
| `test`（3.10 / 3.12 / 3.13） | 用例、ruff、覆盖率门槛 | —— |
| `package` | 装出来的 wheel 能用 | `pip install -e` 与 `pythonpath = ["src"]` 都直接读源码树：文件根本没进 wheel，用例照样全绿（B-20 的模板就是这么丢的） |
| `extras` | `pyproject` 声明的每个 extra 都装得上 | 前两个作业装的是写死的那几个包，从不读 extra 声明本身：包名打错、版本号钉死成一个不存在的，谁都不会知道 |

三处容易写错、踩过一次的细节：

- **`package` 里的 `-o pythonpath=` 不能省。** `pyproject.toml` 写着
  `pythonpath = ["src"]`，不盖掉的话 pytest 会把源码树放回 `sys.path`，
  这个作业就退回成「测源码树」——而且照样全绿。同一作业里还有一句
  「`holdings.__file__` 必须在 `site-packages` 下」的断言，防的是守卫自己失效。
  这条命令的有效性实测过：故意让模板不进 wheel，它红 13 个用例，
  与 B-20 那次 CI 失败同数。
- **`extras` 的名单从 `pyproject.toml` 现读**，不在 workflow 里再抄一份：
  抄一份的话，将来加了 extra 而忘了同步到这里，这条检查就悄悄失效了。
- **`test` 作业装 `.[dev,chart]`。** 不装 plotly，绘图那几条用例会静默跳过，
  于是那几行代码成了「看着测过」的样子。`data` 那两组很重（实测 344MB），
  只在 `extras` 作业里装一次。
- 覆盖率门槛写在 `pyproject.toml` 的 `[tool.coverage.report]`，本地
  `pytest --cov` 与 CI 读同一份，不把数字再抄进 workflow。

