# 待办清单（BACKLOG）

> 2026-09-15 工程体检的剩余发现，加上体检后新发现的问题与已知能力缺口。
> **本文件是工作项的唯一权威清单**，路线图与体检报告只保留摘要并指向这里。

## 怎么读这份清单

- 每项给出 **优先级 / 位置 / 现状 / 要做什么 / 完成判据**。完成判据是「这件事算不算做完」的客观标准，
  不能自证「已改」——要么有用例锁住，要么有可复现的命令输出。
- 优先级沿用体检报告的 P1/P2/P3：**P1 = 文档承诺了但功能不存在**，
  **P2 = 会误导用户或丢数据**，**P3 = 工程卫生**。
- 改动任何一项时，顺手核对受影响的文档（尤其 `SCHEMA.md`、`USER_GUIDE.md`、`CONFIG_SPEC.md`）。
  这批问题的成因几乎都是「文档先行、实现没跟上」，改实现时不同步改文档会再生产一批。
- 条目标题形如 `B-07`，可在提交信息与 PR 里直接引用（如 `fix: 修正窄终端表格截断 (B-07)`）。

**12 项是怎么来的**：

- 体检报告剩余 **9 项发现**对应 8 个条目 —— B-01、B-02、B-03、B-04、B-06、B-07、B-09，
  加上 B-08（「`remove` 报错格式」与「`check --json` 退出码」是同一个契约问题的两面，合并为一项）。
