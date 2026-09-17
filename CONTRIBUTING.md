# 开发者环境搭建指南（CONTRIBUTING）

> 目标：让新人在 **5 分钟内**跑起开发环境。

## 前置要求

- Python ≥ 3.10（见 `pyproject.toml` 的 `requires-python`）。

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Chenghao999/holdings.git
cd holdings

# 2. 安装依赖（可编辑安装 + dev 可选组）
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"

# 3. 初始化开发环境（创建测试数据库与配置）
.venv/bin/holdings init --dev

# 4. 运行测试
.venv/bin/python -m pytest tests/
```

> 可选数据源：默认不装 `akshare` / `yfinance`（体积大、非必需）。
> 需要真实行情时执行 `.venv/bin/python -m pip install -e ".[data]"`。
> `chart` / `tui` 两组同理，按需安装。

## 常用开发命令

| 命令 | 用途 |
|------|------|
| `.venv/bin/python -m pip install -e ".[dev]"` | 安装开发依赖 |
| `pytest tests/` | 运行全部单元测试 |
| `pytest tests/ --cov=holdings` | 运行测试并生成覆盖率报告 |
| `ruff check .` | 代码规范检查 |
| `ruff format .` | 代码格式化 |
| `holdings --help` | 查看 CLI 命令 |

## 目录约定

核心代码位于 `src/holdings/`，分层如下（详见 README / 技术设计文档）：

- `services/`：统一服务层（GUI 与 CLI 共用）
- `cli/`：表现层（终端），极薄，仅渲染
- `models/`：Pydantic 数据模型
- `data/`：数据获取层（外部 API 封装）
- `portfolio/`：业务逻辑层（纯计算，无 IO）
- `storage/`：持久化层（SQLite CRUD）
- `utils/`：工具函数

## 提交 PR 前检查清单

1. 运行 `pytest tests/` 全部通过。
2. 运行 `ruff check .` 与 `ruff format .` 无报错。
3. 新增代码遵循三层分离铁律（业务层无 `print` / `click.echo` / `rich.print`）。
4. 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范（见 [CODING_STANDARDS.md](docs/CODING_STANDARDS.md)）。