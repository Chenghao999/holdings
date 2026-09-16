# 架构与模块隔离规范（ARCHITECTURE）

> 目标：确保每个功能**模块化独立、互相解耦**，任何模块的改动不影响其它模块。本文档给出带标注的目录结构、依赖方向与隔离铁律。

## 一、带标注的目录结构

```text
holdings/
├── src/
│   └── holdings/
│       │
│       ├── exceptions.py                    # 【基础层】全部自定义异常的基类，不 import 任何内部模块
│       │
│       ├── models/                          # 【基础层·无内部依赖】
│       │   ├── transaction.py               #    仅依赖 pydantic，不 import 任何项目内部模块
│       │   ├── snapshot.py                  #    定义与 storage 解耦的纯数据结构
│       │   ├── asset_meta.py                #    标的名称 / 币种 / 年化管理费率（仅展示用）
│       │   └── enums.py                     #    MarketType / AssetType / TradeType（含 FEE）
│       │
│       ├── utils/                           # 【基础层·无内部依赖】
│       │   ├── config.py                    #    只做 YAML 读写 + 默认值，不引用业务模块
│       │   ├── deps.py                      #    依赖包是否已安装的检测，纯函数
│       │   ├── currency.py                  #    汇率换算（预留），独立纯函数
│       │   └── formatter.py                 #    金额/百分比格式化，独立纯函数
│       │
│       ├── portfolio/                       # 【业务计算层·纯函数，零 IO】
│       │   ├── calculator.py                #    加权成本/盈亏/交易校验，只吃 models，不碰 storage/data
│       │   ├── allocator.py                 #    配置占比，独立
│       │   └── metrics.py                   #    年化/回撤/夏普，独立
│       │
│       ├── storage/                         # 【持久化层·只读写 DB，无业务计算】
│       │   ├── db.py                        #    连接/建表/迁移
│       │   ├── transaction_dao.py           #    交易 CRUD（含 add_many 单事务批量写）
│       │   ├── snapshot_dao.py              #    快照 CRUD
│       │   ├── asset_meta_dao.py            #    资产基础信息 CRUD
│       │   └── price_cache_dao.py           #    价格缓存 CRUD + TTL 新鲜度判断
│       │
│       ├── data/                            # 【数据获取层·只找外部 API，不碰 DB】
│       │   ├── fetcher.py                   #    工厂统一入口，同步/异步双接口
│       │   ├── sources.py                   #    按 data_sources.priority 依次尝试各源
│       │   ├── resilience.py                #    网络调用的超时（守护线程）与重试次数
│       │   ├── a_stock.py                   #    akshare / yfinance 两个源，顺序由配置决定
│       │   ├── us_stock.py                  #    yfinance 实现（单一数据源）
│       │   └── gold.py                      #    黄金：按代码选路，不参与优先级配置
│       │
│       ├── services/                        # 【编排层·唯一被 CLI/GUI 调用的入口】
│       │   ├── portfolio_service.py         #    编排 portfolio + storage + data
│       │   ├── report_service.py            #    快照 → 回撤 / 年化 / 夏普（口径不成立时给 None）
│       │   ├── snapshot_service.py          #    快照的记录与读取
│       │   ├── asset_meta_service.py        #    标的名称 / 币种 / 年化管理费率的读写
│       │   ├── chart_service.py             #    净值曲线：取数与筛日期（plotly 懒加载）
│       │   ├── trade_service.py             #    写入闸门：落库前的历史持仓校验
│       │   ├── sync_service.py              #    编排 data + storage
│       │   └── chart_service.py             #    编排 storage，返回 Figure/JSON
│       │
│       └── cli/                             # 【表现层·极薄，仅渲染输出】
│           ├── main.py                      #    click 入口组 + 异常→退出码映射
│           ├── dates.py                     #    日期参数的解析与校验，各命令共用
│           ├── commands/                    #    子命令：仅调用 service + 打印
│           │   ├── init.py    add.py     check.py    list.py    meta.py
│           │   ├── import_cmd.py  sync.py   report.py
│           │   └── snapshot.py  snapshots.py  chart.py  remove.py
│           └── renderers/                   #    把 Service 数据转为 Rich 表格/图表
│               ├── table_renderer.py
│               └── chart_renderer.py
│
├── data/                                    # 运行时产物（SQLite），不属于代码模块
├── snapshots/                               # 运行时产物（图表 HTML）
├── config.yaml                              # 用户配置
├── pyproject.toml
└── tests/                                   # 每个模块独立测试，互不依赖
                                             # 完整文件树与覆盖率见测试策略文档
```

