# 详细开发路线图（ROADMAP）

> 管理用户预期，标注当前进度。按季度 / 里程碑划分。

## 里程碑总览

| 版本 | 计划时间 | 实际状态 | 里程碑内容 |
|------|---------|---------|-----------|
| v0.1.0 | 2026 Q4 | ✅ 已发布（2026-09-15） | 基础 CRUD + 手动输入价格 |
| v0.2.0 | 2027 Q1 | ✅ 提前完成 | 集成 akshare 自动同步 + 报表 |
| v1.0.0 | 2027 Q2 | ✅ 已发布（2026-09-20） | 稳定 CLI + 完整测试覆盖 |
| v2.0.0 | 2027 Q4 | 🚧 进行中（TUI 与多币种已提前交付） | 界面与多币种 |

> v0.1.0 与 v0.2.0 的全部内容已随 `0.1.0` 一并交付，v1.0.0 的内容随 `1.0.0` 交付
> （见 [CHANGELOG](../CHANGELOG.md)）。三个里程碑都早于计划时间完成。

## 阶段性任务拆解

### 2026 Q4 —— v0.1.0（MVP：CRUD + 手动价格）✅

- [x] 搭建项目骨架（`pyproject.toml`、目录结构）。
- [x] 完成 `storage/db.py` 建表 + `models` 数据模型定义。
- [x] 实现 `holdings add`（含 `--fee`）与 `holdings list`。
- [x] 手动输入价格，跑通 CRUD。
- [x] 补齐 `README.md`、基础 `docs/` 文档。

### 2027 Q1 —— v0.2.0（数据接入 + 报表）✅

- [x] 集成 `akshare` 与 `yfinance`。
- [x] 实现 `holdings sync`（A 股降级 + 5 分钟缓存）。
- [x] 先支持黄金 ETF（`518880`）与贵州茅台（`600519`）测试。
- [x] 实现 `portfolio/calculator.py` 加权成本算法（含费用归集）。
- [x] 实现 `holdings report`：表格 + 配比表 + 费用汇总。

### 2027 Q2 —— v1.0.0（稳定 CLI）✅

- [x] 实现 `holdings snapshot` 与 `holdings chart` 净值曲线。
- [x] 补齐单元测试，核心计算模块覆盖率达标（`calculator.py` 99%，目标 ≥ 90%）。
- [x] 稳定 CLI 交互，完善错误码与异常处理（入口点映射、参数校验、写入闸门已落地）。
- [x] 清掉工程体检的剩余发现（12 项）与执行期间拆出的 3 项 ——
      **完整清单见 [待办清单（BACKLOG）](BACKLOG.md)**：
  - ✅ P1 已完成：`metrics.py` 接入 `report`（[B-02](BACKLOG.md#b-02)）、
        `asset_meta` 表接入（[B-01](BACKLOG.md#b-01)）
  - ✅ P2 已完成：网络超时与 4 个死配置项（[B-05](BACKLOG.md#b-05)）、
        无行情时的「−100%」误导（[B-06](BACKLOG.md#b-06)）、
        窄终端表格截断（[B-07](BACKLOG.md#b-07)）、
        报错格式与退出码统一（[B-08](BACKLOG.md#b-08)）、
        `snapshot --note` 持久化（[B-03](BACKLOG.md#b-03)）、
        `chart --start` 生效（[B-04](BACKLOG.md#b-04)）
  - ✅ 已提前做：UI 可复用性的守卫（[B-15](BACKLOG.md#b-15)，原属 v2.0.0 的前置条件）
  - ✅ P1 已完成：`asset_meta` 表接入（[B-01](BACKLOG.md#b-01)）
  - ✅ P3 已完成：`utils` / `data` 层测试缺口（[B-09](BACKLOG.md#b-09)、[B-10](BACKLOG.md#b-10)）、
        铁律 3 的剩余违反（[B-11](BACKLOG.md#b-11)）、零引用死代码（[B-12](BACKLOG.md#b-12)）、
        配置字段校验（[B-14](BACKLOG.md#b-14)）
- [x] 录制演示并放进 README（[B-18](BACKLOG.md#b-18)）——工具从 `vhs` 换成
      `asciinema` + `agg`（vhs 依赖 headless Chrome，本机起不来，详见 BACKLOG）。
      录制脚本与样例库在 [`docs/demo/`](demo/)。
- [x] 收尾发布：版本号到 `1.0.0`、CHANGELOG 收口、打 tag `v1.0.0`（[B-18](BACKLOG.md#b-18)）。
- [x] 清掉发布前扫出的两处「说了没做」：[B-16](BACKLOG.md#b-16)（删两个零引用 extra）、
      [B-17](BACKLOG.md#b-17)（删空壳参数 `init --dev`）。
- [x] 处理多币种混加（[B-19](BACKLOG.md#b-19)）——汇总改为只按人民币口径相加，
      非 CNY 标的如实排除并说明（汇率换算仍留到 v2.0.0）。

### 2027 Q4 —— v2.0.0（界面与多币种）

- [x] 基于 Textual 的 TUI 终端仪表盘预览版（[B-15](BACKLOG.md#b-15)）——
      持仓 + 报表两屏已可运行，数据全部来自 `services/`。
- [ ] Web 界面，只读看板起手（[B-20](BACKLOG.md#b-20)）。
- [x] 多币种：基准货币人民币，先在汇总里如实排除非 CNY 标的（[B-19](BACKLOG.md#b-19)）
      ——**已提前交付**，汇率换算仍待做。
- [ ] 多账户管理（[B-21](BACKLOG.md#b-21)）。
- [x] GUI 直接复用 `services/` 层 —— **前置条件已落实**：
      `tests/test_layering.py` 在 CI 里守着「核心层零输出、零终端依赖、
      依赖方向合规、只 import 核心层不会拖进 click / rich」。

## 当前进度

- [x] v0.1.0 已发布（2026-09-15）。
- [x] v0.2.0 内容已随 v0.1.0 提前交付。
- [x] v1.0.0 已发布（2026-09-20）：体检发现的 17 项与 [B-19](BACKLOG.md#b-19)（多币种混加）
      均已交付，收尾发布（版本号 / CHANGELOG 收口 / 演示录制 / 打 tag）见
      [B-18](BACKLOG.md#b-18)。
- [ ] v2.0.0 未开始：剩余 [B-20](BACKLOG.md#b-20)（Web）、[B-21](BACKLOG.md#b-21)（多账户）、
      [B-22](BACKLOG.md#b-22)（桌面端形态待定）、[B-23](BACKLOG.md#b-23)（基准对比 / 分红拆股 / 导出）。