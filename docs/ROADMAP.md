# 详细开发路线图（ROADMAP）

> 管理用户预期，标注当前进度。按季度 / 里程碑划分。

## 里程碑总览

| 版本 | 计划时间 | 实际状态 | 里程碑内容 |
|------|---------|---------|-----------|
| v0.1.0 | 2026 Q4 | ✅ 已发布（2026-09-15） | 基础 CRUD + 手动输入价格 |
| v0.2.0 | 2027 Q1 | ✅ 提前完成 | 集成 akshare 自动同步 + 报表 |
| v1.0.0 | 2027 Q2 | 🚧 进行中 | 稳定 CLI + 完整测试覆盖 |
| v2.0.0 | 2027 Q4 | ⏳ 未开始 | Textual GUI 预览版 |

> v0.1.0 与 v0.2.0 的全部内容已随 `0.1.0` 一并交付（见 [CHANGELOG](../CHANGELOG.md)）；v1.0.0 的 `snapshot` / `chart` 亦已提前实现，剩余工作是测试覆盖与交互打磨。

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

### 2027 Q2 —— v1.0.0（稳定 CLI）🚧

- [x] 实现 `holdings snapshot` 与 `holdings chart` 净值曲线。
- [x] 补齐单元测试，核心计算模块覆盖率达标（`calculator.py` 99%，目标 ≥ 90%）。
- [x] 稳定 CLI 交互，完善错误码与异常处理（入口点映射、参数校验、写入闸门已落地）。
- [ ] 修复工程体检剩余发现（见 [CHANGELOG](../CHANGELOG.md) 与体检报告）：
  - [ ] `asset_meta` 表接入 DAO 与展示，`portfolio/metrics.py` 接入 `report`
  - [ ] 4 个未生效的配置项（`default_market` / `data_sources.priority` /
        `sync.timeout_seconds` / `sync.retry_count`）接线或移除
  - [ ] 网络请求补超时；`data/` 层降级路径补测试
  - [ ] 配置项取值校验；`snapshot` 的 `--note` 持久化；`chart --start` 生效
  - [ ] 统一 `check --json` 与文本模式的退出码
- [ ] 用 `terminalizer` 录制演示 GIF，上传 GitHub。

### 2027 Q4 —— v2.0.0（GUI 预览）

- [ ] 基于 Textual 的 TUI 终端仪表盘预览版。
- [ ] GUI 直接复用 `services/` 层。

## 当前进度

- [x] v0.1.0 已发布（2026-09-15）。
- [x] v0.2.0 内容已随 v0.1.0 提前交付。
- [ ] v1.0.0 进行中：功能已齐，剩余测试覆盖、体检发现的修复与交互打磨。