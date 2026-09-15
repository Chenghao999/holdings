# 配置项字典（CONFIG_SPEC）

> `holdings` 使用 `config.yaml` 作为用户配置，位于项目根目录。配置支持**读写**（未来 GUI 的设置界面依赖写入）。

## 配置文件位置与格式

- 路径：`config.yaml`
- 格式：YAML
- 解析库：`pyyaml`；加载/写入封装在 `utils/config.py`，提供 `load_config()` / `save_config()`。

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

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default_market` | string | `全部` | 未显式指定市场时的默认市场 |
| `cache_ttl_seconds` | integer | `300` | 价格缓存过期阈值（秒），控制 `price_cache` 的新鲜度 |
| `data_sources.priority` | map | 见上 | 各市场数据源优先级，决定降级顺序 |
| `sync.timeout_seconds` | integer | `10` | 单次网络请求超时时间 |
| `sync.retry_count` | integer | `1` | 超时后的重试次数 |
| `database_path` | string | `data/holdings.db` | SQLite 数据库文件路径 |
| `default_group` | string | `默认` | 新增交易的默认组合分组 |

## 配置读写约束

1. **必须支持写入**：`config.save()` 需能在运行期修改并持久化，供 GUI 设置界面使用。
2. 读取时若文件不存在，应生成带默认值的配置文件，并提示用户。
3. 字段取值非法（如 `cache_ttl_seconds` 为负数）应抛出 `ConfigError`（见 [ERROR_HANDLING.md](ERROR_HANDLING.md)）。

## 未来扩展预留

- `data_sources.priority` 为 map 结构，便于后续扩展更多市场（如港股）。
- 汇率换算相关的货币配置，在 `utils/currency.py` 中预留，MVP 暂不启用。