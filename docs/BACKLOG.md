# 待办清单（BACKLOG）

> 2026-09-15 工程体检的剩余发现，加上体检后新发现的问题与已知能力缺口。
> **本文件是工作项的唯一权威清单**，路线图与体检报告只保留摘要并指向这里。

**当前状态（2026-09-23）**：除待办的 **B-21~B-23** 与 **B-28~B-33** 外，
清单内条目**全部交付**（用例 159 → 427，覆盖率 67% → 96.52%），**v1.0.0 已发布**。
这 9 项都是 v2.0.0 的能力建设，建议顺序见文末
「[剩余条目的执行顺序](#剩余条目的执行顺序)」。

## 怎么读这份清单

- 每项给出 **优先级 / 位置 / 现状 / 要做什么 / 完成判据**。完成判据是「这件事算不算做完」的客观标准，
  不能自证「已改」——要么有用例锁住，要么有可复现的命令输出。
- 优先级沿用体检报告的 P1/P2/P3：**P1 = 文档承诺了但功能不存在**，
  **P2 = 会误导用户或丢数据**，**P3 = 工程卫生**。
- 改动任何一项时，顺手核对受影响的文档（尤其 `SCHEMA.md`、`USER_GUIDE.md`、`CONFIG_SPEC.md`）。
  这批问题的成因几乎都是「文档先行、实现没跟上」，改实现时不同步改文档会再生产一批。
- 条目标题形如 `B-07`，可在提交信息与 PR 里直接引用（如 `fix: 修正窄终端表格截断 (B-07)`）。

**条目是怎么来的**：

- 体检报告剩余 **9 项发现**对应 8 个条目 —— B-01、B-02、B-03、B-04、B-06、B-07、B-09，
  加上 B-08（「`remove` 报错格式」与「`check --json` 退出码」是同一个契约问题的两面，合并为一项）。
- 另有 **4 项**不在那 9 项里：
  - [B-05](#b-05) 死配置项与网络超时 —— 报告里那一行标记的是「文档已改正」，
    让配置项**真正生效**是没做的工作；
  - [B-10](#b-10) `data/` 层降级路径测试 —— 报告只在模块完整度表里提了一句；
  - [B-11](#b-11) 铁律 3 的违反 —— 同上，只在 `ARCHITECTURE.md` 里记录过；
  - [B-12](#b-12) 零引用死代码 —— 体检后新 grep 出来的，不在最初的清单里。

**B-13 ~ B-15** 是执行期间新增的：B-13（全库英文化）提出后**被用户撤回**，
已从清单移除；B-14（配置字段校验）与 B-15（UI 层）是做的过程中拆出来的。

**B-16 ~ B-23** 是 B-01~B-15 全部交付后重新扫描出来的，分三类：

- **B-16 / B-17**：与刚清完的那批同类的「说了没做」——只是一个在 `pyproject.toml` 里，
  一个在 `init --dev` 上（B-12 清的是代码里的零引用，漏了配置里的）。
- **B-18**：发布收尾（版本号还停在 `0.1.0`）。
- **B-19**：多币种标的被当成同一种货币相加——口径不成立却给了看着像结论的数，
  与 B-05 / B-06 同类。
- **B-20 ~ B-23**：v2.0.0 的路线图事项与已知能力缺口。

**B-24 ~ B-26** 是交付后回头复盘 CI 与协作流程时发现的，三项同源——都是「已经
有地方证明了，只是没人看」或「规矩一直有，只是没写在会被读到的地方」，见各自条目。

**B-27 ~ B-33** 不在体检范围内，来自用户提的两条需求：**「导入股票交易流水，
支持模块化增加不同证券公司」**与**「拉取股票信息也支持模块化配置」**。它们是能力
缺口而非缺陷，拆法受一条判断支配：**这两件事是同一个机制**（按名字注册进来、
按配置挑一个用），而取价链路已经把这个骨架搭了一半（`data/sources.py` 的按配置
降级早就生效）——所以是把它提出来共用，不是各写一套。

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
| [B-10](#b-10) | ✅ 已完成 | 三个 fetcher 覆盖率 18%~29%，降级路径无测试 | `tests/test_data.py` |
| [B-11](#b-11) | ✅ 已完成 | `cli` 越过 `services` 直接碰 `storage` | `cli/commands/`、`services/` |
| [B-12](#b-12) | ✅ 已完成 | 3 个模块/函数写完从未被调用 | `utils/`、`services/chart_service.py` |
| [B-14](#b-14) | ✅ 已完成 | `config.yaml` 的字段取值没有校验 | `utils/config.py` |
| [B-15](#b-15) | ✅ 已完成 | UI 层（v2.0.0） | `tui/` |
| [B-16](#b-16) | ✅ 已完成 | `web` / `gui` 两个 extra 零引用 | `pyproject.toml` |
| [B-17](#b-17) | ✅ 已完成 | `init --dev` 是个空壳 | `cli/commands/init.py` |
| [B-18](#b-18) | ✅ 已完成 | 收尾并发布 v1.0.0 | `pyproject.toml`、`docs/` |
| [B-19](#b-19) | ✅ 已完成 | 多币种标的被当成同一种货币相加 | `services/portfolio_service.py` |
| [B-20](#b-20) | ✅ 已完成 | Web 界面（v2.0.0） | 新增 `web/` |
| [B-21](#b-21) | P3 | 多账户 | `portfolio_group` 已预留 |
| [B-22](#b-22) | P3 | 桌面端（v2.0.0） | 取决于 [B-16](#b-16) |
| [B-23](#b-23) | P3 | 能力缺口：基准对比 / 分红拆股 / 导出 | 待定 |
| [B-24](#b-24) | ✅ 已完成 | CI 只验证了「源码树能跑」 | `.github/`、`pyproject.toml` |
| [B-25](#b-25) | ✅ 已完成 | `holdings chart` 的产图路径没有用例 | `tests/`、`cli/` |
| [B-26](#b-26) | ✅ 已完成 | 「一个功能一个 PR」没写在入口页 | `CONTRIBUTING.md` |
| [B-27](#b-27) | ✅ 已完成 | 对账单里认不出的行，不能静默跳过 | `cli/commands/import_cmd.py` |
| [B-28](#b-28) | P1 | 券商流水导入：解析器注册表与识别 | 新增 `data/brokers/` |
| [B-29](#b-29) | P2 | 同一个文件导两遍，账翻倍 | `storage/`、`services/trade_service.py` |
| [B-30](#b-30) | P1 | 头两家券商的真实解析器（**卡在样本上**） | `data/brokers/`、`tests/fixtures/` |
| [B-31](#b-31) | P2 | 「股票信息」目前只有价格 | 新增 `data/instrument.py` |
| [B-32](#b-32) | P2 | 导入时只有代码，市场只能默认 | `cli/commands/import_cmd.py` |
| [B-33](#b-33) | P3 | 加一个市场要改 `get_fetcher` 的 if-chain | `data/fetcher.py` |

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

**优先级** ✅ 已完成（2026-09-16）
**位置** `tests/test_data.py`

### 完成情况

降级链路本身在 B-05 已覆盖（重试次数、退避、降级时机、优先级顺序），
本次补的是**各数据源自己的解析分支**，用 `monkeypatch.setitem(sys.modules, ...)`
伪造 `akshare` / `yfinance` 模块：

- `_from_akshare`：解析最新价、代码不存在时抛 `SymbolNotFoundError`、
  未装 akshare 时抛 `DataSourceUnavailableError`（而不是漏一个 `ImportError`）。
- `_from_yfinance`：**后缀推导**（`6` 开头 → `.SS`，否则 `.SZ`）、空行情报未找到、
  未装 yfinance 时报「未安装」。后缀推错不会报错，只会查到一个不存在的代码然后
  「未找到标的」——排查起来毫无线索，所以单列一条参数化用例。
- 美股与黄金同样三条：解析、未找到、缺依赖。黄金另有一条：国内代码确实走
  A 股链路而不是国际金价。

**顺带修掉一处真实等待**：`test_a_domestic_gold_symbol_never_gets_the_international_price`
的退避没打桩，真的睡满 1 秒——正是判据里「整个 tests/ 跑完不加 sleep 时间」
要拦的那种。已打桩。现在唯一耗时 1 秒的是 B-05 那条刻意验超时的用例
（配置里写 `timeout_seconds: 1`，等的是真实的预算而不是 sleep），属于预期。

**完成判据**

- ✅ `data/` 层覆盖率 **98%**（要求 ≥ 80%）；三个 fetcher 分别 **100% / 94% / 95%**。
- ✅ 「akshare 失败一次后成功时不调用 yfinance」「始终失败才降级、最终抛
  `DataSourceUnavailableError` 而非原始异常」在 B-05 已锁住，本次沿用。
- ✅ 整个 `tests/` 跑完 3.6 秒，无真实 sleep。

---

*以下为动手前的原始分析，保留备查。*

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

## 剩余条目的执行顺序

B-01~B-17 已交付（原顺序的前两步走完）。以下是 B-18 之后的建议顺序，
按「依赖关系 + 能不能立刻做完」排：

1. ~~**B-19**~~ —— ✅ 已完成（2026-09-19）。多币种混加会给出看着像结论的错数，
   与 B-05 / B-06 同类，优先于路线图事项。口径已定（基准货币人民币），
   本轮只要求「如实排除并说明」。
2. ~~**B-18**~~ —— ✅ 已完成（2026-09-20），v1.0.0 已打 tag。
   BREAKING CHANGE 已随 CHANGELOG 记入（`init --dev` 移除、两个 extra 删除，
   见 [B-16](#b-16) / [B-17](#b-17)）。
3. ~~**B-20**~~ —— ✅ 已完成（2026-09-21），只读看板（[B-20](#b-20)）。
   v2.0.0 的能力建设，按实际用到的顺序做；B-21（多账户）与 B-23（能力缺口）
   不依赖彼此，可以先做更常用的那个。
4. **B-22** —— 桌面端形态未定。[B-16](#b-16) 已给出结论（两个 extra 都删掉、
   不留占位），所以要先在 `VISION.md` / `ARCHITECTURE.md` 里定下形态，
   再决定是否加回依赖。
5. ~~**B-24**~~ —— ✅ 已完成（2026-09-22）。不在原计划里，是回头复盘 CI 时
   发现的：三个漏口（不建 wheel、覆盖率不上 CI、extra 声明从不被安装）
   有同一个根子——**CI 只证明「源码树能跑」**。已拆成三条作业
   （[B-24](#b-24)）。
6. ~~**B-25**~~ —— ✅ 已完成（2026-09-22），与 B-24 同源：同一次复盘里发现的
   测试缺口（`holdings chart` 的成功路径零执行），[B-24](#b-24) 让 CI 装上
   plotly 之后它才补得动（[B-25](#b-25)）。
7. ~~**B-26**~~ —— ✅ 已完成（2026-09-22）。同样是复盘产物：规矩一直有，只是
   没写在协作入口页上，[B-26](#b-26)。
8. **B-27 → B-28 →（B-29 / B-31 并行）→ B-30 → B-32 → B-33** —— 用户提的两条
   需求拆成的一批（[B-27](#b-27) 起）。这个顺序不是偏好，是依赖：
   - ~~**B-27 最先**~~ —— ✅ 已完成（2026-09-23）。三态口径与逐行报告已定，
     [B-28](#b-28) 的解析器照着它产出即可（[B-27](#b-27)）；
   - **B-29 与 B-31 互不依赖**，谁先都行；B-31 是 B-32 的前置；
   - **B-30 卡在样本上**：没有真实对账单，解析器只能对着想象的格式写。
     样本到位前先交付 B-27 / B-28 / B-29 / B-31；
   - **B-33 最后**：纯重构，等前两项把注册表的形状真的用出来再搬，免得先设计
     一个没人用的通用件（[B-12](#b-12) 的教训）。

> **B-13（全库英文化）的说明**：它曾被提出、动工后由用户撤回，代码已全部回滚
> （见提交历史里那段 i18n 的往返）。此处不再列为待办；若将来要做，
> 当年那份设计（轻量字典目录 + `config.yaml` 的 `language` + 英文为基准）
> 在 git 历史里可查。

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

**优先级** ✅ 已完成（2026-09-16）
**位置** `src/holdings/tui/`、`cli/commands/tui.py`

### 完成情况

起手做了 TUI（`holdings tui`）：持仓表 + 报表两屏，`q` 退出、`r` 刷新。

- **数据全部来自 `services/`**，界面里一行 SQL、一个网络请求都没有。
  这也让「前置条件已具备」从判断变成了可验证的事实——`tests/test_layering.py`
  断言 `tui/` 层不允许 import `cli/`、`storage/`、`data/`、`portfolio/`。
- **`HOLDINGS_COLUMNS` 从渲染层搬到服务层**（前一个提交）：表头是两个界面
  共用的契约，各写一份迟早叫法不一致。
- 口径与 CLI 一致：无行情显示 `—` 并提示去 sync，绩效算不出来时不显示数字。
- Textual 是可选依赖，缺了抛 `MissingDependencyError`（退出码 6）并给出
  `pip install 'holdings[tui]'`。
- `textual` 同时进 `dev` extra——否则 CI 只能测「缺依赖时报错」那一条，
  界面本身永远测不到。界面用 Textual 的 headless 测试跑真实渲染。

**完成判据**

- ✅ TUI 启动、能看持仓与报表，且不 import `cli/`（覆盖率 100%）——
  `tests/test_tui.py` 用 `app.run_test()` 跑真实界面：表格行数、无行情提示、
  报表页的最大回撤、`r` 刷新后跟着库变。
- ✅ 缺 textual 时退出码 6 并给出安装命令。
- ✅ ARCHITECTURE 的目录树与依赖方向图补上这一层。

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

<a id="b-16"></a>

## B-16　`web` / `gui` 两个可选依赖组零引用

**优先级** ✅ 已完成（2026-09-17）
**位置** `pyproject.toml`、`CONTRIBUTING.md`

### 完成情况

按条目的倾向**删除**两个 extra，而不是标注「预留」：

- `pyproject.toml` 去掉 `web` / `gui` 两行，留一条注释记下它们为何消失、
  何时该加回来（形态决策见 [B-22](#b-22)）。
- `CONTRIBUTING.md` 的「`tui` / `web` / `gui` 三组同理」同步改为 `chart` / `tui`。
- `chart` 上方那条注释原本靠「此前挂在 `gui` 里」解释自己为何单列，
  `gui` 没了之后那句话指向一个不存在的组，一并改写成当下的理由。

**完成判据**

- ✅ `pyproject.toml` 里不再有声明了却零引用的 extra。剩余四组的源码引用：

  ```console
  $ grep -rn "streamlit\|fastapi\|PySide6" src/ tests/
  （无输出——两个已删的组确实零引用）
  $ grep -rn --include='*.py' "akshare\|yfinance" src/ | wc -l   # data 组
  34
  $ grep -rln --include='*.py' plotly src/ | wc -l              # chart 组
  4
  $ grep -rln --include='*.py' textual src/ | wc -l             # tui 组
  2
  ```

  `dev` 组的 `ruff` / `pytest-cov` 零 import 是正常的——它们是命令行工具，
  不是被 import 的库；判据针对的是「装了却用不上的依赖」。
- ✅ 元数据里只剩四组，已删的两组不再出现：

  ```console
  $ python -c "import tomllib;print(list(tomllib.load(open('pyproject.toml','rb'))['project']['optional-dependencies']))"
  ['data', 'chart', 'tui', 'dev']
  ```

  改动只动了 `optional-dependencies`，核心依赖未变；`pip install --dry-run --no-deps -e .`
  仍能正常解析元数据。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`pyproject.toml` 声明了 `web = ["streamlit", "fastapi"]` 与
`gui = ["PySide6", "plotly"]`，但 `streamlit` / `fastapi` / `PySide6` 在
`src/holdings/` 里**零引用**。`pip install 'holdings[gui]'` 会装好 200MB 的
PySide6，然后没有 GUI 可用。

这与 [B-12](#b-12) 是同一类问题，只是发生在配置里而不是代码里——B-12 清了代码中
的零引用，漏了 `pyproject.toml`。

### 要做什么

二选一，别维持现状：

- **删掉**这两个 extra，等真写 Web / 桌面端时再加回来；
- 或保留但在 `pyproject.toml` 与 `README` 里**明确标成「预留，未实现」**。

倾向删除：装了却用不上的依赖比没有更费解。（[B-22](#b-22) 的形态选择依赖本项结论。）

### 完成判据

- `pip install -e .` 不带额外依赖时不装任何用不上的包。
- `pyproject.toml` 里不再有声明了却零引用的 extra，或每一条都有「预留」标注。

---

<a id="b-17"></a>

## B-17　`init --dev` 是个空壳

**优先级** ✅ 已完成（2026-09-17）
**位置** `src/holdings/cli/commands/init.py`、`tests/test_init_cmd.py`

### 完成情况

选**删除**而不是补语义。补语义需要先回答「开发库与生产库差在哪」，而 `init`
本就按 `config.yaml` 的 `database_path` 建库，两者没有分别——补出来的语义是硬造的。
`CONTRIBUTING.md` 的入门第 3 步也因此从 `init --dev` 改回 `init`（那一步此前
其实什么都没多做到）。

顺带删掉同在该命令上、**全仓库唯一一处** `@click.pass_context`：`ctx` 从未被读，
是同一类摆设（只是不在命令行上）。

`init` 此前**零用例**，本次补上 `tests/test_init_cmd.py` 三条：建出库与配置、
不覆盖已有配置、`--dev` 已被拒绝。

**完成判据**

- ✅ 参数不复存在，且拒绝方式符合既有契约：

  ```console
  $ holdings init --help
  Usage: holdings init [OPTIONS]

    初始化项目：创建数据库与默认配置文件。

  Options:
    --help  Show this message and exit.

  $ holdings init --dev
  错误（5）：No such option '--dev'.
  $ echo $?
  5
  ```

  退出码 5 而非 click 默认的 2 是既有的有意设计：2 归「标的 / 记录未找到」，
  用法错误统一归 5（`cli/main.py` 用 `standalone_mode=False` 接管）。
- ✅ `USER_GUIDE.md` 的示例与 `--help` 同步，`CONTRIBUTING.md` 的入门步骤同步。
- ✅ 用例锁住：`tests/test_init_cmd.py::test_removed_dev_flag_is_rejected`。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`--dev` 的全部实现是：

```python
if dev:
    click.echo("开发模式已启用（暂不创建额外数据）")
```

它什么都不做。与 [B-04](#b-04) 修掉的 `chart --start`（help 自己写着「暂存参数」）
是同一类——**参数存在但无效比没有更糟**，用户会以为开发环境被配置好了。

### 要做什么

二选一：**给它真实语义**（如初始化测试库、写入一份开发用 `config.yaml`），
或**删掉它**（连同 `USER_GUIDE` 里的示例）。

### 完成判据

- `holdings init --dev` 要么产生可观察的差异，要么这个参数不复存在。
- `USER_GUIDE.md` 与 `--help` 同步。

---

<a id="b-18"></a>

## B-18　收尾并发布 v1.0.0

**优先级** ✅ 已完成（2026-09-20）
**位置** `pyproject.toml`、`CHANGELOG.md`、`ROADMAP.md`、`README.md`、`docs/demo/`

### 完成情况

1. **版本号 `1.0.0`，且只有一处**：`pyproject.toml` 的 `version` 是唯一的那个数，
   `holdings.__version__` 从打包元数据读出，不再手写第二份（两处改一处漏一处，
   此前不会有任何东西会响）。`holdings --version` 已是 `1.0.0`；本地 editable
   安装要重装一次才看得到。
2. **CHANGELOG 收口**：`Unreleased` → `## [1.0.0]`；14 个重复小节归成
   Added / Changed / Removed / Fixed / Docs 五节（正文逐行保留，只挪位置）；
   删掉已过期的 `### Planned`（其中「清掉 B-01~B-12」早已交付）。
3. **演示录制**——**换了工具**。原计划用 `terminalizer` / `asciinema`，
   执行时先选了 `vhs`，实测**在本机不可用**：它靠 headless Chrome 渲染终端，
   而 Chrome 起不来（`--headless --dump-dom about:blank` 挂死超过 120 秒，
   关掉命令沙箱一样挂），连 vhs 自带的示例 tape 都出不了文件——且失败时退出码是 0、
   不报错。改用 **`asciinema` + `agg`**，两者都不依赖浏览器。
   - 两处踩坑记在 `docs/demo/demo.sh` 的注释里：录制的 pty 默认 80 列，
     会让 `list` 退化成 B-07 的简表，要用 `stty cols 110` 撑开；转 GIF 时
     agg 的 `--cols` 必须跟着改成 110，否则边框字符错位。
   - 演示**不含真实的 `sync`**：实测耗时 2 分 09 秒、满屏 curl 报错，
     且 518880 稳定失败。改为由 `docs/demo/setup.sh` 预置行情缓存
     （等价于「已经 sync 过」），`sync` 命中缓存、瞬间返回。代价是演示里的价格
     是**编造的样例数字**，这一点在 `setup.sh` 注释与 README 的演示小节都写明了。
4. **ROADMAP 勾选收尾**：v1.0.0 小节与里程碑总览的「实际状态」同步。
5. **打 tag `v1.0.0`**（仓库的第一个 tag）。

### 完成判据

- ✅ `holdings --version` 输出 `1.0.0`。
- ✅ README 里有演示动图（`docs/demo/holdings.gif`），并链接到可复现的录制脚本。
- ✅ `ROADMAP.md` 的 v1.0.0 全部勾上，里程碑总览改为「已发布」。
- ✅ 打 tag `v1.0.0`。

> **一处未查证**：判据里的「打 tag 后 CI 绿」这一条没能核实——本机到 GitHub API
> 的 TLS 握手超时（`gh` 用不了），只有 git 协议通。CI 的触发条件是 push 到
> `main` / `master` 或 PR，**推 tag 本身不会触发**，要绿得看 `b-18-release`
> 那个 PR 的运行结果。

---

<a id="b-19"></a>

## B-19　多币种标的被当成同一种货币相加

**优先级** ✅ 已完成（2026-09-19）
**位置** `services/portfolio_service.py`、`cli/renderers/table_renderer.py`、`utils/formatter.py`

### 完成情况

按条目倾向的第 1 条做：**如实排除，不做换算**。基准货币 `BASE_CURRENCY = "CNY"`
写在 `portfolio_service` 里（与 `AssetMeta.currency` / `price_cache.currency` 的默认值一致），
不进配置——汇率才是 v2.0.0 的事，一个现在只有唯一取值的配置项就是下一个死配置（[B-05](#b-05)）。

- 汇总的口径从「有行情的标的」收紧为「**能按基准货币计价的标的**」：有行情、且行情
  是人民币，两个条件都满足才计入。外币标的的市值、成本、盈亏三项一律不加，
  由新的 `foreign_holdings` / `foreign_cost` 报给渲染层。
- `holding_for(pos, None)` 这一条现成的通道就够了：把「算不出来」交给它，市值、盈亏、
  盈亏率自然变成 `None`，渲染层显示 `—`，不必新增第二套空值机制。
- **行内账本事实与行情派生数字分开**：数量 / 成本价 / 累计费用照常显示（那是账本记下的，
  与有没有行情、是哪种货币无关），市值 / 盈亏 / 盈亏率显示 `—`；现价照常显示但**带上币种**
  （`200.0000 USD`），只在非人民币时标——同一列里混着两种货币而不加标注，
  等于把「不混加」做了一半。
- 提示行与 B-06 的无行情提示并列，措辞说明的是「没加进去」而不是「加不了」：

  ```text
  总市值 1,200.00 | 总成本 1,000.00 | 总盈亏 200.00 (20.00%) | 累计费用 0.00
  1 个标的以美元计价（成本合计 1,000.00），未计入上面的汇总；本工具按人民币口径汇总，不做汇率换算
  ```

**顺带统一了一处口径**：`total_value` / `total_cost` 在**一个标的都计不进来**时改为 `None`。
此前它们仍是 `0.0`，由渲染层另外判断一次（`not unpriced_symbols or bool(allocation)`）
才显示成 `—`——两处判断迟早对不上，而这一项正好要往里面加第三个条件。现在三个数
与 `total_profit` 一致，渲染层直接 `format_money` 即可，那段启发式判断已删除。

**两处判断**

- **`total_fees` 不按币种拆分**。外币标的的费用同样记在它自己的货币下，但交易流水里
  没有币种字段，拿行情缓存的币种去反推账本口径只是另一层猜测。已在字段旁写明这一点，
  而不是假装它已经被处理过。
- **行内不隐藏成本价**。「USD 标的的成本价是多少」是账本事实且自洽（用户按当地市场
  报价录入），与市值不同——市值要放进总额才需要汇率。

**完成判据**

- ✅ 持有美股 + A 股时 `holdings list` 的总市值**不含**美元标的，且有提示行 ——
  `tests/test_multi_currency.py::test_list_reports_what_it_left_out`（断言 `总市值 1,200.00`，
  即只算人民币标的）与 `test_a_foreign_holding_stays_out_of_every_total`。
- ✅ 三种情形都有用例：全 CNY（`test_all_cny_is_the_baseline`）、混合
  （`test_a_foreign_holding_stays_out_of_every_total`）、全非 CNY
  （`test_everything_foreign_reports_unknown_not_zero`，断言总额是 `None` 而非 `0`）。
- ✅ 行内取值：外币行保留现价与币种、三个派生数字为 `NaN`；人民币行不受邻居影响。
  渲染层另有「现价带币种、人民币行不带」「无行情行不挂币种」两条。
- ✅ TUI 同口径 —— `tests/test_tui.py::test_foreign_symbols_are_flagged`。
- ✅ `VISION.md` 的「不做多币种换算」改为准确描述（不做换算，但不混加）；
  `USER_GUIDE.md` 第 3 节补上外币的显示规则与提示语。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`PriceResult` 带 `currency`，`price_cache` 也存了币种，但汇总**完全不看它**：

```python
market_value = position.quantity * current_price  # 不管 price 是 USD 还是 CNY
total_value = sum(market_values.values())
```

持有 AAPL（USD 报价）与 600519（CNY 报价）时，**总市值是把美元和人民币当同一种
货币加出来的数**，而它看起来完全正常——与 [B-06](#b-06) 的「−100%」、
[B-05](#b-05) 的黄金 GC=F 是同一类：口径不成立时给了一个看着像结论的数。

`VISION.md` 把它写成「不做多币种复杂换算」，但真正的问题不是「没有换算功能」，
而是**没有换算却照加不误**。

### 口径（已定）

**基准货币是人民币（CNY）。** 它已经是 `AssetMeta.currency` 与
`price_cache.currency` 的默认值。

### 要做什么

不必真做汇率换算（那是 v2.0.0）。本轮要的是**别给一个错的数**：

1. 汇总时检查各标的的 `currency`，与基准货币不一致的按 B-06 那套处理——
   不计入总额、显示 `—`，并在提示行说明「N 个标的以美元计价，未计入汇总」。
2. 或引入 `default_currency` 配置项 + 一张汇率表；若走这条，汇率的来源与
   更新方式要先在 `CONFIG_SPEC.md` 里写清楚。

倾向第 1 条：先把「不知道」如实说出来，换算留到 v2.0.0
（见 [B-20](#b-20) 同批）。

### 完成判据

- 持有美股 + A 股时，`holdings list` 的总市值**不含**美元标的，且有明确的提示行。
- 用例覆盖「全 CNY」「混合币种」「全非 CNY」三种情形。
- `VISION.md` 的「不做多币种换算」改为准确描述：不做换算，但不混加。

---

<a id="b-20"></a>

## B-20　Web 界面（v2.0.0）

**优先级** ✅ 已完成（2026-09-21）
**位置** 新增 `src/holdings/web/`（与 `cli/`、`tui/` 平级）、`cli/commands/web.py`

### 完成情况

起手做了**只读看板**（`holdings web`）：持仓 / 报表 / 净值曲线三页，默认
`http://127.0.0.1:8420`。

- **只读是刻意划的界**。`VISION.md` 说的远期形态里有「FastAPI 服务」，但写操作
  （`add` / `meta`）没有一起做：写入闸门（[B-11](#b-11)）要把「哪一条不合法、
  为什么」连同校验结果一起搬进页面才算数，而一个绕开闸门的 Web 表单正是
  「多了个入口就少了一道校验」。先把读的做扎实。
- **依赖随代码加回来**：`web = ["fastapi", "uvicorn", "jinja2"]`。
  [B-16](#b-16) 删掉的那个零引用 extra，到这里才有资格存在。
  `fastapi` / `jinja2` 同时进 `dev`——否则 CI 只能测「缺依赖报错」那一条路径。
  `uvicorn` 不进 `dev`：起真服务器的用例只会多出端口冲突这一种偶发失败。
- **模板是代码不是文档**：`[tool.setuptools.package-data]` 把
  `web/templates/*.html` 打进包里。漏了这条，源码目录里跑永远正常，
  `pip install` 装出来的包一请求就报「模板不存在」（已用 `pip wheel` 验证）。
  同一件事的另一半是 **`.gitignore` 的 `*.html`**——那条规则本意是忽略
  `holdings chart` 的导出，却把模板一并挡在版本库外：本地 380 个用例全绿
  （文件在磁盘上），CI 上每一次请求都是 `TemplateNotFound`。已改成锚定的
  `/networth.html`，理由与上面 `/data/` 那条相同，并加了
  `tests/test_packaging.py` 按**结果**守住——同一个坑这个仓库踩过两次了。

**顺手把「三个界面显示同一张表」从口号变成结构**

这是本项改动最大的一块，起因是第三个界面把重复摆到了明面上：

- **单元格文本上移到服务层**（`portfolio_service.holdings_cell`）。此前 TUI 自己
  有一份 `_cell`，Web 再写一份就是两份；列名（`HOLDINGS_COLUMNS`）早就在服务层了，
  「这一列按金额还是按单价显示」是同一份契约的另一半，没有理由留在界面里。
- **两条提示语上移到服务层**（`unpriced_hint` / `foreign_hint`，原先叫
  `render_unpriced_hint` / `render_foreign_hint`）。它们是**口径的一部分**——
  「上面的总额里少算了什么」必须和那个总额一起读。三个界面各写一遍的话，
  改口径时漏掉其中一句，用户就会把一个自己不知道是部分的数当成全部。
  界面只负责上色（CLI / TUI 裹 `[yellow]`，Web 裹一个 class）。
- 结果：CLI 的 `list` / `report`、TUI、Web 三处的提示语与单元格格式**物理上
  只有一处实现**。`tests/test_web.py::test_the_table_uses_the_shared_column_contract`
  断言 Web 的表头逐字来自那份契约。

**完成判据**

- ✅ 新层进入 `tests/test_layering.py` 的 `ALLOWED_IMPORTS`（`web` 只允许
  `services` / `models` / `utils` / `exceptions`），且不 import `cli/` / `tui/` ——
  依赖方向由 `test_imports_follow_the_layer_diagram` 参数化覆盖。
- ✅ 只读看板能起服务并看到真实数据 —— `tests/test_web.py` 用 `TestClient`
  直接打请求（起真服务器只多出端口冲突，测不到额外的东西）：持仓表、
  无行情提示、外币提示、`—` 而非 `0.00`、报表页的最大回撤 25.00%、
  曲线页嵌入 plotly 图。
- ✅ 三页的「算不出来」都照服务层的口径显示（`—` + 原因），页面不重算任何数：
  `test_the_numbers_match_the_service` 断言页面上的金额就是
  `get_summary()` 的返回值格式化的结果。
- ✅ 缺 `fastapi` / `uvicorn` 时退出码 6 并给出 `pip install 'holdings[web]'`。
- ✅ `holdings web` 默认只绑 `127.0.0.1` —— 这是个把全部持仓摊开的页面，
  `test_the_defaults_are_local_only` 锁住这一点。
- ✅ 文档同步：ARCHITECTURE 目录树与依赖方向图、TESTING_STRATEGY 用例清单、
  ROADMAP、VISION、USER_GUIDE、README、CHANGELOG。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`VISION.md` 的长期目标是「用同一套 Service 层，从 CLI 平滑演进到 TUI、Web
乃至桌面应用」。TUI 已在 [B-15](#b-15) 落地，Web 一行没有。

前置条件已具备：`tests/test_layering.py` 守着核心层零输出、零终端依赖、
依赖方向合规——新起一层界面不需要先挖 `print`。

### 要做什么

1. 起手做只读看板（持仓 + 报表 + 净值曲线），数据全部来自 `services/`。
2. 写操作（`add` / `meta`）需要 [B-11](#b-11) 那套写入闸门继续把关，
   不因为是 Web 就绕过校验。
3. 汇率（[B-19](#b-19)）若在此版实现，界面要能切换基准货币。

### 完成判据

- 新层进入 `tests/test_layering.py` 的 `ALLOWED_IMPORTS`，且不 import `cli/` / `tui/`。
- 只读看板能在本地起服务并看到真实数据。

---

<a id="b-21"></a>

## B-21　多账户

**优先级** P3 · 已预留的字段终于要用
**位置** `portfolio_group` 相关链路

### 现状

`transactions.portfolio_group` 与 `--group` 筛选早就在了（`add` / `import` /
`list` 都支持），但没有任何地方能**管理**它：不能重命名、不能列出有哪些组合、
不能看「每个组合各占多少」。它目前只是个筛选标签。

### 要做什么

- 一个列出全部组合及其汇总的命令或界面；
- 组合的重命名与合并（注意：改的是历史数据的字段，要一次事务写完）；
- `report` 可按组合分组展示。

### 完成判据

- 能列出组合清单与各自的总市值 / 盈亏。
- 重命名后 `list --group <新名>` 与旧名筛选的行为符合预期，且有用例锁住。

---

<a id="b-22"></a>

## B-22　桌面端（v2.0.0）

**优先级** P3 · 路线图事项
**位置** 待定

### 现状

`VISION.md` 提到 PySide6，但**没有任何代码**。形态未定：桌面端要么自己画界面
（PySide6），要么套一层 WebView 复用 [B-20](#b-20) 的 Web 界面。

### 要做什么

先决定形态，再动手。若要 PySide6，先做 [B-16](#b-16)（把那个零引用的 extra
处理掉，别让它继续假装存在）。

### 完成判据

- 形态决策写进 `VISION.md` / `ARCHITECTURE.md`，代码与依赖声明一致。

---

<a id="b-23"></a>

## B-23　能力缺口：基准对比 / 分红拆股 / 导出

**优先级** P3 · 记账工具的自然延伸
**位置** 待定

### 现状

三处已知的能力缺口，都不是缺陷，但都会在真实使用中撞到：

1. **基准对比**：`metrics.py` 能算组合自身的回撤与年化，但没法和指数比
   （「跑赢沪深 300 了吗」）。需要引入基准数据源与对齐逻辑。
2. **分红与拆股**：移动加权平均成本法只认 `BUY` / `SELL` / `FEE`。
   A 股送转会把成本价与数量一次性改变，分红则是现金流入——目前只能手工
   用 `SELL` + `BUY` 或 `FEE` 凑，凑出来的成本价是错的。
3. **导出**：只有 CSV **导入**，没有导出。报税、迁移、备份都缺一个出口。

### 要做什么

按实际撞到的顺序逐个做，每个都先想清口径再动代码（尤其第 2 项：它会影响
`calculator.py` 的核心算法，必须先写清「送转当天成本价应该怎么变」）。

### 完成判据

- 每个子项单独立项，各自给出可复现的判据。

---

<a id="b-24"></a>

## B-24　CI 只验证了「源码树能跑」

**优先级** ✅ 已完成（2026-09-22）
**位置** `.github/workflows/ci.yml`、`pyproject.toml`

### 完成情况

CI 从一条作业变成三条，每条证明一件**原来没有任何人证明**的事：

| 作业 | 证明什么 | 原来为什么没被证明 |
|------|----------|--------------------|
| `test` | 用例、ruff、**覆盖率门槛** | `pytest-cov` 装在 `dev` 里，却没人跑 `--cov`：96% 一直是本地手测的数，掉下去 CI 不会红 |
| `package` | **装出来的 wheel 能用** | `pip install -e` 与 `pythonpath = ["src"]` 两条路都直接读源码树 |
| `extras` | **每个 extra 都装得上** | CI 只装写死的 `[dev]`，从不读 extra 声明本身 |

三处关键细节：

- `package` 作业拿**装出来的 wheel** 跑 `tests/test_web.py`，用 `-o pythonpath=`
  盖掉 `pyproject` 里的 `pythonpath`，另加一句「导入的必须在 `site-packages` 下」
  的断言——防的是守卫自己失效。**已实测它真会红**：故意去掉 `package-data`
  重打一个 wheel，13 个用例失败，与 B-20 那次 CI 失败同数。
- `extras` 作业的 extra 名单从 `pyproject.toml` **现读**，不在 workflow 里抄一份。
  抄一份的写法会在「加了新 extra 而忘了同步」时悄悄失效。
- 覆盖率门槛 `fail_under = 95` 写在 `pyproject.toml`，本地与 CI 读同一份。
  取 95 而不是 96：实测是 95.55%，终端显示的 96% 是四舍五入来的，
  照显示值卡会立刻失败。

### 完成判据

- [x] wheel 里少文件时 `package` 作业确实变红（已用坏 wheel 实测，13 红）。
- [x] `extras` 装的就是 `pyproject` 声明的全部 extra，不存在「忘了同步」这种失败模式。
- [x] 覆盖率门槛在本地与 CI 生效，且实测不达标即失败。
- [x] 三条作业在全绿状态下跑通。

---

*以下为动手前的原始分析，保留备查。*

### 现状

仓库只有一个 workflow、一条作业、三步：`pip install -e ".[dev]"` →
`pytest tests/ -q` → 两条 ruff，45 秒跑完，矩阵 3.10 / 3.12 / 3.13。

三个漏口：

1. **从不构建 wheel。** `pip install -e` 与 `pythonpath = ["src"]` 都读源码树，
   于是「装出来的分发版能不能用」从来没被验证过。B-20 那 13 个
   `TemplateNotFound` 确实是 CI 抓到的，但严格说抓到的是 `.gitignore` 那一环；
   `[tool.setuptools.package-data]` 写错、wheel 里少了文件，照样能全绿溜过去。
2. **覆盖率不在 CI 里。** `pytest-cov` 装了，但没有 `--cov`、没有配置、
   没有 `fail_under`，96% 是本地手工测出来的数。
3. **`web` / `chart` / `data` 三组 extra 从没被 `pip install` 过。** CI 只装
   `[dev]`，而 `[dev]` 里有 fastapi / jinja2 / httpx 却故意没有 uvicorn，
   于是 `web = ["fastapi", "uvicorn", "jinja2"]` 这一行本身没人验。
   顺带：不装 plotly 时绘图用例静默跳过，那几行代码成了「看着测过」的样子。

### 要做什么

1. 新增 `package` 作业：构建 wheel，**不以可编辑方式**装进去，拿装出来的包
   跑一遍 `tests/test_web.py`——模板在不在 wheel 里，只有这条能证明。
2. 覆盖率接进 `test` 作业，门槛与理由写进 `pyproject.toml`。
3. 新增 `extras` 作业：装齐 `pyproject` 声明的每一个 extra，跑全量用例。

### 完成判据

- 三条作业各自能在「只坏它该管的那个东西」时变红。
- 新增一个 extra 而忘了在 CI 里装，应当有东西变红，而不是静静放过。

---

<a id="b-25"></a>

## B-25　`holdings chart` 的产图路径没有用例

**优先级** ✅ 已完成（2026-09-22）
**位置** `tests/test_chart_cmd.py`

### 完成情况

补了一条走完整命令的用例：跑 `holdings chart --output <tmp>`，断言图**真的写出来了**
（文件里有 `Plotly.newPlot`，且快照日期确实进了图里）、**说了写到哪儿**、
**并且请了浏览器打开**。

产图这条链路现在三个文件都是 100%：

| 文件 | 之前 | 现在 |
|------|------|------|
| `cli/commands/chart.py` | 82%（漏 30-32 行） | 100% |
| `cli/renderers/chart_renderer.py` | 67%（漏 `figure.write_html()`） | 100% |
| `services/chart_service.py` | 100% | 100% |

`webbrowser.open` 打了桩：不打桩时本地跑一次测试就弹一个浏览器窗口，
在 CI 上则是一个没人看、也没人发现失败的副作用。打桩后还能断言「它被调用了」，
把「忘了通知用户」也一起挡住。

**已实测这条用例真会红**：把 `write_html` 改成空操作，只有它失败
（1 failed, 8 passed），还原后 9 passed。

### 完成判据

- [x] 成功路径有用例：产物真的落盘，内容确为图表且含快照日期。
- [x] `webbrowser.open` 被断言调用过，测试不弹窗。
- [x] `chart.py` 与 `chart_renderer.py` 覆盖率到 100%。
- [x] 缺 plotly 时跳过（`requires_plotly`），与 `test_web.py` 同一套写法。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`holdings chart` 的**成功路径从没被跑通过**。`chart.py` 最后三行
（`write_html` / `echo("已生成图表：…")` / `webbrowser.open`）在测试里零执行，
现有用例只有两条错误路径：未来日期退 2、非法日期退 5。

画图**算**的部分覆盖得好（`chart_service` 100%），漏的是**落盘 + 通知用户**那一段。

### 要做什么

一条用例走完整命令，断言产物落盘、内容确为图表、并通知了用户。
`webbrowser.open` 必须打桩。

### 为什么要做

两个事实凑在一起才是问题：

- `pyproject.toml` 声明 `plotly>=5.0.0`，**没有上界**，实际装到的是 7.x（跨两个大版本）；
- 而调用 plotly 真实 API 的那一行，零覆盖。

于是 plotly 哪天改了 `write_html` 的签名或默认参数，CI 不会红，用户敲一下才发现。
这条风险不大但很具体，不是「为了覆盖率而覆盖率」。

> 这一项是 [B-24](#b-24) 的直接产物：B-24 让 CI 的 `test` 作业开始装
> `.[dev,chart]`，plotly 才真的在场。放在 B-24 之前，这条用例只会变成
> 一条天天被跳过的用例。

### 完成判据

- 一条用例走完整命令，断言产物真的落盘、内容确为图表、且通知了用户。
- 不用 plotly 的环境里该用例跳过，而不是失败。

---

<a id="b-26"></a>

## B-26　「一个功能一个 PR」没写在入口页

**优先级** ✅ 已完成（2026-09-22）
**位置** `CONTRIBUTING.md`、`docs/CODING_STANDARDS.md`

### 完成情况

规则本身一直写着（[合并粒度](CODING_STANDARDS.md#合并粒度一个功能一个-pr硬性要求)），
但只在 `docs/` 里：`CONTRIBUTING.md` 是新人和新会话最先打开的那一页，而它的
「提交 PR 前检查清单」里一个字都没提分支与 PR 的粒度。

- `CONTRIBUTING.md` 新增「分支与 PR 粒度」一节：一个工作项 = 一个分支 = 一个 PR、
  分支名与 PR 标题带条目编号、一个 PR 不跨工作项、CI 绿才合、合完删分支并同步
  `main`；检查清单加上对应的一条。
- **细则与理由不在两处各写一遍**：入口页只放可操作的那部分，并指向
  `CODING_STANDARDS.md`——同一段话写三遍，改的时候必然漏掉一处。
- 顺带修掉 `CODING_STANDARDS.md` 里被 [B-24](#b-24) 改陈旧的一句：CI 已经从
  「三个 Python 版本跑 pytest 与 ruff」变成三条作业。

### 完成判据

- [x] `CONTRIBUTING.md` 里能直接读到「一个工作项 = 一个分支 = 一个 PR」。
- [x] 两处对 CI 的描述与 `.github/workflows/ci.yml` 一致（三个作业）。
- [x] 规则全文仍只在 `CODING_STANDARDS.md` 一处。

---

*以下为动手前的原始分析，保留备查。*

### 现状

在全部 Markdown 里搜「一个 PR」，只命中 `CODING_STANDARDS.md` 与引用它的
`BACKLOG.md`；协作入口 `CONTRIBUTING.md` 完全没提，而它才是开工前会读的那一页。

### 要做什么

把可操作的那部分写进入口页，细则留在原处并给出链接；顺带核对两处对 CI 的描述
是否还准（[B-24](#b-24) 刚把 CI 从一条作业改成三条）。

### 完成判据

- 入口页能回答「这个 PR 该装几件事」。
- 没有同一段规则被抄成三份。

---

<a id="b-27"></a>

## B-27　对账单里认不出的行，不能静默跳过

**优先级** ✅ 已完成（2026-09-23）
**位置** `cli/commands/import_cmd.py`、`models/enums.py`

### 完成情况

一次提交，只定口径与报告，不碰分红摊销算法（那归 [B-23](#b-23)）。

**口径落成三种结局，而不是两种。** 改动前只有「入账」与「整批报错」，
这一项把中间那类拆了出来，三种结局的处置本来就是相反的：

| `trade_type` 的值 | 结局 | 为什么 |
|-------------------|------|--------|
| `BUY` / `SELL` / `FEE` | 入账 | 今天就支持 |
| 分红 / 送转 / 配股 / 银证转账 / 利息 | **不入账 + 逐行报出来** | 口径未支持，或与持仓无关 |
| 其余一切 | 整批拒绝、退出码 5 | 这是「这个值非法」 |

第三行**刻意保持原样**：把认不出的值也当成「不入账」放过，用户改错了文件却
什么都看不到；反过来把第二行也当成错误，一份正确的对账单就永远导不进来。

- 新增 `NonTradeType`（五类）与 `classify_trade_type()`，放在 `models/enums.py`。
  它返回三态（`TradeType` / `NonTradeType` / `None`），调用方必须区别对待——
  把「认不出」与「不入账」写在同一个返回值里，是这一项要防的那个坑。
- 别名表是**通用词表**（`股息` / `红利入账` / `送转股` / `利息归本`……），
  不是某一家券商的映射：券商自己那一列叫什么，归 [B-28](#b-28) 的解析器翻译。
- 不入账的行**不做逐列校验**。对账单里分红行常常没有数量与价格，因为
  「分红行没有数量」而整批失败，等于让一份正确的对账单永远导不进来。
- 结尾汇总固定三段：`识别 N 行，入账 M 笔，未入账 K 行`，未入账是 0 也照印
  ——「0」是被数出来的，不是没数。每条未入账的行单列一行，带行号、原始写法、
  归到哪一类、以及为什么不入账。

**`--strict` 的语义在这里定下来**：有未入账的行时一笔都不写、退出码 5。
条目只要求定退出码，写不写数据是顺带要定的——定为「一笔都不写」而不是
「先写进去再以非零码结束」，理由是 `import` 目前还没有幂等（[B-29](#b-29)）：
写了一半又以非零退出码结束，用户重跑一次就把账翻倍了。本命令的契约
本来就是整批校验、整批写入，这样定也与它一致。

**完成判据**

- [x] 一份含全部 5 类非买卖行的样本，导入后终端逐行列出「第 N 行 XX，未入账」，
      库中一笔不多 —— `tests/test_import_cmd.py::test_all_five_non_trade_rows_are_listed_and_none_is_posted`
      （断言汇总的 `识别 6 行，入账 1 笔，未入账 5 行`、五条行号逐条命中、
      以及库中只有那 1 笔买入）。
- [x] 分类表写进 `USER_GUIDE.md`（第 5 节的「哪些行会入账 / 不会入账」两张表），
      含不支持时用户会看到什么。
- [x] 有用例锁住「未入账的行数」与「报出的行号」——
      上面那条断言的是行号与条数本身，不是「命令没报错」；另有一条
      `test_an_unknown_trade_type_still_rejects_the_whole_batch` 守着三态里
      最容易被合并掉的那一态。

**顺带**：`_row_to_transaction` 的 `trade_type` 改由调用方传入——入账与否在
分拣时已经判过，函数里再解一次就会有第二个「什么算合法交易类型」的答案。
该函数余下几列的报错分支此前无用例，一并补上，`import_cmd.py` 覆盖率 100%。

---

*以下为动手前的原始分析，保留备查。*

### 现状

`TradeType` 只有 `BUY` / `SELL` / `FEE` 三个取值（`models/enums.py:22`）。而一份真实的
A 股对账单里，除买卖之外还会有：分红派息、送股/转增、配股、银证转账、利息。这些行
今天既表达不了，也**没有任何地方会报出来**——`import` 遇到不认识的 `trade_type` 确实会
抛错（`import_cmd.py:89`），但那是「这个值非法」，不是「这个值我们认识、只是暂不入账」；
两者的提示文案、退出码、以及用户能不能绕过，都不一样。

真正的风险在顺序上：**先写解析器、后定口径，结果一定是导入 92% 的行、然后静默错掉
剩下 8%**——而错的恰好是改成本价的那几行（送转当天数量与成本价同时变，见
[B-23](#b-23) 第 2 项）。用户看不出区别：命令退出码 0，数字看着也对。

### 要做什么

只定**最小口径**，不在这里写分红摊销算法：

1. 每一类非买卖行给出明确归属：**入账 → 映射成什么**，或 **不入账 → 怎么报出来**。
   默认必须是不入账 + 报出来，**不许静默跳过**；
2. `import` 的结尾汇总固定成三段：识别 N 行、入账 M 笔、**未入账 K 行（逐行列出行号与原因）**；
3. K > 0 时退出码是否非零在这里定下来（倾向：默认 0 但汇总必须醒目，`--strict` 时非零）。

分红与送股具体怎么摊销成本仍归 [B-23](#b-23) 第 2 项。本项只保证一件事：
**不支持的行不会被算成"导入成功"**。

### 完成判据

- 一份含全部 5 类非买卖行的样本，导入后终端逐行列出「第 N 行 XX，未入账」，库中一笔不多。
- 分类表写进 `USER_GUIDE.md`：哪些行支持、哪些不支持、不支持时会看到什么。
- 有用例锁住「未入账的行数」与「报出的行号」，避免以后被顺手改成静默跳过。

---

<a id="b-28"></a>

## B-28　券商流水导入：解析器注册表与识别

**优先级** P1 · `USER_STORIES.md` 用例 1 的直接缺口
**位置** 新增 `src/holdings/data/brokers/`、`cli/commands/import_cmd.py`

### 现状

`holdings import` 只认一种格式：全英文表头、UTF-8 的 CSV，五个必需列写死在
`import_cmd.py:14`。而券商真实导出的对账单在四个维度上都不同：

| 维度 | 今天的假设 | 真实情况 |
|------|-----------|---------|
| 编码 | UTF-8（`utf-8-sig`） | GBK / GB18030（Windows Excel 另存为），偶尔是带 BOM 的 UTF-16 |
| 表头 | 英文 | 中文，且各家叫法不同（`成交日期` / `发生日期` / `交易日期`） |
| 交易类型 | `BUY` / `SELL` | `证券买入` / `担保品划入` / `申购`……一个"买入"有若干种写法 |
| 费用 | 一列 `fee` | 佣金、印花税、过户费是**三列** |

换一家券商就要改一次源码——这正是「模块化增加不同证券公司」要解决的问题。

### 要做什么

- `data/brokers/` 下每家券商一个模块，实现同一套接口：`name`、`matches(表头, 样本)`、
  `parse(文本) -> 行列表`；
- 一个注册表把模块收进来；`--broker <名字>` 显式指定，不给则**自动识别**；
- **识别不出、或识别出多个时明确报错，不许猜**——猜错的代价是整批数字错，而用户
  会以为导成功了；
- 编码按 `BOM → 试 UTF-8 → 回落 GB18030` 的顺序探测。**顺序不能颠倒**：GB18030 几乎
  能解码任意字节序列（它有覆盖全码位的四字节形式），先试它会**把 UTF-8 文件解成乱码
  而不报错**；
- 逐行报错带行号，与今天 `_row_to_transaction` 的做法一致（`import_cmd.py:76`）。

**放进 `data/` 而不是新开一层**：`data` 已经是「外部世界 → 领域对象」的适配层，它
允许的导入集合（exceptions / models / utils）正好够解析器用，`tests/test_layering.py`
的 `ALLOWED_IMPORTS` 一个字都不用改。代价是要改文档里 `data/` 的定义——现在写的是
「只封装外部 API」，应改为「外部数据的适配器：API 与文件格式」，涉及 `ARCHITECTURE.md`、
`CODING_STANDARDS.md` 的三层分离表、`CONTRIBUTING.md` 的目录约定三处。**这三处随本项
一起改，不要提前改**：定义不该先于实现存在，那正是这个项目反复踩的那个坑。
等解析器超过五个、或需要自己的第三方依赖时，再升级成独立层。

**v1 只收 CSV。** 券商也常导出 `.xlsx` / `.xls`，但那要 `openpyxl` / `xlrd` 进依赖，
用户先另存为 CSV 即可；Excel 支持单独立项。

**不做第三方插件发现**（entry-points）。加一家券商 = 加一个模块 + 注册一行，够用；
`importlib.metadata` 那套的元数据陈旧问题在 B-20 前后已经坑过一次，而第三方券商包
现在还是个假设。真有人要，注册表的形状不用改。

### 完成判据

- [ ] 两个假券商夹具各能整批导入，`--broker` 与自动识别两条路都通。
- [ ] 拿一份表头陌生的样本，得到的是「识别不出，请用 `--broker` 指定」，而不是半批乱数据。
- [ ] 一份 GB18030 样本与一份 UTF-8 样本都能正确读入（各有用例）。
- [ ] 加第三家券商时，只新增一个模块 + 注册一行，`import_cmd.py` 与 `fetcher.py` 不改。

---

<a id="b-29"></a>

## B-29　同一个文件导两遍，账翻倍

**优先级** P2 · 会算错账，且今天就已经存在
**位置** `storage/db.py`、`storage/transaction_dao.py`、`services/trade_service.py`

### 现状

`holdings import` 没有幂等：同一个文件导两次就是全量入库两遍，持仓数量与成本价
直接翻倍。这**不是券商导入才有的问题**——通用 CSV 导入今天就是这样。

而对券商对账单来说它是必然撞上的：本月导出的文件包含上月最后几笔，逐月补充导出
就会重复。一个「帮你批量导入历史流水」的功能，如果会静默把账算成两倍，比没有这个
功能更糟。

### 要做什么

- 给 `transactions` 加两列：`source`（来源标识，如 `csv` / `huatai`）与 `external_id`
  （券商流水号，有则用）。走 `db.py:_migrate` 已备好的补列机制（`db.py:91`），老库
  打开时自动升级，不需要用户做任何事；
- 去重键：有 `external_id` 用 `(source, external_id)`；没有则回退到全字段指纹
  （日期 + 类型 + 数量 + 价格 + 费用 + 标的）；
- 默认行为：**发现重复即报错并列出行号**，由用户显式加 `--dedupe skip` 跳过。静默跳过
  与静默重复一样坏——一个少算一个多算，用户都看不出来。

### 完成判据

- [ ] 同一文件连导两次：第二次 0 笔入库、指出重复行号、退出码符合预期。
- [ ] 老库（没有这两列）打开后自动补列，已有数据不受影响。
- [ ] 通用 CSV 导入同样受益，有用例锁住。

---

<a id="b-30"></a>

## B-30　头两家券商的真实解析器

**优先级** P1（[B-28](#b-28) 的另一半）· **卡在样本上**
**位置** `data/brokers/`、`tests/fixtures/`

### 现状

没有样本。仓库里一份券商对账单都没有（`find . -name "*.csv"` 在 `docs/` 下没有命中），
`docs/demo/` 只有演示脚本与录像。**照着想象出来的格式写解析器，等于写一个只对假样本
成立的解析器**——这正是这个项目历史上反复出现的「文档先行、实现没跟上」的同一种错，
只是这次换成「解析器先行、样本没有」。

### 要做什么

1. 收两份及以上**真实且脱敏**的对账单，至少覆盖两家不同券商；格式差异越大越有价值
   （一家大型券商 + 一家互联网券商）；
2. 与用户核对：导入后的持仓数量与成本价，必须与券商 APP 上显示的对得上——**这是唯一
   有意义的验收**，用例绿不绿说明不了这件事；
3. 样本进 `tests/fixtures/`，脱敏规则写在文件头（账号、姓名、金额怎么替换），并确认
   脱敏后仍能触发该券商的全部分支（含 [B-27](#b-27) 那些非买卖行）。

### 完成判据

- [ ] 至少两家券商的真实样本能整批导入。
- [ ] 导入结果与券商 APP 的持仓数量、成本价一致（**逐标的核对，不是抽样**）。
- [ ] 夹具已脱敏，且脱敏后仍能触发该券商的全部分支。

---

<a id="b-31"></a>

## B-31　「股票信息」目前只有价格

**优先级** P2 · 能力缺口
**位置** 新增 `data/instrument.py`、`storage/asset_meta_dao.py`

### 现状

`data/` 取回来的 `PriceResult` 只有代码、价格、币种、来源（`fetcher.py:26`）。而「股票
信息」在真实使用中指的是**名称、市场、资产类型、币种**——`asset_meta` 表已经有
`name` / `market` / `currency` 三个字段（`db.py:39`），但除手工 `holdings meta` 之外，
没有任何东西能把它们填上。

「模块化配置」这一半也只做了一半：`data/sources.py` 的按配置顺序降级
（`priority_for` / `fetch_with_fallback`）**已经真的生效**，但上面还压着两处写死——
`get_fetcher` 的 `if market ==` 三分支（`fetcher.py:47`）与各市场模块里写死的源字典
（`a_stock.py:20`）。

### 要做什么

- 新增 `SymbolInfo` DTO：`symbol` / `name` / `market` / `asset_type` / `currency`；
- 多来源按配置顺序降级，**复用 `sources.fetch_with_fallback` 同一套**，不新造第二套
  降级逻辑——重试与退避的行为也就自动一致了；
- 结果落 `asset_meta` 做缓存，避免每次导入都联网；缓存新鲜度的语义参照 `price_cache`
  的 `cache_ttl_seconds`；
- 配置写在 `data_sources` 同一节下（如 `instrument_priority`），不另开一节。

### 完成判据

- [ ] 给一个代码能取回名称与市场；离线或取不到时**不报错，只是留空**——导入不能因为
      没网就做不了。
- [ ] 第二次取同一个代码走缓存、不发请求（有用例）。
- [ ] 加一个新来源只改配置与一个模块，降级逻辑不动。

---

<a id="b-32"></a>

## B-32　导入时只有代码，市场只能默认

**优先级** P2 · [B-28](#b-28) 与 [B-31](#b-31) 的接合处
**位置** `cli/commands/import_cmd.py`

### 现状

`import_cmd.py:84` 与 `:94` 里，`market` 缺省成 `A股`、`asset_type` 缺省成 `stock`。
券商 CSV 里通常只有代码，于是**整份对账单的市场都会被记成 A 股**——`report` / `sync`
据此取价，取不到就显示 `—`，用户得逐个用 `meta` 手工修。

另一半是账号：对账单天然带资金账号，而 `transactions.portfolio_group` 正好是干这个的
（`--group` 早就在了），但导入时只能给全批指定同一个，不能按账号分别落。

### 要做什么

- 导入时用 [B-31](#b-31) 按代码补全 `market` / `asset_type` / `name`；取不到时回落到今天
  的默认值，并**在汇总里说明有几行是靠默认值进来的**（不说明就等于把默认值当成了事实）；
- 从对账单里读资金账号落到 `portfolio_group`，一次导入可以落多个组合；
- **不碰** [B-21](#b-21) 的组合管理（重命名、合并、清单）——这里只负责把账号**落成**
  group，管理仍归 B-21。

### 完成判据

- [ ] 只写代码的 CSV 能导进来，且市场不再是清一色的默认值。
- [ ] 一份含两个资金账号的样本，导入后两个 group 各自筛得出来。
- [ ] 取不到资料时（离线）导入仍然成功，且提示里说清了哪些行用的是默认值。

---

<a id="b-33"></a>

## B-33　加一个市场要改 `get_fetcher` 的 if-chain

**优先级** P3 · 工程卫生
**位置** `data/fetcher.py`、`data/a_stock.py`、`data/us_stock.py`、`data/gold.py`

### 现状

`get_fetcher`（`fetcher.py:47`）是 `if market == A_SHARE / US_STOCK / GOLD` 的三分支
加一个 `raise`；每个市场模块内部又是一个写死的 `{"akshare": self._from_akshare, ...}`
字典。加港股要改这个函数，加一个源要改对应模块。

要说清楚的是：**取价链路已经比它看上去模块化**——`data_sources.priority` 真的生效，
降级、重试、退避也是三个市场共用的。写死的只有「有哪些源」和「哪个市场用哪个
fetcher」这一层。所以这是收尾，不是重写。

### 要做什么

把 [B-28](#b-28) 与 [B-31](#b-31) 用的同一套**注册表写法**搬过来：源按名字注册、
市场按名字注册，`get_fetcher` 退化成一次查表。**行为必须不变**——同样的源、同样的
优先级、同样的降级与重试。

两处**保持原样**：

- 黄金那条「不参与 `data_sources.priority`」的特殊路径（见 `gold.py` 的模块说明）
  是有意为之，不是待清理的硬编码；
- **先不抽公共基类。** 各域自建注册表、用同一套写法即可——这个项目已经吃过一次
  「先写通用件、结果没人用」的亏（[B-12](#b-12) 的零引用模块）。等第三个出现、
  形状确实一样，再抽。

### 完成判据

- [ ] 加一个市场或一个数据源，`fetcher.py` 一个字不改。
- [ ] 现有取价用例全绿且**一条都不用改**——这是「行为不变」的证据。
- [ ] 黄金的取路规则与「不读 priority」这点仍被用例锁住。

---

## 相关文档

- [架构与模块隔离规范](ARCHITECTURE.md) —— 铁律与当前执行情况
- [数据库设计说明](SCHEMA.md) —— `asset_meta` 与 `snapshots` 的字段定义
- [配置项字典](CONFIG_SPEC.md) —— 标注了哪些配置项尚未生效
- [错误码与异常处理规范](ERROR_HANDLING.md) —— 退出码契约
- [测试策略](TESTING_STRATEGY.md) —— 覆盖率目标与现状
- [详细开发路线图](ROADMAP.md) —— 里程碑划分