> 新增/删除模块时**必须同步这棵树**。它是「代码实际长什么样」的索引，
> 一旦落后于代码，读者就分不清哪些是规范、哪些是历史。
> 测试目录的完整清单在 [TESTING_STRATEGY](TESTING_STRATEGY.md#测试目录约定)，
> 此处不重复维护一份必然走样的副本。

## 二、依赖方向（只能从上向下，禁止反向/跨层）

```text
cli (表现层)
  └── 只允许 import → services（以及 models / utils / exceptions 三个基础层）

services (编排层)
  └── 允许 import → portfolio / storage / data / models / utils

portfolio / storage / data (核心层，三者互相平行、互不依赖)
  ├── storage → models / utils
  ├── data    → utils （不碰 storage、不碰 portfolio）
  └── portfolio → models / utils （不碰 storage、不碰 data）

models / utils (基础层)
  └── 不 import 任何项目内部模块
```

## 三、隔离铁律（违反即构成耦合）

| # | 规则 | 目的 |
|---|------|------|
| 1 | `portfolio/`、`data/`、`storage/` **严禁** `print` / `click.echo` / `rich.print` | 保证三核心层与表现层无关，可被 GUI 复用 |
| 2 | `storage` 不依赖 `data`；`data` 不依赖 `storage` | 数据「存取」与「获取」彻底解耦，换数据源不动存储 |
| 3 | `cli` 不直接触碰 `storage` / `data` / `portfolio`，只经 `services` | 命令层可随意增删，不影响核心逻辑 |
| 4 | `services` 只做**编排**，不写具体 SQL、不发网络请求、不做算法 | 每个子模块可单独替换 |
| 5 | `models` / `utils` 保持零内部依赖 | 基础层稳定，向上兼容 |
| 6 | 返回值统一为 `dict` / `DataFrame` / `dataclass` / `pydantic` | 消除隐性共享可变状态 |

### 这六条铁律现在有用例守着

上面这张执行情况表此前只是**声明**：往 `portfolio/` 里写一句 `print`、给
`storage/` 加一个 `rich` 依赖，CI 不会有任何反应，直到真的去接 UI 的那一天
才发现核心层早就黏上了终端。

现在由 `tests/test_layering.py` 用 AST 守着（用 AST 不用文本匹配：注释里提到
`print` / `click` 是正常的，它们恰恰是在解释为什么不这么做）：

| 用例 | 守的是 |
|------|--------|
| `test_non_ui_layers_never_write_to_the_terminal` | 铁律 1：六个非表现层零 `print` / `echo` |
| `test_non_ui_layers_do_not_depend_on_terminal_libraries` | 非表现层不 import `rich` / `click` |
| `test_imports_follow_the_layer_diagram` | 上面「二、依赖方向」那幅图 |
| `test_cli_reaches_core_layers_only_through_services` | 铁律 3，含已知越界的精确清单 |
| `test_services_can_be_used_without_touching_the_cli` | 服务层可脱离 CLI 使用 |
| `test_core_layers_import_cleanly_without_the_cli_package` | 只 import 核心层不会把 click / rich 拖进来 |

最后一条是「可直接被 GUI / Web 复用」最直接的检验：在子进程里只 import 核心层，
然后检查 `sys.modules` 里没有 click / rich。

### 铁律的当前执行情况（2026-09-15 核对）

| # | 状态 | 说明 |
|---|------|------|
| 1 | ✅ | `portfolio/` `data/` `storage/` 三个核心层零 `print` / `click.echo` |
| 2 | ✅ | `data/` 与 `storage/` 之间无相互引用 |
| 3 | ✅ | 见下方：仅存一处**有理由的豁免** |
| 4 | ✅ | `services/` 内无裸 SQL、无网络请求 |
| 5 | ✅ | `models/` `utils/` 只 import `exceptions`，无业务模块依赖 |
| 6 | ✅ | |

**铁律 3 的唯一豁免**（`cli` 越过 `services` 直接触碰 `storage`）：

| 文件 | 直接引用 | 为什么是豁免而不是待办 |
|------|---------|----------------------|
| `cli/commands/init.py` | `storage.db.connect` | `init` 是引导命令，它要建的正是其它 service 赖以工作的数据库。为它包一层 service 是纯粹的形式主义 |

`snapshot` 一处已在 B-03 收口，`remove` 一处已在 B-11 收口（删除交易改经
`trade_service`——删除看起来不涉及校验，但绕过它，账本就有了第二条不受管的
写入路径）。`tests/test_layering.py` 的 `ALLOWED_CLI_CORE_TOUCHES` 只登记
`init` 一条，且断言的是**精确内容**：新增越界会红，修好一处不删名单行也会红。

## 四、模块职责 vs 禁止事项对照表

| 模块 | 该做什么 | 不该做什么 |
|------|---------|-----------|
| `models/` | 定义数据结构与枚举 | 不做计算、不读写文件、不 print |
| `utils/` | 通用纯函数与配置读写 | 不 import 业务模块、不联网 |
| `portfolio/` | 成本/盈亏/配比/指标纯计算 | 不读写 DB、不联网、不 print |
| `storage/` | SQLite 建表与 CRUD | 不计算盈亏、不拉行情、不 print |
| `data/` | 封装外部行情 API | 不写 DB、不算盈亏、不 print |
| `services/` | 跨模块编排、组装返回对象 | 不写 SQL、不发请求、不算算法 |
| `cli/` | 参数解析、调用 service、渲染 | 不写业务、不写 SQL、不发请求 |

## 五、独立性验证清单（写代码前的自查）

- [ ] 修改 `portfolio/calculator.py` 是否会影响 `data/` 或 `storage/`？——不该会。
- [ ] 换一个数据源（akshare → yfinance）是否需要改 `storage/`？——不该需要。
- [ ] 新增一个 CLI 命令是否需要改 `services/` 之外的核心层？——不该需要。
- [ ] 每个模块是否可单独 `import` 测试而不触发其它模块副作用？——应当可以。