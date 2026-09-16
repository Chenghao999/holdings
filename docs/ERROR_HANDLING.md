# 错误码与异常处理规范（ERROR_HANDLING）

> 统一 CLI 与未来 GUI 的报错反馈格式，保证用户与开发者都能快速定位问题。

## 自定义异常类

统一在异常层定义业务异常，供所有层级抛出：

| 异常类 | 触发场景 | 用户友好提示 |
|--------|---------|-------------|
| `HoldingsError` | 所有自定义异常的基类 | - |
| `DataSourceUnavailableError` | 数据源（akshare / yfinance）不可用或超时 | 数据源不可用，请检查网络或稍后重试 |
| `SymbolNotFoundError` | 标的代码不存在或无法识别 | 未找到该标的，请检查代码与市场 |
| `ConfigError` | 配置文件缺失、YAML 语法错误或字段非法 | 配置错误，请检查 config.yaml |
| `DatabaseError` | 数据库读写失败 | 数据库操作失败 |
| `TradeValidationError` | 交易数据不合法（买入数量非正、卖出超过当时持有量、费用或单价为负） | 该笔交易不合法，已拒绝写入 |
| `MissingDependencyError` | 依赖未安装（画图缺 plotly、`check` 发现必需包缺失） | 缺少依赖，请按提示安装 |
| `RecordNotFoundError` | 要操作的记录不存在（如 `remove --id` 给的交易号） | 未找到该记录 |

以上异常**均继承 `HoldingsError`**，实现位于 `holdings/exceptions.py`；
`storage` / `data` / `utils` 各自重新导出对应异常，历史导入路径（如
`from holdings.storage.db import DatabaseError`）继续可用。

## CLI 退出码规范

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `1` | 网络错误 / 数据源不可用（**可重试**） |
| `2` | 数据不存在（标的 / 交易记录未找到） |
| `3` | 配置错误 |
| `4` | 数据库错误 |
| `5` | 参数校验失败 / 用户输入非法 |
| `6` | 缺少依赖（**重试没有用，要装包**） |
| `130` | 用户中止（`Ctrl-C` 或拒绝确认） |

> **为什么把「缺少依赖」从 1 里拆出来**：它和「网络不通」是两种完全不同的
> 处置——前者重试多少次都一样，后者才值得重试。CI 里靠退出码分流时，并到
> 同一个码会让「网络抖了一下」和「环境没装好」看起来是同一种故障，
> 而它们的修法一个是重跑、一个是改 Dockerfile。

## 错误反馈格式

### CLI

- 错误信息通过 `stderr` 输出，采用统一前缀：`错误（<错误码>）：<人类可读信息>`。
- 使用 `click` 的 `UsageError` / `ClickException` 或自定义异常 + 顶层捕获，保证退出码一致。

示例：

```text
错误（1）：A股数据源不可用：600519
错误（2）：未找到交易 #99999
错误（6）：缺少必需依赖：yfinance、akshare；请运行 pip install -e .
```

### GUI（未来）

- 异常统一在 Service 层抛出，GUI 通过信号槽捕获并映射为消息框 / Toast 提示。
- 不再抛出 `None` 或裸字符串，保证 GUI / CLI 共用同一套异常语义。

## 处理原则

1. 数据获取层（`data/`）对网络异常做**重试 + 降级**，仅在彻底失败时抛出 `DataSourceUnavailableError`。
2. 存储层（`storage/`）将底层 SQLite 异常包装为 `DatabaseError`，不向上泄漏底层异常。
3. 参数校验分两处完成，失败均以退出码 `5` 返回：
   - **取值合法性**（市场、交易类型、日期格式）在命令入口用 `click.Choice` / 回调完成；
   - **领域合法性**（卖出不得超过当时持有量等，需要历史持仓才能判断）在
     `portfolio.calculator.check_trade` 中定义，由 `services.trade_service` 在**落库前**
     调用，`add` 与 `import` 两条写入路径都必须经过它。
4. 任何异常不得使程序静默失败；CLI 必须输出明确提示并返回非零退出码。
5. **命令体里不出现 `SystemExit`**：异常一律抛到 `main()`，由 `cli.main.exit_code_for`
   统一映射。命令里自己 `SystemExit(N)` 会绕过映射层，退出码与文案迟早各走各的。
   唯一的例外是 `main()` 自身——它正是那个映射层。
6. `pyproject.toml` 的 console script **必须指向 `holdings.cli.main:main`**。
   指向裸 click group `cli` 会绕开下面的异常映射层，本文档定义的退出码与
   `错误（N）：` 前缀将全部失效，用户只会看到裸 traceback 与恒定的退出码 1。