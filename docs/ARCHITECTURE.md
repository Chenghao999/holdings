# 架构与模块隔离规范（ARCHITECTURE）

> 目标：确保每个功能**模块化独立、互相解耦**，任何模块的改动不影响其它模块。本文档给出带标注的目录结构、依赖方向与隔离铁律。

## 一、带标注的目录结构

```text
holdings/
├── src/
│   └── holdings/
│       │
│       ├── models/                          # 【基础层·无内部依赖】
│       │   ├── transaction.py               #    仅依赖 pydantic，不 import 任何项目内部模块
│       │   ├── snapshot.py                  #    定义与 storage 解耦的纯数据结构
│       │   └── enums.py                     #    MarketType / TradeType（含 FEE）
│       │
│       ├── utils/                           # 【基础层·无内部依赖】
│       │   ├── config.py                    #    只做 YAML 读写 + 默认值，不引用业务模块
│       │   ├── currency.py                  #    汇率换算（预留），独立纯函数
│       │   └── formatter.py                 #    金额/百分比格式化，独立纯函数
│       │
│       ├── portfolio/                       # 【业务计算层·纯函数，零 IO】
│       │   ├── calculator.py                #    加权成本/盈亏，只吃 models，不碰 storage/data
│       │   ├── allocator.py                 #    配置占比，独立
│       │   └── metrics.py                   #    年化/回撤/夏普，独立
│       │
│       ├── storage/                         # 【持久化层·只读写 DB，无业务计算】
│       │   ├── db.py                        #    连接/建表/迁移，只依赖 models + utils/config
│       │   ├── transaction_dao.py           #    交易 CRUD，只返回数据，不做计算
│       │   └── snapshot_dao.py              #    快照 CRUD
│       │
│       ├── data/                            # 【数据获取层·只找外部 API，不碰 DB】
│       │   ├── fetcher.py                   #    工厂统一入口，同步/异步双接口
│       │   ├── a_stock.py                   #    akshare 实现，含重试/降级
│       │   ├── us_stock.py                  #    yfinance 实现
│       │   └── gold.py                      #    黄金（国内现货优先，降级 GC=F）
│       │
│       ├── services/                        # 【编排层·唯一被 CLI/GUI 调用的入口】
│       │   ├── portfolio_service.py         #    编排 portfolio + storage + data
│       │   ├── sync_service.py              #    编排 data + storage
│       │   └── chart_service.py             #    编排 portfolio + storage，返回 Figure/JSON
│       │
│       └── cli/                             # 【表现层·极薄，仅渲染输出】
│           ├── main.py                      #    click 入口组，只转发到 services
│           ├── commands/                    #    子命令：仅调用 service + 打印
│           │   ├── add.py
│           │   ├── list.py
│           │   ├── sync.py
│           │   └── report.py
│           └── renderers/                   #    把 Service 数据转为 Rich 表格/图表
│               ├── table_renderer.py
│               └── chart_renderer.py
│
├── data/                                    # 运行时产物（SQLite），不属于代码模块
├── snapshots/                               # 运行时产物（图表 HTML）
├── config.yaml                              # 用户配置
├── pyproject.toml
└── tests/                                   # 每个模块独立测试，互不依赖
    ├── test_calculator.py
    └── test_fetcher_mock.py
```

## 二、依赖方向（只能从上向下，禁止反向/跨层）

```text
cli (表现层)
  └── 只允许 import → services

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