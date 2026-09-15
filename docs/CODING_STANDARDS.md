# 代码风格与 Git 提交规范（CODING_STANDARDS）

## 代码风格

- 格式化与 lint 统一使用 **`ruff`**（替代 `black` / `flake8`）。
- 强制执行：
  - `ruff format .`：格式化代码。
  - `ruff check .`：静态检查。
- 提交代码前必须保证两者均无报错。

## 三层分离铁律（架构约束）

| 层 | 目录 | 约束 |
|----|------|------|
| 业务逻辑层 | `portfolio/` | **纯函数**，无 IO、无 `print` |
| 数据获取层 | `data/` | 只封装外部 API，无表现层输出 |
| 持久化层 | `storage/` | 只做 CRUD，返回数据对象 |
| 配置工具层 | `utils/` | 配置支持读写，无表现层输出 |

> `portfolio/`、`data/`、`storage/` 下**严禁**出现 `print`、`click.echo` 或 `rich.print`；所有返回必须是 `dict`、`DataFrame` 或 Pydantic / dataclass 对象。

## 类型与数据模型

- 统一使用 [pydantic](https://docs.pydantic.dev/)（v2）定义 DTO（数据传输对象）。
- Service 层返回值使用 `dataclass` / `pydantic` / `pandas.DataFrame`，供 CLI 与 GUI 复用。

## Git 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```text
<type>: <description>
```

### type 取值

| type | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: add sync command` |
| `fix` | 修复缺陷 | `fix: handle akshare timeout` |
| `docs` | 文档变更 | `docs: update user guide` |
| `refactor` | 重构（无功能变更） | `refactor: extract calculator` |
| `test` | 测试相关 | `test: add weighted cost tests` |
| `chore` | 构建/工具 | `chore: bump dependencies` |

### 提交信息要求

- 描述使用祈使句，首字母小写。
- 单一提交聚焦单一目的，避免混合多种改动。
- 破坏性变更需在 body 中标注 `BREAKING CHANGE:`。