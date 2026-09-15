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
# 默认市场（可选值：A股 / 美股 / 黄金 / 全部）
default_market: 全部

# 价格缓存过期时间（秒）。默认 300 秒 = 5 分钟
cache_ttl_seconds: 300

# 数据源优先级与降级顺序
data_sources:
  priority:
    A股: [akshare, yfinance]
    美股: [yfinance]
    黄金: [akshare, yfinance]   # 国内现货/518880 优先，降级 GC=F

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
| `default_market` | string | `全部` | ⚠️ **尚未生效** | 规划中：未显式指定市场时的默认市场。当前 `sync` 的默认值是硬编码的「全部」 |
| `cache_ttl_seconds` | integer | `300` | ✅ 生效 | 价格缓存过期阈值（秒），控制 `price_cache` 的新鲜度 |
| `data_sources.priority` | map | 见上 | ⚠️ **尚未生效** | 规划中：各市场数据源优先级。当前的降级顺序硬编码在 `data/` 层的各 fetcher 里 |
| `sync.timeout_seconds` | integer | `10` | ⚠️ **尚未生效** | 规划中：单次网络请求超时。**当前代码没有任何超时设置** |
| `sync.retry_count` | integer | `1` | ⚠️ **尚未生效** | 规划中：重试次数。当前 A 股的重试次数硬编码为 1 次（`a_stock.py`），改这里没有效果 |
| `database_path` | string | `data/holdings.db` | ✅ 生效 | SQLite 数据库文件路径 |
| `default_group` | string | `默认` | ✅ 生效 | `add` / `import` 未传 `--group` 时的组合分组 |

> **标了「尚未生效」的 4 项请勿依赖**：它们会被正常解析并保留在配置对象上，
> 但没有任何代码读取，改动不会产生任何行为变化。降级与重试的真实逻辑见
> [FAQ](FAQ.md#数据同步)。这 4 项是作为结构预留保留的，接线工作见
> [ROADMAP](ROADMAP.md)。

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
- 汇率换算相关的货币配置，在 `utils/currency.py` 中预留，MVP 暂不启用。
