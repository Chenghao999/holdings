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

# 3. 初始化环境（创建数据库与 config.yaml）
.venv/bin/holdings init

# 4. 运行测试
.venv/bin/python -m pytest tests/
```

> 可选数据源：默认不装 `akshare` / `yfinance`（体积大、非必需）。
> 需要真实行情时执行 `.venv/bin/python -m pip install -e ".[data]"`。
> `chart` / `tui` / `web` 三组同理，按需安装（`web` 是 `pip install -e ".[web]"`，
> 装完即可 `holdings web` 打开只读看板）。

## 常用开发命令

| 命令 | 用途 |
|------|------|
| `.venv/bin/python -m pip install -e ".[dev]"` | 安装开发依赖 |
| `pytest tests/` | 运行全部单元测试 |
| `pytest tests/ --cov=holdings` | 运行测试并生成覆盖率报告（低于 95% 会失败，门槛在 `pyproject.toml`） |
| `ruff check .` | 代码规范检查 |
| `ruff format .` | 代码格式化 |
| `holdings --help` | 查看 CLI 命令 |

## 目录约定

核心代码位于 `src/holdings/`，分层如下（详见 README / 技术设计文档）：

- `services/`：统一服务层（GUI 与 CLI 共用）
- `cli/`：表现层（终端），极薄，仅渲染
- `models/`：Pydantic 数据模型
- `data/`：数据适配层（行情 API、券商对账单文件）
- `portfolio/`：业务逻辑层（纯计算，无 IO）
- `storage/`：持久化层（SQLite CRUD）
- `utils/`：工具函数

## 分支与 PR 粒度

**一个工作项 = 一个分支 = 一个 PR。** 分支从最新的 `main` 切出，分支名与 PR 标题都带上
条目编号（如 `b-03-snapshot-note` / `B-03: snapshot 的 --note 落库`）——清单、PR、
`git log` 三者据此互相追溯。

- **一个 PR 里可以有几个提交，但不跨工作项**：「实现 + 测试 + 文档」拆成几个提交是好的；
  把 B-03 与 B-06 塞进同一个 PR 则不行——那样的 PR 没法只批准一半，也没法只回滚一半。
- **CI 必须绿才合。** 挂了先修 CI，不要在红的基础上叠加。
- 合并后删掉分支，并把本地 `main` 同步到最新。

细则与理由（为什么要这么细）只在
[编码与提交规范](docs/CODING_STANDARDS.md#合并粒度一个功能一个-pr硬性要求) 里写一遍，
这里只放可操作的那部分；**提交**（而不是 PR）的粒度要求见该文件上一节。

## 提交 PR 前检查清单

1. 运行 `pytest tests/` 全部通过。
2. 运行 `ruff check .` 与 `ruff format .` 无报错。
3. 新增代码遵循三层分离铁律（业务层无 `print` / `click.echo` / `rich.print`）。
4. 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范（见 [CODING_STANDARDS.md](docs/CODING_STANDARDS.md)）。
5. 本 PR 只做一个工作项（见 [分支与 PR 粒度](#分支与-pr-粒度)）——混进了第二个条目，就把它拆出去再提。