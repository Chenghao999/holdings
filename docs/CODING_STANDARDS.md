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

### 提交粒度：一项改动一个提交（硬性要求）

**每一项独立的改动都要有自己的提交，不允许把多项改动攒成一个。** 具体到本项目的操作方式：

1. **BACKLOG 里的一个条目 = 至少一个提交**，提交信息带上条目编号
   （如 `fix: 给网络调用加超时 (B-05)`），便于在 PR 与 `git log` 里追溯。
   一个条目内部若有彼此独立、互不依赖的部分（如「加超时」与「接通
   数据源优先级」），拆成多个提交。
2. **文档变更单独成提交**：改代码的提交里不夹带文档改动；代码与配套文档
   可以相邻提交，但不要混在一次里。
3. **纯格式化、纯重命名、纯注释**各自独立，不与功能改动混在一起——
   否则 review 时真正的逻辑改动会被淹没在噪声里。
4. **一次提交必须是一次可独立回滚的最小单元**：任何一次提交都应该能单独
   `git revert` 而不牵连其它改动。

> 这条不是为了好看，是为了止损。**攒成一大坨未提交的改动，一旦方向要变
> （需求改了、判断错了），唯一的选择就是整片丢弃**——其中做对的部分也一起
> 没了，且没有任何中间状态可供对比。细粒度的提交让「退一半」成为可能。
> 未提交的改动越多，判断出错的代价越大。