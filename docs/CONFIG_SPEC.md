# 配置项字典（CONFIG_SPEC）

> `holdings` 使用 `config.yaml` 作为用户配置，位于项目根目录。

## 配置文件位置与格式

- 路径：`config.yaml`
- 格式：YAML
- 解析库：`pyyaml`；加载封装在 `utils/config.py` 的 `load_config()`，
  写入由返回的 `Config` 对象上的 `Config.save()` 完成。

> **`config.yaml` 由 `holdings init` 生成。** `load_config()` 在文件缺失时返回
> 一份内存里的默认配置且**不落盘**（避免任何命令的副作用都在磁盘上凭空造出文件）；
> 需要落盘请显式调用 `Config.save()`。

## 配置项清单

```yaml
# sync 未显式指定 --market 时的默认市场（可选值：A股 / 美股 / 黄金 / 全部）
default_market: 全部

# 价格缓存过期时间（秒）。默认 300 秒 = 5 分钟
cache_ttl_seconds: 300

# 各市场的数据源顺序（黄金不在此列，原因见下表）
data_sources:
  priority:
    A股: [akshare, yfinance]
    美股: [yfinance]

# 同步超时（秒）与重试次数
sync:
  timeout_seconds: 10
  retry_count: 1

# 数据目录（相对或绝对路径）
database_path: data/holdings.db

# 默认组合分组
default_group: 默认
```

## 字段含义

| 字段 | 类型 | 默认值 | 状态 | 说明 |
|------|------|--------|------|------|
| `default_market` | string | `全部` | ✅ 生效 | `sync` 未显式传 `--market` 时的默认市场。取值写错会按参数校验失败报错（退出码 `5`），而不是静默按「全部」跑 |
| `cache_ttl_seconds` | integer | `300` | ✅ 生效 | 价格缓存过期阈值（秒），控制 `price_cache` 的新鲜度 |
| `data_sources.priority` | map | 见上 | ✅ 生效 | 各市场按什么顺序尝试数据源。列表里没实现的源会被跳过；**黄金不读这一项**，见下 |
| `sync.timeout_seconds` | integer | `10` | ✅ 生效 | **每个标的**拉取行情的时间预算（秒）。预算用尽即放弃该标的、记成失败，不让 `sync` 挂死。写 `0` 或负数表示不限时 |
| `sync.retry_count` | integer | `1` | ✅ 生效 | A 股取价的**重试次数**（`1` = 首次失败后再试 1 次，共 2 次尝试）。重试之间退避 0.5 秒；用尽后降级 yfinance |
| `database_path` | string | `data/holdings.db` | ✅ 生效 | SQLite 数据库文件路径 |
| `default_group` | string | `默认` | ✅ 生效 | `add` / `import` 未传 `--group` 时的组合分组 |

> **`data_sources.priority` 对黄金无效，这是有意的。** 黄金的两个源是两种
> **不同的标的**：国内现货/ETF（如 `518880`）与国际 `GC=F`。它们不是彼此的
> 备份——`sync` 按**请求的代码**入库，把国内链路失败回退到国际金价，等于把
> 美元/盎司的报价（约 2000）存成一只人民币 ETF 的行情，数字差三个数量级且
> 看不出来。因此黄金由代码选路（写了 `GC=F` 就是要国际金价），配置里的
> `黄金:` 一项会被忽略。
>
> **超时的语义是「放弃等待」而非「取消请求」**：被放弃的那次请求仍会在后台
> 跑到它自己结束（Python 没有安全的线程取消机制），但命令会及时返回。
>
> **重试次数是「每个数据源各自」的**：`retry_count: 1` 且该市场配了两个源时，
> 上游全挂的极端情况下最多发起 4 次请求（每个源各 2 次尝试）。

## 配置读写约束

1. **必须支持写入**：`Config.save()` 需能在运行期修改并持久化，供未来的 GUI 设置界面使用。
   当前 CLI 未提供修改配置的命令，`config.yaml` 可由用户手工编辑（或删除后重新 `holdings init`）。
2. 读取时若文件不存在，返回默认配置，**不自动创建文件**（见上方说明）。
3. YAML 语法错误、根节点不是字典、文件不可读，均抛出 `ConfigError`（退出码 `3`）。
4. ⚠️ **字段取值暂未做校验**：`cache_ttl_seconds: -1` 或 `cache_ttl_seconds: abc`
   不会被 `load_config()` 拒绝，而是在命令读取该字段时才可能报错。
   这一项待补（见 [ROADMAP](ROADMAP.md)）。

## 未来扩展预留

- `data_sources.priority` 为 map 结构，便于后续扩展更多市场（如港股）。
- 汇率换算相关的货币配置：暂不预留。原先的占位模块 `utils/currency.py` 零调用，已删除（[B-12](BACKLOG.md#b-12)），需要时再加。