- 另有 **4 项**不在那 9 项里：
  - [B-05](#b-05) 死配置项与网络超时 —— 报告里那一行标记的是「文档已改正」，
    让配置项**真正生效**是没做的工作；
  - [B-10](#b-10) `data/` 层降级路径测试 —— 报告只在模块完整度表里提了一句；
  - [B-11](#b-11) 铁律 3 的违反 —— 同上，只在 `ARCHITECTURE.md` 里记录过；
  - [B-12](#b-12) 零引用死代码 —— 体检后新 grep 出来的，不在最初的清单里。

## 总览

| ID | 优先级 | 一句话 | 位置 |
|----|--------|--------|------|
| [B-01](#b-01) | P1 | `asset_meta` 表零 DAO，年化管理费率无处可填 | `storage/`、`cli/` |
| [B-02](#b-02) | ✅ 已完成 | `metrics.py` 三个纯函数从未被调用 | `services/report_service.py` |
| [B-03](#b-03) | P2 | `--note` 回显但不入库，静默丢数据 | `models/snapshot.py`、`storage/snapshot_dao.py` |
| [B-04](#b-04) | P2 | `--start` 是空参数，传了不生效 | `cli/commands/chart.py`、`services/chart_service.py` |
| [B-05](#b-05) | P2 | 4 个配置项改了不起作用；网络调用无超时 | `utils/config.py`、`data/` |
| [B-06](#b-06) | P2 | 未同步时显示「−100%」，看起来像血亏 | `services/portfolio_service.py`、`cli/renderers/` |
| [B-07](#b-07) | P2 | 80 列终端下代码列只剩 `6005…` | `cli/renderers/` |
| [B-08](#b-08) | P2 | `remove` / `check` 不走统一前缀；`check --json` 漏报退出码 | `cli/commands/remove.py`、`check.py` |
| [B-09](#b-09) | P3 | `deps.py` 零测试 | `tests/` |
| [B-10](#b-10) | P3 | 三个 fetcher 覆盖率 18%~29%，降级路径无测试 | `tests/test_data.py` |
| [B-11](#b-11) | P3 | `cli` 越过 `services` 直接碰 `storage` | `cli/commands/`、`services/` |
| [B-12](#b-12) | P3 | 3 个模块/函数写完从未被调用 | `utils/`、`services/chart_service.py` |

---

<a id="b-01"></a>

## B-01　`asset_meta` 表接入（DAO + 录入 + 展示）

**优先级** P1 · 文档承诺了但功能不存在
**位置** `src/holdings/storage/`（新建 `asset_meta_dao.py`）、`src/holdings/cli/commands/`、`services/`

### 现状

`docs/SCHEMA.md` 定义并详解了 `asset_meta` 表，含 `annual_management_fee`（年化管理费率）字段，
正文写着「完整支持基金托管费」。实际上建表语句之外**全项目零引用**：

```console
$ grep -rn "asset_meta" src/ tests/
src/holdings/storage/db.py:36:    CREATE TABLE IF NOT EXISTS asset_meta (
tests/test_storage.py:26:        断言表存在
```

也就是说，除了建表那一行和一条「表存在」的断言，没有任何代码读写它。
「基金托管费」目前只能靠 `add --fee` 一次性记录，按年计提的管理费完全没有入口。

### ⚠️ 动手前先看这条约束

`docs/SCHEMA.md` 对 `annual_management_fee` 的定义是：

> 年化管理费率（如基金托管费），**用于参考展示，不直接参与单笔成本计算**

**不要**实现「按持仓天数自动计提管理费」。那会让 `list` 的成本价随日历漂移，
与移动加权平均成本法冲突，也与上面这句文档直接矛盾。缺的是下面三样：

### 要做什么

1. **DAO**：`storage/asset_meta_dao.py`，提供 `get` / `upsert` / `delete`，与其余三个 DAO 同构
   （签名收 `db_path`，内部 `connect()` + `try/finally`，异常包成 `DatabaseError`）。
2. **录入入口**：一个 `holdings meta` 子命令（`--symbol` / `--name` / `--currency` / `--fee-rate`），
   或在 `add` 里加可选的 `--name`。倾向前者——别把 `add` 的参数表撑得更长。
3. **展示**：`list` 增一列「名称」，取不到时回落到 symbol；`report` 增加一行费用说明
   （「年化管理费率合计 x%，仅供参考」），措辞必须让用户明白它没被计进成本。

### 完成判据

- `asset_meta_dao` 有覆盖 CRUD 与唯一约束的用例，覆盖率 ≥ 90%。
- 能跑通：`holdings meta --symbol 518880 --name "黄金ETF" --fee-rate 0.5` →
  `holdings list` 显示「黄金ETF」，且**成本价与盈亏数字与录入前完全一致**（证明费率未参与计算）。
- `SCHEMA.md` 与 `USER_GUIDE.md` 补上新命令。

---

<a id="b-02"></a>

## B-02　`metrics` 接入 `report`

**优先级** ✅ 已完成（2026-09-15）
**位置** `src/holdings/services/report_service.py`、`cli/renderers/`

### 完成情况

新增 `services/report_service.py`（`get_performance()`）与
`portfolio/metrics.py` 的 `return_series()` / `periods_per_year()`，
`report` 输出多一行绩效（`cli/renderers/table_renderer.py:render_performance_line`）。

- `sharpe_ratio` 的 `periods_per_year` 改为**必填**，不再默认 252（见上面陷阱 1）：
  原先硬编码 `sqrt(252)`，等于默认所有调用方传的都是日收益。
- 间隔判据为变异系数 ≤ 25%，超过则夏普显示 `—` 并附原因；年化另设 30 天最小跨度。
- `metrics.py` 覆盖率 0% → **100%**（`tests/test_metrics.py` 31 个用例），
  `report_service.py` 100%，全项目 67% → 76%。
- 端到端判据已锁在 `tests/test_report_cmd.py`：100/120/90/110 → `最大回撤 25.00%`。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`portfolio/metrics.py` 完整实现了 `max_drawdown` / `annualized_return` / `sharpe_ratio`，
但没有任何地方 import——只出现在 `portfolio/__init__.py` 的 `__all__` 里。
`VISION.md` 与 `USER_STORIES.md` 承诺的「回撤曲线」「与回撤数据一起导出」因此都没落地。
`chart_service.networth_figure()` 只画 `total_value`，不画回撤。

### ⚠️ 两个口径陷阱

1. **`sharpe_ratio` 硬编码了 `sqrt(252)`**，即假定入参是**日**收益序列。
   但 `snapshots` 是用户随手记的，间隔完全不规律——直接喂进去算出的夏普没有意义。
   接线前必须先按快照间隔折算成统一口径（例如先算每段区间的年化收益再求统计量），
   或者干脆只在「快照间隔足够规律」时才展示，否则显示 `—`。
2. **`annualized_return` 的 `years` 需要真实天数**，从首末快照的 `snapshot_date` 算，
   不要用 `len(snapshots) / 252`。

### 要做什么

- `report_service.summary()` 读全部快照，算最大回撤与年化收益，接进 `report` 的输出。
- 夏普按上面的口径处理：做不到就显示 `—` 并在文档里写清「快照不规律时不计算」，
  **好过给一个错的数**。
- 快照少于 2 条时全部显示 `—`，不要拿单点算出「回撤 0.00%」这种看着像结论的东西。
- `allocator` 已有占比表，可考虑在 `report` 里加一列回撤贡献（可选，非必须）。

### 完成判据

- `metrics.py` 覆盖率从 0% 提到 ≥ 90%，用例覆盖空序列、单点、全涨（回撤 0）、全跌等边界。
- 造一组已知快照（如 100 / 120 / 90 / 110），`holdings report` 显示的最大回撤等于
  手算的 `(120-90)/120 = 25.00%`。
- 快照 < 2 条时输出 `—` 而不是数字。

---

<a id="b-03"></a>

## B-03　`snapshot` 的 `--note` 持久化

**优先级** P2 · 静默丢数据
**位置** `src/holdings/models/snapshot.py`、`src/holdings/storage/snapshot_dao.py`、`storage/db.py`

### 现状

终端回显「已记录快照 #2（月度定投第12期）」，**但这条 note 根本没有入库**：

```console
$ sqlite3 ~/.holdings/holdings.db "PRAGMA table_info(snapshots);"
id | snapshot_date | total_value | cash_balance | equity_value | gold_value | created_at
```

`snapshots` 表没有 `note` 列，`models/snapshot.py` 的 `Snapshot` 没有 `note` 字段，
`snapshot_dao.add` 只插 5 列。用户被告知存下了，实际下次 `list-snapshots` 看不到任何备注。
`USER_GUIDE.md` 的例子也跑不通（`--total` 是 `required=True`，照抄会报 Missing option）。

### 要做什么

1. `db.py` 的 `CREATE TABLE snapshots` 加 `note TEXT`。
2. `Snapshot` 模型与 `snapshot_dao.add` 补该列。
3. **迁移**：已存在的数据库需要 `ALTER TABLE snapshots ADD COLUMN note TEXT`。
   `db.py` 目前的建表用 `IF NOT EXISTS`，对老库不会生效——需要一段显式的
   `PRAGMA table_info` 探测 + 补列的迁移逻辑，这是本项真正的工作量所在。
4. 快照列表命令展示 note；`USER_GUIDE.md` 的示例补上 `--total`。

### 完成判据

- 新建库与已有旧库（用当前代码造一个）都能正常写入并读回 note。
- 用例覆盖：写 note → 读回一致；不传 `--note` → 存 `NULL` 而非空串。
- 迁移用例：手工建一张不含 `note` 的 `snapshots` 表，调 `connect()` 后 `PRAGMA` 能看到该列。

---

<a id="b-04"></a>

## B-04　`chart --start` 生效

**优先级** P2 · 参数是摆设
**位置** `src/holdings/cli/commands/chart.py`、`src/holdings/services/chart_service.py`

### 现状

`--start` 的 help 原文就写着「暂存参数」，`networth_figure()` 也没有对应形参，
传了完全不生效。`USER_GUIDE.md:123` 却拿它当日期筛选的示例。

顺带：四份文档都提到的「配置占比柱状图」实际输出是 Rich 两列表格，全项目 grep `Bar` 零命中。
这一条已在 `1a3405e` 把文档改成「表格」，**不是本项的工作**。

### 要做什么

- 二选一，别维持现状：
  - **接线**：`networth_figure(db_path, start=None)`，在取快照时按 `snapshot_date >= start` 过滤；
    `--start` 加 `click.DateTime` 或复用 `add` 里已有的日期校验回调，非法日期给退出码 5。
  - **删掉**：连同 `USER_GUIDE.md` 的示例一起移除。参数存在但无效比没有更糟。
- 倾向接线——按时间段看净值曲线是真实需求，实现成本也低。

### 完成判据

- `holdings chart --start 2025-01-01 --output out.html` 生成的图只含该日期之后的点；
  用 `--start 2030-01-01`（未来）时给出明确提示而非空白图。
- `--start 2025-13-45` 退出码 5，输出 `错误（5）：…`，无 traceback。

---

<a id="b-05"></a>

## B-05　四个死配置项与网络超时

**优先级** P2 · 配置项骗人
**位置** `src/holdings/utils/config.py`、`src/holdings/data/a_stock.py`、`us_stock.py`、`gold.py`

### 现状

`docs/CONFIG_SPEC.md` 原本把每个配置项都写成了生效的行为，`FAQ.md` 甚至指导用户
「调整 `sync.retry_count`」。实际只有 `database_path` 与 `cache_ttl_seconds` 被真正读取，
以下四项**改了不起任何作用**：

| 配置项 | 默认值 | 现状 |
|--------|--------|------|
| `default_market` | `A股` | 无引用 |
| `data_sources.priority` | `[akshare, yfinance]` | 无引用，降级顺序硬编码在 `a_stock.py` |
| `sync.timeout_seconds` | `10` | 无引用，**网络调用根本没有超时** |
| `sync.retry_count` | `1` | 无引用，`a_stock.py` 里硬编码 `for _ in range(2)` |

其中**网络无超时是真问题**：`akshare` / `yfinance` 卡住时 `holdings sync` 会无限期挂起，
用户只能 Ctrl-C。`CONFIG_SPEC.md` 已在 `1a3405e` 加了「⚠️ 尚未生效」标注，
标注只是止血，不是修复。

### 要做什么

1. **超时优先**。给三个 fetcher 的网络调用加超时。`yfinance` 走 `requests`，
   可用 `yf.Ticker(...)` 前设置 `requests` 的默认超时或用 `history(timeout=...)`；
   `akshare` 没有超时参数，需在 `fetcher` 层用 `concurrent.futures` 包一层
   （`ThreadPoolExecutor` + `future.result(timeout=...)`）——线程无法真正中断，
   但至少能让 CLI 及时返回并报 `DataSourceUnavailableError`。
2. 把 `retry_count` 接进 `_with_fallback` 的循环次数（默认 1 次重试 = 循环 2 次，与现状一致）。
3. `default_market` 接到 `sync` / `list` 的 `--market` 默认值上。
4. `data_sources.priority` 接进 `fetcher.get_fetcher`：按配置顺序依次尝试。
   这一项改动面最大，**可以单独拆一次提交**；若判断收益不足，就在 `CONFIG_SPEC.md` 里
   把它标成「预留，未实现」并同步删掉 FAQ 里的相关说法——但**不要留着一个假装生效的配置项**。

### 完成判据

- 把 `sync.timeout_seconds` 改成 `1`，对一个已知不可达的源执行 `sync`，
  命令在 ~1 秒内返回并给出退出码 1，而不是挂住。
- 把 `retry_count` 改成 `0` / `3`，用 monkeypatch 计数 fetcher 被调用的次数，
  断言与配置一致。
- `CONFIG_SPEC.md` 里不再有任何 ⚠️ 标注（要么生效，要么明确写「预留」）。

---

<a id="b-06"></a>

## B-06　无行情时的「现价 0 / −100%」误导

**优先级** P2 · 误导
**位置** `src/holdings/services/portfolio_service.py:50`、`cli/renderers/`

### 现状

```python
cached = price_cache_dao.get(db_path, symbol)
current_price = cached.price if cached else 0.0
```

从未 `sync` 就执行 `list` / `report` 时，`current_price` 取 0，盈亏率算成 `−100.00%`。
**用户看到的是「血亏 100%」，实际只是没有数据**，且表格里没有任何「未同步」标注。

### 要做什么

- `current_price` 缺省从 `0.0` 改为 `None`（`holding_for` 的形参同步放宽），
  渲染层据此显示 `—`，盈亏与盈亏率同样显示 `—`，并在表尾加一行提示
  「N 个标的无行情，请先执行 `holdings sync`」。
- 排序时把无行情的标的排在末尾（`na_position="last"`），别让它们污染 `--sort 盈亏率` 的结果。
- 汇总口径：无行情标的的市值不计入总市值（现状是计 0，结果相同但语义更清楚），
  并在输出里说明「已排除 N 个无行情标的」。
- 注意 `--sort 数量` 之类不依赖价格的排序仍须正常工作——无行情的标的仍应出现在表里。

### 完成判据

- 清空 `price_cache` 后 `holdings list`：盈亏列显示 `—`，不出现 `-100.00%`，有提示行。
- `sync` 成功后同样的命令恢复正常数字。
- 用例覆盖「部分标的有行情、部分没有」的混合场景，断言无行情那些显示 `—`。

---

<a id="b-07"></a>

## B-07　窄终端下持仓表截断到无法辨认

**优先级** P2 · 可用性
**位置** `src/holdings/cli/renderers/`

### 现状

2026-09-15 复核排序修复时实测发现，不在最初的审计清单里。持仓表共 10 列，
总宽超出默认 80 列后 Rich 对每列平均截断：

```
│ 6005… │ A股 │ stock │ 100.… │ 1680… │ 1750… │ 178,… │ 5.00… │ 6,94… │ 4.13% │
```

**代码列只剩 4 个字符，用户无法从表里认出自己持的是哪只标的。** 这是默认终端宽度下的默认行为，
不是边缘情况。

### 要做什么

- 标识列（代码、市场、类型）设 `no_wrap=True` 与合理的 `min_width`，让 Rich 优先牺牲数字列。
- 数字列可以用更紧凑的格式（`178,4…` 这种截断没有信息量，不如缩短小数位或省略千分位）。
- 更彻底的方案是按终端宽度分「简表 / 详表」两档：窄终端只显示
  代码 / 数量 / 现价 / 盈亏率 四列，宽终端显示全部。**倾向这一档方案**——
  10 列本来也不是窄终端能承载的信息量。
- `rich.console.Console()` 目前未指定宽度，可用 `Console(width=...)` 或读取
  `console.size.width` 来判断档位；测试里通过 `Console(width=80, force_terminal=True)` 固定。

### 完成判据

- 在 80 列下运行 `holdings list`，**代码列完整可见**（`600519` 而不是 `6005…`）。
- 用例：用固定宽度的 `Console` 渲染，断言输出中包含完整 symbol，且行宽不超过终端宽度。
- 宽终端（≥ 120 列）下列数与现状一致，不多不少。

---

<a id="b-08"></a>

## B-08　报错格式与退出码统一

**优先级** P2 · 契约不一致
**位置** `src/holdings/cli/commands/remove.py`、`check.py`、`cli/main.py`

### 现状

三处偏离 `docs/ERROR_HANDLING.md` 的契约：

1. **`remove` 不走统一前缀**。未找到交易时输出裸文本「未找到交易 #3」后 `SystemExit(2)`。
   退出码 2 本身是对的（「数据不存在」），错的是格式——
   文档要求 `错误（2）：未找到交易 #3`，且必须经 `main()` 的映射层而非命令内直接 `SystemExit`。
2. **`check` 同样不走统一前缀**。缺必需依赖时输出 Rich 的红色文本后 `SystemExit(1)`。
3. **`check --json` 缺依赖时仍 exit 0**。`as_json` 分支在 `missing_required()` 检查**之前**
   就 `return` 了，靠退出码判断的 CI 脚本会漏检——这是三项里唯一会真正咬人的。

> ⚠️ 体检报告当初还写了「`check` 的退出码 1 与文档定义的『网络错误』冲突」，
> **这条已经不成立了**：`1a3405e` 把 `ERROR_HANDLING.md` 的退出码 1 改成
> 「网络错误 / 数据源不可用 / 缺少可选依赖」，冲突是**改文档绕过去的**，不是修掉的。
> 所以剩下的问题是格式与退出码一致性，不是「文档与代码对不上」。

### 要做什么

- `remove` 的「未找到」改抛 `SymbolNotFoundError`（或新建 `RecordNotFoundError`），
  由 `main()` 统一映射为 `错误（2）：…`。退出码不变。
- `check` 缺依赖改抛 `MissingDependencyError`（该异常已在 `fe251e8` 引入并映射到退出码 1），
  让提示走统一前缀。**顺带做一个决定**：退出码 1 现在同时表示「网络问题」和「依赖缺失」
  两类完全不同的故障（前者重试有意义，后者没有）。要么承认 1 就是「外部依赖问题」这个大类、
  在文档里明确写成一个类别；要么给「依赖缺失」拆一个专属码（建议 6）。
  **倾向拆分**——CI 里「装包」和「重试网络」是两种完全不同的处置。
- `check --json` 的输出与退出码解耦：先收集结果，输出 JSON 之后再依据 `missing_required()`
  决定退出码。JSON 里也应带上一个可用于判断的字段（如 `"ok": false`）。
- 统一走异常 + `main()` 映射，命令体里不再出现 `SystemExit`
  （`init.py` 等引导命令若确有必要，在 `ARCHITECTURE.md` 里记为例外）。

### 完成判据

- `holdings remove --id 99999` 输出 `错误（2）：…`，退出码 2。
- `holdings check` 在缺依赖时输出 `错误（N）：…`（N 按上面的决定取 1 或 6），
  `holdings check --json` 退出码与文本模式**一致**，且 JSON 里带可判断的字段。
- `tests/test_cli_errors.py` 的退出码参数化表覆盖最终选定的退出码；
  该文件必须走 `main()` 而非 `CliRunner`（见 `TESTING_STRATEGY.md`）。
- `ERROR_HANDLING.md`、`USER_GUIDE.md`、`README.md` 三处退出码表同步更新。

---

<a id="b-09"></a>

## B-09　`utils/` 层测试缺口

**优先级** P3
**位置** `tests/`

### 现状

`utils/config.py` 已在近期补到 90%（deep merge、YAML 错误、缺失文件），但同层仍有空白：

| 文件 | 覆盖率 | 说明 |
|------|--------|------|
| `utils/deps.py` | 0% | `is_installed` / `check_dependencies` / `missing_required` 三个纯函数，`check` 命令直接依赖 |
| `utils/formatter.py` | 0% | **零调用，属死代码**，见 B-12 |
| `utils/currency.py` | 0% | **零调用，属死代码**，见 B-12 |

### 要做什么

- 补 `deps.py` 的用例：`is_installed("一定不存在的包")` 为 `False`；
  `missing_required()` 在 monkeypatch 掉某个必需包后返回其名；`check_dependencies()` 的返回结构
  与 `PackageStatus` 字段完整。
- `formatter.py` / `currency.py` **不补测试，去 B-12 处理**——给死代码写测试是双重浪费。
- `cli/renderers/` 当前 15%~0%，渲染层的测试适合和 B-06 / B-07 一起补：
  固定 `Console(width=..., force_terminal=True)` 后断言输出内容。

### 完成判据

- `utils/deps.py` 覆盖率 ≥ 90%。
- 全项目行覆盖率从 67% 提升，且 `TESTING_STRATEGY.md` 的覆盖率表同步更新到真实数字。

---

<a id="b-10"></a>

## B-10　`data/` 层降级路径测试

**优先级** P3
**位置** `tests/test_data.py`

### 现状

三个 fetcher 覆盖率 18%~29%，且降级路径——也就是这一层最复杂的逻辑——完全没有测试：

- `AStockFetcher._with_fallback`：akshare 抛错 → 重试 → 降级 yfinance → 再失败才抛
  `DataSourceUnavailableError`。这条链路的每一环都没被验证过。
- `_from_yfinance` 的代码后缀推导（`6` 开头 → `.SS`，否则 `.SZ`）无测试。
- 懒加载的分支：未装 `akshare` 时应抛 `DataSourceUnavailableError("未安装 akshare")`，
  而不是 `ImportError`。
- `fetcher.get_fetcher` 对未知市场抛 `SymbolNotFoundError`。

这些都能用 monkeypatch 测，不需要真实网络——`test_data.py` 现有用例已经用了这个手法，
直接沿用即可（`responses` 库已在 `fe251e8` 从 `dev` 依赖中移除）。

### 要做什么

- 用 monkeypatch 伪造 `akshare` / `yfinance` 模块，覆盖上面四条链路。
- 重试次数与 `time.sleep(0.5)` 要一起打桩，否则用例会真的睡 0.5 秒——
  给 `time.sleep` 打 no-op，同时断言它被调用的次数。
- B-05 接线 `retry_count` 后，这些用例正好用来锁住新行为。

### 完成判据

- `data/` 层覆盖率 ≥ 80%，三个 fetcher 都不低于该值。
- 用例断言「akshare 失败一次后成功」时**不会**调用 yfinance；
  「akshare 始终失败」时才降级，且最终失败时抛的是 `DataSourceUnavailableError` 而非原始异常。
- 整个 `tests/` 跑完不加 sleep 时间（打桩生效）。

---

<a id="b-11"></a>

## B-11　铁律 3 的三处违反

**优先级** P3 · 架构
**位置** `src/holdings/cli/commands/snapshot.py`、`remove.py`、`init.py`

### 现状

`docs/ARCHITECTURE.md` 的铁律 3 是「`cli` 不直接触碰 `storage` / `data` / `portfolio`，只经 `services`」。
当前执行情况表已如实标注 3 处违反：

| 命令 | 违反方式 |
|------|---------|
| `snapshot` | 直接 `from holdings.storage import snapshot_dao` |
| `remove` | 直接 `from holdings.storage import transaction_dao` |
| `init` | 直接 `from holdings.storage import db`（**可接受的引导例外**，见下） |

`init` 是例外：初始化时数据库还不存在，让它走 `services` 是纯粹的形式主义。
建议在 `ARCHITECTURE.md` 里把它写成明确的豁免条款，而不是继续挂在「违反」里。

### 要做什么

- 新建 `services/snapshot_service.py`，把 `snapshot_dao` 的调用收进去；
  `cli/commands/snapshot.py` 改为只调 service。
- `remove` 的交易删除接进已有的 `trade_service`（其中已有写入闸门与校验逻辑，
  直接删 DAO 也绕过了这层保护）。
- `ARCHITECTURE.md` 的执行情况表同步更新，`init` 移入豁免说明。
- **这是唯一需要先对齐再动手的一项**：如果判断「为了 2 个命令多建 2 个 service 层不划算」，
  那就改铁律本身——把「简单 CRUD 命令可直接调 DAO」写成正式条款。
  两条路都行，**但不要让规则和代码长期各说各的**。

### 完成判据

- `grep -rn "holdings.storage" src/holdings/cli/` 只剩 `init.py` 一处，且文档已写明它是豁免。
- 既有测试全绿（`remove` / `snapshot` 的行为不变，只换了调用路径）。
- `ARCHITECTURE.md` 的执行情况表与代码一致，不再有 ⚠️。

---

<a id="b-12"></a>

## B-12　零引用的死代码

**优先级** P3
**位置** `src/holdings/utils/formatter.py`、`utils/currency.py`、`services/chart_service.py`

### 现状

体检后又 grep 到三处「写完了但从未被调用」，与 `metrics.py`（见 B-02）同一类：

```console
$ grep -rn "format_money\|format_percent\|format_quantity" src/ tests/
src/holdings/utils/formatter.py:4:def format_money(...)     # 仅定义处
（无任何调用）

$ grep -rn "networth_json" src/ tests/
src/holdings/services/chart_service.py:32:def networth_json(db_path: str) -> str:   # 仅定义处
（无任何调用）

$ grep -rn "currency.convert" src/ tests/
（无任何命中）
```

`formatter` 的三个函数只在 `utils/__init__.py` 的 `__all__` 里被提及，
`currency.convert` 零调用，`networth_json` 零调用。

### 要做什么

逐个决定**接上还是删掉**，不要留着：

- `formatter.py`：`list` / `report` 里的金额格式化目前散在渲染层各写各的。
  把它接上能统一格式（尤其是 B-06 / B-07 改渲染时会重写这些代码，正是接入的时机）。
  **建议接上**，否则删。
- `currency.py`：汇率换算属于 v2.0.0 的多币种需求，当前 `PriceResult` 已有 `currency` 字段但
  无人消费。**建议保留并在文件头注明「预留，v2.0.0 使用」**，
  或者删掉、等真要用时再从 git 历史里取——倾向后者，注释挡不住它继续腐烂。
- `networth_json()`：返回 JSON 字符串供前端用，属于 web 版本的预留。
  `chart` 命令已有 `networth_figure` + `write_html`。**建议删掉**——
  真做 web 时需要的 JSON 结构跟现在这个多半不一样。

### 完成判据

- 三个文件/函数各有明确结论（接上 or 删除），且**没有第四个零引用模块**——
  处理完顺手跑一遍全项目 grep，确认 `__all__` 里的每个名字都有真实调用点。
- 若删除，`utils/__init__.py` 的 `__all__` 同步清理；
  `ARCHITECTURE.md` 的目录树同步删除对应行。
- 若接上，配套测试一并补（这会同时改善 B-09 的覆盖率数字）。

---

## 建议的执行顺序

按「依赖关系 + 风险」排，不建议打乱前两步：

1. **B-02 + B-09（部分）** —— 纯计算层，改动隔离，一次提交能同时消掉一个 P1 和一片覆盖率空白。
2. **B-05 的超时部分** —— 网络无超时是会挂死进程的真缺陷，优先于其余 P2。
3. **B-03 → B-06 → B-07** —— 都动到快照 / 渲染，按此顺序做可以一次把渲染层的测试补齐。
4. **B-08 → B-04 → B-05（其余配置项）** —— 契约与参数层面的收尾。
5. **B-01** —— 唯一需要新命令 + 新 DAO 的功能项，放最后，因为它不影响现有行为。
6. **B-11 + B-12** —— 纯重构与清理，任何时候都可做，适合穿插在等 CI 的时候。

每完成一项：更新本文件的勾选状态、同步受影响的文档、在 `CHANGELOG.md` 记一笔、提交并推 CI。

**一项改动一个提交**——一个条目至少一个提交，条目内部互不依赖的部分再拆。
提交信息带上条目编号（如 `fix: 给网络调用加超时 (B-05)`）。这条是硬性要求，
理由与细则见 [编码与提交规范](CODING_STANDARDS.md#提交粒度一项改动一个提交硬性要求)。

---

## 相关文档

- [架构与模块隔离规范](ARCHITECTURE.md) —— 铁律与当前执行情况
- [数据库设计说明](SCHEMA.md) —— `asset_meta` 与 `snapshots` 的字段定义
- [配置项字典](CONFIG_SPEC.md) —— 标注了哪些配置项尚未生效
- [错误码与异常处理规范](ERROR_HANDLING.md) —— 退出码契约
- [测试策略](TESTING_STRATEGY.md) —— 覆盖率目标与现状
- [详细开发路线图](ROADMAP.md) —— 里程碑划分
