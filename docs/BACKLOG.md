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
| [B-01](#b-01) | ✅ 已完成 | `asset_meta` 表零 DAO，年化管理费率无处可填 | `storage/`、`cli/` |
| [B-02](#b-02) | ✅ 已完成 | `metrics.py` 三个纯函数从未被调用 | `services/report_service.py` |
| [B-03](#b-03) | ✅ 已完成 | `--note` 回显但不入库，静默丢数据 | `models/snapshot.py`、`storage/snapshot_dao.py` |
| [B-04](#b-04) | ✅ 已完成 | `--start` 是空参数，传了不生效 | `cli/commands/chart.py`、`services/chart_service.py` |
| [B-05](#b-05) | ✅ 已完成 | 4 个配置项改了不起作用；网络调用无超时 | `utils/config.py`、`data/` |
| [B-06](#b-06) | ✅ 已完成 | 未同步时显示「−100%」，看起来像血亏 | `services/portfolio_service.py`、`cli/renderers/` |
| [B-07](#b-07) | ✅ 已完成 | 80 列终端下代码列只剩 `6005…` | `cli/renderers/` |
| [B-08](#b-08) | ✅ 已完成 | `remove` / `check` 不走统一前缀；`check --json` 漏报退出码 | `cli/commands/remove.py`、`check.py` |
| [B-09](#b-09) | ✅ 已完成 | `deps.py` 零测试 | `tests/` |
| [B-10](#b-10) | P3 | 三个 fetcher 覆盖率 18%~29%，降级路径无测试 | `tests/test_data.py` |
| [B-11](#b-11) | ✅ 已完成 | `cli` 越过 `services` 直接碰 `storage` | `cli/commands/`、`services/` |
| [B-12](#b-12) | ✅ 已完成 | 3 个模块/函数写完从未被调用 | `utils/`、`services/chart_service.py` |
| [B-14](#b-14) | ✅ 已完成 | `config.yaml` 的字段取值没有校验 | `utils/config.py` |
| [B-15](#b-15) | P3 | UI 层（v2.0.0）——前置条件已具备 | 新增 `ui/` 或 `tui/` |

---

<a id="b-01"></a>

## B-01　`asset_meta` 表接入（DAO + 录入 + 展示）

**优先级** ✅ 已完成（2026-09-16）
**位置** `storage/asset_meta_dao.py`、`cli/commands/meta.py`、`services/asset_meta_service.py`

### 完成情况

三次提交，对应条目列的三样：

1. **DAO**：`models/asset_meta.py` + `storage/asset_meta_dao.py`
   （`get` / `get_all` / `upsert` / `delete`，与其余三个 DAO 同构）。
   `upsert` 用 `ON CONFLICT DO UPDATE`——`symbol` 是主键，一条语句表达
   「有则更新、无则插入」，也省掉两次查询之间的竞态。
2. **录入入口**：采纳条目倾向的「新命令」方案，`holdings meta`
   （`--symbol` / `--name` / `--currency` / `--fee-rate` / `--remove`）。
   没有往 `add` 上加 `--name`——那些参数与「记一笔交易」无关。
3. **展示**：`holdings list` 增「名称」列（取不到回落代码）；
   `holdings report` 在记过费率时印一行「年化管理费率合计 x%（仅供参考，未计入成本）」。

**遵守了条目开头那条约束**：`annual_management_fee` 只作参考展示，
**没有**实现「按持仓天数自动计提管理费」。这条约束放在最容易被顺手违反的地方——
`AssetMeta` 的 docstring、`SCHEMA.md` 的字段说明、命令的输出与 `USER_GUIDE`，
四处都写了；并用一条用例锁住。

**几处行为判断**

- `holdings meta --symbol X` 一个字段都不给时是**查看**，不是写一条空记录——
  顺手 upsert 一条全空的记录会静默清掉已有的名称与费率。
- 覆盖时**没给的字段保留原值**：只想改名称不该把费率一起抹掉。
- 删除用 `--remove` 走同一条命令：DAO 的 `delete` 需要一个真实调用方，
  否则就是 [B-12](#b-12) 说的「写完从未被调用」的死代码。

**完成判据**

- ✅ `asset_meta_dao` 覆盖率 **100%**（要求 ≥ 90%）——除 CRUD 与主键唯一性外，
  另有一组参数化用例注入会抛 sqlite3 异常的连接，覆盖四个 `except` 分支：
  这些分支漏出去会绕过 `main()` 的退出码映射（`sqlite3.Error` 不是 `HoldingsError`），
  用户看到的是裸 traceback 而不是「错误（4）：…」。
- ✅ `holdings meta --symbol 518880 --name "黄金ETF" --fee-rate 0.5` →
  `holdings list` 显示「黄金ETF」，且**成本价与盈亏数字与录入前逐项相等** ——
  `tests/test_meta_cmd.py::test_the_rate_changes_nothing_about_the_numbers`。
- ✅ `SCHEMA.md` 补上字段表与该约束；`USER_GUIDE.md` 补上第 4 节
  （后续小节顺延编号）。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-15）
**位置** `src/holdings/models/snapshot.py`、`src/holdings/storage/snapshot_dao.py`、`storage/db.py`

### 完成情况

两次提交：

1. **落库与迁移**：建表语句、`Snapshot` 模型、`snapshot_dao.add` 补上 `note`；
   `snapshot` 命令把 `--note` 传进模型（此前只拿去拼了一句回显）。
   **本项真正的工作量在迁移**——`note` 是后加的列，而 `CREATE TABLE IF NOT EXISTS`
   对已存在的表完全不生效，老库不会自己长出来。`db.py` 新增 `_migrate()`，
   用 `PRAGMA table_info` 探测后 `ALTER TABLE` 补列；判定「列在不在」而不是查
   版本号（这个库由用户直接拿着用，不会有谁维护 schema_version，而列的存不
   存在是自证的，也就不会出现版本号与事实不符）。
2. **让备注可见**：新增 `holdings snapshots` 命令与 `services/snapshot_service.py`。

**条目原文的一处出入**：它写「下次 `list-snapshots` 看不到任何备注」，
但项目里**从来没有 `list-snapshots` 这个命令**（与 B-05 把 `list --market`
写进去是同一类笔误）。所以「展示」这一步不是接线，而是要新加一条命令——
不做的话，备注写得进去、读不出来，只是把「静默丢数据」换成了「静默存数据」。

**顺带收口铁律 3 的一处违反**：新增的 `snapshot_service` 同时接管了
`snapshot` 命令对 `snapshot_dao` 的直接调用。再让新命令直接调 DAO，
等于把违反从一处变成两处。[B-11](#b-11) 因此只剩 `remove` 与 `init`。

**完成判据**

- ✅ 新建库与旧库都能写入并读回 note —— `tests/test_storage.py` 的迁移用例
  手工建了一张不含 `note` 的旧表并塞入数据，`connect()` 后确认列已补上、
  旧数据未被动到、迁移后的库能正常写入与读回。
- ✅ 写 note → 读回一致；不传 `--note` → 存 `NULL` 而非空串
  （直接查库确认是 `NULL`）—— `tests/test_snapshot_cmd.py` 与 `test_storage.py`。
- ✅ `SCHEMA.md` 补上该列与迁移策略；`USER_GUIDE.md` 补上新命令，
  并把 `--note` 的说明从「仅回显，不写入数据库」改正。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-16）
**位置** `src/holdings/cli/commands/chart.py`、`services/chart_service.py`、`cli/dates.py`

### 完成情况

按条目倾向的「接线」方案做的：

- `networth_series(db_path, start=None)` 只保留该日（含）**之后**的快照。
  含当天：不含的话，用户按自己记得的那个日期筛会莫名少一条。
- `--start` 走与 `--date` 同一套校验回调，非法日期退出码 5。回调收进新增的
  `cli/dates.py` 共用——此前只有 `add` 里有一份，`chart` 干脆没校验。
- **筛完一条不剩时抛 `RecordNotFoundError`（退出码 2），不生成空白图**：
  空图与「净值跌没了」在图上是分不出来的。提示里带上现有的条数与首末日期，
  用户才知道该把 `--start` 调到哪里；一条快照都没有时直接提示先执行
  `holdings snapshot`。

**一处结构调整**：取数从 `networth_figure` 里拆成独立的 `networth_series`。
它不依赖 plotly，于是「这段时间没有数据」在没装画图库时也能先报出来——
而且 CI 只装 `.[dev]`（不含 plotly），判据要能在 CI 里跑，这一步拆分是前提。
相应地 `networth_figure` 改为**先取数据、再导入 plotly**：数据为空是用户当场
能处理的事，比「去装个包」更该先说。既有的那条 plotly 用例因此要先塞一条快照
才走得到导入那步。

**完成判据**

- ✅ `--start` 只含该日期之后的点 ——
  `tests/test_chart_cmd.py::test_start_keeps_only_the_snapshots_on_or_after_it`。
- ✅ 未来日期给出明确提示而非空白图（且不写出 HTML 文件）——
  `test_a_future_start_is_an_error_not_an_empty_chart` 与
  `test_future_start_exits_2_without_writing_a_file`。
- ✅ `--start 2025-13-45` 退出码 5、输出 `错误（5）：…`、无 traceback ——
  `test_malformed_start_exits_5_without_a_traceback`。
- ✅ 另有一条用例守着 help 文案里不再出现「暂存参数」。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-15）
**位置** `src/holdings/utils/config.py`、`src/holdings/data/`

### 完成情况

四项分三次提交，每一项独立可回滚：

1. **超时**（`d717f1b`）：新增 `data/resilience.call_with_timeout`，把取价放进
   **守护线程**并按 `sync.timeout_seconds` 放弃等待。粒度是**每个标的**而不是
   每次请求——用户关心的是「一个标的最多等多久」，这个口径也让下面的判据成立。
   用 `ThreadPoolExecutor` 试过：`with` 块退出时 `shutdown(wait=True)` 把省下的
   时间又等回去，显式 `wait=False` 也仍会被 atexit 的 join 拦住，超时形同虚设。
   代价是被放弃的请求仍在后台跑完，这一点在 docstring 与 CONFIG_SPEC 里如实写明，
   没有假装超时能中断请求。
2. **`sync.retry_count`**（`7d633ce`）：改为读配置，默认 1 次重试 = 共 2 次尝试，
   与改动前行为一致。顺带修掉退避的位置——原先 `sleep` 写在 `except` 末尾，
   最后一次失败后还要白等 0.5 秒才降级。
3. **`default_market`**（`b2ccd69`）：接到 `sync --market` 的默认值上。
   条目原文写的是「接到 `sync` / `list` 的 `--market`」，但 `list` 根本没有
   `--market` 选项；CONFIG_SPEC 自己的描述就是「当前 `sync` 的默认值是硬编码的
   『全部』」。按后者理解，只接 `sync`。
4. **`data_sources.priority`**：新增 `data/sources.py`，顺序由配置决定，
   重试与降级三市场共用一份。

**动手时发现并单独修掉的缺陷**（`1a8beb9`）：`load_config()` 用浅拷贝复制默认配置，
`_deep_merge` 会就地改到模块级的 `DEFAULT_CONFIG` 上——「加载过一份配置」这件事
本身改变了此后所有加载得到的默认值。是做第 4 项时被「配置写空列表应回落到内置
顺序」的用例抓出来的：回落取到的正是被上一次加载改写过的值。

**冲突与取舍**：黄金的两个源（国内现货/ETF 与 `GC=F`）曾被按优先级做成可互相
回退的两个源。这会**写坏数据**：`sync` 按请求的代码入库（不看 `PriceResult.symbol`），
518880 在 akshare 失败时会拿到 GC=F 的价格（美元/盎司）并以 518880 的名义缓存。
改为由代码选路，黄金不参与 `priority`，默认配置里移除 `黄金:` 一项
（老配置里留着的会被忽略）。`tests/test_data.py` 对这条有专门断言。

**完成判据**

- ✅ `timeout_seconds` 改成 1 后，对不响应的源执行 `sync` 在 ~1 秒内返回并给出
  退出码 1 —— `tests/test_resilience.py::test_sync_command_returns_instead_of_hanging`。
- ✅ `retry_count` 改成 0 / 3 时 fetcher 的调用次数与配置一致 ——
  `tests/test_data.py::test_retry_count_controls_how_many_times_akshare_is_tried`。
- ✅ `CONFIG_SPEC.md` 里四个配置项的 ⚠️ 标注全部消除。**另有一处与这四项无关的
  ⚠️（字段取值未校验）仍在**，那是个独立问题，已记为 [B-14](#b-14)。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-15）
**位置** `src/holdings/services/portfolio_service.py`、`portfolio/calculator.py`、`cli/renderers/`

### 完成情况

一次提交，从计算层一路改到渲染层：

- `calculator.Holding` 的 `current_price` / `market_value` / `profit` / `profit_rate`
  放宽为 `float | None`；`holding_for(pos, None)` 返回的市值与盈亏都是 `None`。
  零成本持仓的收益率同样从 `0.0` 改为 `None`——`0.00%` 看着像「不赚不亏」这个
  结论，而事实是这个比值没有定义。
- `portfolio_service` 不再用 `0.0` 兜底缺价，并把汇总口径收敛为**有行情的标的**，
  同时报出 `unpriced_symbols` / `unpriced_cost` 供提示行使用。
- 渲染层：表格里空值显示 `—`；新增 `render_summary_line` / `render_unpriced_hint`，
  `list` 与 `report` 共用（此前那段汇总行是两处复制粘贴，改一处忘一处的风险是实的）。
- 排序 `na_position="last"`。

**一处口径判断**（条目只说了「市值不计入总市值」）：盈亏率的分母同样只算有行情的
成本。分子里的盈亏只含有行情的标的，分母若含全部成本，会算出一个既不是「全体」
也不是「部分」的数。相应地**总成本也改为只算有行情的部分**——否则「总市值 0 /
总成本 1000」看起来像巨亏，与这一项要修的毛病是同一类。没计入的部分由提示行
如实说明数量与成本合计。

**完成判据**

- ✅ 清空 `price_cache` 后 `holdings list` 盈亏列显示 `—`、不出现 `-100.00%`、
  有提示行 —— `tests/test_unpriced.py::test_list_shows_dashes_and_a_hint_instead_of_a_fake_loss`。
- ✅ `sync` 成功后同样的命令恢复正常数字 —— `test_list_recovers_after_sync`。
- ✅ 混合场景（部分有行情、部分没有）断言无行情那些显示 `—` ——
  `test_unpriced_holding_carries_no_numbers` 与 `test_totals_only_cover_the_priced_positions`。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-15）
**位置** `src/holdings/cli/renderers/`

### 完成情况

采纳了条目里倾向的**按宽度分档**方案：

- `render_holdings_table(df, width=None)`：窄于 `COMPACT_WIDTH_THRESHOLD`（100 列）
  只渲染 `COMPACT_COLUMNS` 四列（代码 / 数量 / 现价 / 盈亏率）；宽终端仍是十列，
  与改动前一致。`width=None` 保持全表，既有的调用方与测试不必关心终端宽度。
- 标识列（代码 / 市场 / 类型）设 `no_wrap` 与 `min_width`，让 Rich 优先牺牲数字列。
- `list` / `report` 把 `console.width` 传给渲染层——渲染层不自己造 Console，
  否则测试与真实终端会看到两个不同的宽度来源。

**顺带收掉一处重复**：渲染层的 `columns` 字典与 `list` 的 `_SORT_ALIASES` 此前
各写一份同样的列清单，靠 `test_every_displayed_column_is_sortable` 盯着才没走样。
现改为渲染层导出 `HOLDINGS_COLUMNS`，排序别名从它派生。

**完成判据**

- ✅ 80 列下代码列完整可见（`600519` 而不是 `6005…`），且整表不出现省略号 ——
  `tests/test_narrow_terminal.py::test_symbol_is_fully_visible_at_80_columns`。
- ✅ 行宽不超过终端宽度 —— `test_no_line_exceeds_the_terminal_width`。
- ✅ 宽终端下列数与改动前一致 —— `test_wide_terminal_still_shows_every_column`
  直接断言表头列表等于 `HOLDINGS_COLUMNS` 的全部值。
- ✅ 用例用固定宽度的 `Console` 渲染（`Console(width=…)` + `export_text()`）。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-15）
**位置** `src/holdings/cli/commands/`、`cli/main.py`、`exceptions.py`

### 完成情况

两次提交：

1. **「缺少依赖」拆出退出码 6**（采纳条目里「倾向拆分」的建议）。1 此后只表示
   「网络 / 数据源不可用」。理由：两者的处置相反——缺依赖重试没有用、要装包，
   网络故障才值得重试；并到同一个码会让 CI 里「网络抖了一下」和「环境没装好」
   看起来是同一种故障，而它们的修法一个是重跑、一个是改 Dockerfile。
2. **统一报错格式**：`remove` / `sync` / `check` 三处不再自己 `SystemExit`，
   全部抛异常交 `main()` 映射。`check --json` 的退出码与文本模式由同一个出口
   决定，不可能再不一致；JSON 改为对象并带上 `"ok"` 字段。

**顺带**：映射表从 `main()` 的函数体提到模块级的 `exit_code_for()`。此前它藏在
函数里，用例只能断言「返回值落在 1~5 之间」——一个漏掉的分支不会被任何用例发现，
而这张表本身就是契约。新增一条结构性用例用 AST 扫描命令目录，防止后来者再绕过
映射层（用 AST 而不是文本匹配：注释里提到 `SystemExit` 是正常的，要解释为什么
不再用它）。

**一处判断**：条目说「`init.py` 等引导命令若确有必要，在 `ARCHITECTURE.md` 里
记为例外」。实际核对下来 `init.py` 并没有用到 `SystemExit`，命令目录里一处也
没有，因此**不需要例外**——`ERROR_HANDLING.md` 的原则写成「唯一的例外是
`main()` 自身，它正是那个映射层」。

**完成判据**

- ✅ `holdings remove --id 99999` 输出 `错误（2）：未找到交易 #99999`，退出码 2 ——
  `tests/test_cli_errors.py::test_remove_of_a_missing_record_exits_2_with_the_prefix`。
- ✅ `holdings check` 缺依赖输出 `错误（6）：…`；`--json` 退出码与文本模式一致，
  且带 `"ok": false` —— `tests/test_check_cmd.py` 的 7 条用例，其中一条专门
  参数化两种模式断言退出码相等。
- ✅ `tests/test_cli_errors.py` 的参数化表改为断言真实映射（含 6 与
  `RecordNotFoundError`），并仍走 `main()` 而非 `CliRunner`。
- ✅ `ERROR_HANDLING.md`、`USER_GUIDE.md`、`README.md` 三处退出码表同步更新。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-16）
**位置** `tests/test_deps.py`

### 完成情况

补上 `utils/deps.py` 的用例（新增 `tests/test_deps.py`，9 条）：
`is_installed` 对不存在的包为 `False`、对标准库为 `True`；
`check_dependencies` 覆盖全部声明过的包且字段完整、必需/可选标记正确；
`missing_required` 在缺包时返回包名、不缺时为空、**可选包缺失不算缺依赖**；
以及 `yaml` 的 pip 包名是 `pyyaml`（安装提示给用户的是包名，不是 import 名）。

**顺带修掉一个打桩陷阱**：`check_dependencies` 原本调的是模块级别的别名
`_is_installed`，而别名在导入时就绑定了原函数——`monkeypatch.setattr(deps,
"is_installed", ...)` 这个最自然的做法会**静默失效**，测试写出来是绿的看着
像在测东西，实际什么都没换掉。别名只在模块内用，已删除。

`utils/formatter.py` 与 `utils/currency.py` 由 [B-12](#b-12) 处理（前者接上并补测，
后者删除）。

**完成判据**

- ✅ `utils/deps.py` 覆盖率 **100%**（要求 ≥ 90%）。
- ✅ 全项目行覆盖率 89% → **90%**；`TESTING_STRATEGY.md` 与本文的覆盖率数字同步更新。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`utils/config.py` 已在近期补到 90%（deep merge、YAML 错误、缺失文件），但同层仍有空白：

| 文件 | 覆盖率 | 说明 |
|------|--------|------|
| `utils/deps.py` | 0% | `is_installed` / `check_dependencies` / `missing_required` 三个纯函数，`check` 命令直接依赖 |
| `utils/formatter.py` | ✅ 100% | 已由 [B-12](#b-12) 接上渲染层并补测 |

### 要做什么

- 补 `deps.py` 的用例：`is_installed("一定不存在的包")` 为 `False`；
  `missing_required()` 在 monkeypatch 掉某个必需包后返回其名；`check_dependencies()` 的返回结构
  与 `PackageStatus` 字段完整。
- `formatter.py` 已接上并补测；`currency.py` 已删除。两者都由 [B-12](#b-12) 处理完毕。
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

**优先级** ✅ 已完成（2026-09-16）
**位置** `cli/commands/`、`services/`

### 完成情况

- `snapshot` 一处随 [B-03](#b-03) 收口（新增 `services/snapshot_service.py`）。
- `remove` 一处本次收口：`trade_service` 增 `get_transaction` / `remove_transaction`。
  删除看似不涉及校验，但它是「改动账本」的第三条路径——绕过 service，账本就有了
  第二条不受管的写入路径。
- `init` 按条目建议**写成明确的豁免条款**（引导命令，它要建的正是别的 service
  赖以工作的数据库），不再挂在「违反」里。
- ARCHITECTURE 的执行情况表由「⚠️ 2 处违反」改为「✅，仅存一处有理由的豁免」。
- 守卫用例的允许清单缩到只剩 `init`；它断言的是精确内容，所以「修好一处却没删
  名单行」也会红——这份清单不会烂在原地。

**完成判据**

- ✅ `grep -rn "holdings.storage" src/holdings/cli/` 只剩 `init.py` 一处。
- ✅ 既有测试全绿；另补两条 `remove` 的成功路径用例（确认后删除、拒绝确认时不删）——
  换了调用路径，行为必须不变。

---

*以下为动手前的原始分析，保留备查。*

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

**优先级** ✅ 已完成（2026-09-16）
**位置** `utils/`、`services/chart_service.py`、`models/__init__.py`

### 完成情况：三个各有结论

| 对象 | 结论 | 说明 |
|------|------|------|
| `utils/formatter.py` | **接上** | 重写为 money / price / number / percent / ratio / quantity + `is_missing`，渲染层删掉私有的 `_money` / `_percent` / `_number` / `_missing` / `_UNKNOWN` 改用它。`—` 的语义与「一个数该怎么显示」现在只有一处定义。原 `format_money(value, currency)` 去掉了货币参数——没有调用点需要它，留个没人用的参数就是同一类腐烂 |
| `utils/currency.py` | **删除** | 占位实现（同币种返回原值、跨币种抛 `NotImplementedError`）。需要时从 git 历史取 |
| `chart_service.networth_json()` | **删除** | 真做 web 时需要的 JSON 结构多半跟它不一样 |

**顺手查出的第四个**：`models/__init__.py` 重导出了 5 个类并列入 `__all__`，
但全项目没有一处 `from holdings.models import X`——同样是零调用的转发代码，
而且它没有跟着 B-01 新增的 `AssetMeta` 一起维护，本身就是「这份清单没人看」
的证据。已删除，只留模块说明。

**完成判据**

- ✅ 三个对象各有明确结论（上表），没有第四个零引用模块：
  `portfolio/` `services/` `cli/renderers/` 的 `__all__` 里每个名字都验过有调用点。
- ✅ 删除项同步清了 `utils/__init__.py` 的 `__all__` 与 ARCHITECTURE 目录树；
  VISION 与 CONFIG_SPEC 里「预留 `utils/currency.py`」的说法一并改正。
- ✅ 接上项补了 `tests/test_formatter.py`（13 条），覆盖率 100%。

---

*以下为动手前的原始分析，保留备查。*

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

**一项改动一个提交，一个条目一个 PR**——一个条目至少一个提交，条目内部互不
依赖的部分再拆；每个条目走一个独立分支与独立 PR，不把多个条目塞进同一个。
提交信息与 PR 标题都带上条目编号（如 `fix: 给网络调用加超时 (B-05)`）。
两条都是硬性要求，理由与细则见
[编码与提交规范](CODING_STANDARDS.md#合并粒度一个功能一个-pr硬性要求)。

---

---

<a id="b-14"></a>

## B-14　`config.yaml` 字段取值没有校验

**优先级** ✅ 已完成（2026-09-16）
**位置** `src/holdings/utils/config.py`

### 完成情况

`load_config()` 现在校验已知字段的取值，不合法抛 `ConfigError`（退出码 3），
消息指出字段、当前值与期望类型。规则写成一张表（`_FIELD_RULES`），新增配置项时
照着加一行，不容易漏。覆盖 `database_path` / `default_group` / `default_market`、
`cache_ttl_seconds`、`sync.timeout_seconds` / `sync.retry_count`、
`data_sources.priority`。**未知字段原样保留**。

去掉了一套重复机制：`Config` 的 `sync_timeout_seconds` / `sync_retry_count`
此前各自做取值兜底（`timeout_seconds: abc` 静默回落到默认值），校验接上之后
那是不可达代码——而且它会掩盖「配置被静默忽略」这件事，正是本条要修的毛病。
现在属性直接取值，只留一套机制。

**完成判据**

- ✅ `cache_ttl_seconds: abc` → `holdings list` 输出 `错误（3）：…`、退出码 3、无 traceback。
- ✅ 每个受校验字段都有参数化用例（7 条合法值通过、12 条非法值各指出字段名）。
- ✅ `CONFIG_SPEC.md` 第 4 条约束的 ⚠️ 去掉，改成如实描述校验范围。

### 现状

`CONFIG_SPEC.md` 的第 4 条约束写着「⚠️ 字段取值暂未做校验」。语法错误的 YAML 会被
拦成 `ConfigError`（退出码 3），但**取值**不合法不会：

- `cache_ttl_seconds: abc` 或 `-1`，要到某条命令真去读它时才炸，用户看到的是裸
  traceback（退出码退化成 1），而不是「错误（3）：…」；
- `database_path: []`、`default_group: 3` 同理。

B-05 修的是「配置项改了不起作用」，这一条是它没覆盖的另一半：**配置项改错了也不吭声**。
两者合起来才是「配置可信」。

### 要做什么

- 在 `load_config()` 里做一次字段校验，不合法抛 `ConfigError`（退出码 3），
  消息指出是哪个字段、当前值是什么、期望什么。
- 至少覆盖：`cache_ttl_seconds`（非负整数）、`sync.timeout_seconds`（数字）、
  `sync.retry_count`（非负整数）、`database_path` / `default_group` / `default_market`（字符串）、
  `data_sources.priority`（map，值是字符串列表）。
- 校验通过后，`Config` 上那几个**取值兜底**的属性（`sync_timeout_seconds` /
  `sync_retry_count`）就变成不可达代码，一并去掉，只留一套机制。
  `resilience.retry_count()` 里的兜底同理——但要保留它「配置坏了不影响取价」的
  语义，改成捕获 `ConfigError` 返回默认值。

### 完成判据

- `cache_ttl_seconds: abc` → `holdings list` 输出 `错误（3）：…`，退出码 3，无 traceback。
- 每个受校验字段都有一条参数化用例（合法值通过、非法值抛 `ConfigError`）。
- `CONFIG_SPEC.md` 第 4 条约束的 ⚠️ 去掉，改成如实描述校验范围。

---

<a id="b-15"></a>

## B-15　UI 层（v2.0.0）

**优先级** P3 · 路线图事项，不在体检范围内
**位置** 待定（Textual TUI 起手，见 [ROADMAP](ROADMAP.md) 的 v2.0.0）

### 现状

`VISION.md` 的长期目标是「用同一套 Service 层，从 CLI 平滑演进到 TUI、Web 乃至
桌面应用」，`pyproject.toml` 也已声明 `tui` / `web` / `gui` 三组可选依赖——
但**一行界面代码也没有**。此前它只活在 ROADMAP 里，而 BACKLOG 才是工作项的
权威清单，所以在这里登记一条。

### 前置条件：已经具备（2026-09-16）

界面能复用 `services/` 不是一句承诺，而是 CI 里的红线。`tests/test_layering.py`
逐条守着：

- 六个非表现层（`portfolio` / `storage` / `data` / `services` / `models` / `utils`）
  零 `print` / `echo`、不 import `rich` / `click`；
- 依赖方向符合架构图，`services` 不反向依赖 `cli`；
- 在子进程里只 import 核心层，`sys.modules` 里不会出现 click / rich。

也就是说，**现在才开始写 UI 是安全的**：核心逻辑已经是可复用的纯数据接口，
不会出现「接界面时才发现要先把 print 全挖掉」那种返工。

### 要做什么（尚未开始）

1. **起手做 TUI**（Textual，`pyproject` 的 `tui` extra 已就位）：持仓表 + 报表
   两屏，数据全部来自 `services`。CLI 继续存在，两者共用同一套 service。
2. **界面的报错呈现**：`ERROR_HANDLING.md` 的「GUI（未来）」一节已经写明约定
   （异常统一在 Service 层抛出、界面捕获后转成提示），需要落实一次并补文档。
3. **终端宽度**：B-07 给 CLI 做了简表 / 详表两档，TUI 的布局要复用同一份
   `HOLDINGS_COLUMNS` 定义，别再造一份列清单。

### 完成判据

- TUI 能启动、能看持仓与报表，且**不 import `cli/`**——`tests/test_layering.py`
  的 `test_services_can_be_used_without_touching_the_cli` 已经为这条铺好了路。
- `pyproject.toml` 的 `tui` extra 装上就能跑，缺依赖时按退出码 6 的语义给提示。
- `ARCHITECTURE.md` 的目录树与依赖方向图补上这一层。

---

## 相关文档

- [架构与模块隔离规范](ARCHITECTURE.md) —— 铁律与当前执行情况
- [数据库设计说明](SCHEMA.md) —— `asset_meta` 与 `snapshots` 的字段定义
- [配置项字典](CONFIG_SPEC.md) —— 标注了哪些配置项尚未生效
- [错误码与异常处理规范](ERROR_HANDLING.md) —— 退出码契约
- [测试策略](TESTING_STRATEGY.md) —— 覆盖率目标与现状
- [详细开发路线图](ROADMAP.md) —— 里程碑划分
