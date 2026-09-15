# 用户手册（CLI 命令大全 / USER_GUIDE）

> 面向普通用户的命令使用说明。所有命令均支持 `--help` 查看完整选项。

## 环境准备

```bash
# 通过 uv 或 poetry 安装
uv sync --all-extras

# 首次使用前初始化（创建数据库与 config.yaml）
holdings init
```

初始化后会在项目目录生成 `data/holdings.db` 与 `config.yaml`。

---

## 命令详解

### 1. `holdings init`

初始化项目：创建数据库表与默认配置文件。

```bash
holdings init
holdings init --dev       # 开发/测试环境（可选）
```

---

### 2. `holdings add` —— 新增交易

支持交互式输入或全参数传入。

```bash
# 买入股票（含手续费）
holdings add --symbol 600519 --market A股 --type BUY --qty 100 --price 1680.5 --fee 5.0

# 买入黄金ETF
holdings add --symbol 518880 --market A股 --type BUY --qty 1000 --price 4.85

# 卖出
holdings add --symbol 600519 --market A股 --type SELL --qty 50 --price 1750.0

# 记录一笔基金托管费（trade_type=FEE）
holdings add --symbol 518880 --market A股 --type FEE --qty 0 --price 0 --fee 12.5 --notes "4月托管费"
```

| 参数 | 说明 |
|------|------|
| `--symbol` | 标的代码 |
| `--market` | 市场：`A股` / `美股` / `黄金` |
| `--type` | 类型：`BUY` / `SELL` / `FEE` |
| `--qty` | 数量（FEE 类型填 0） |
| `--price` | 单价（FEE 类型填 0） |
| `--fee` | 费用（佣金、印花税、托管费等） |
| `--notes` | 备注（可选） |

---

### 3. `holdings list` —— 查看持仓

```bash
# 查看全部持仓
holdings list

# 按盈亏率排序
holdings list --sort 盈亏率
```

---

### 4. `holdings import` —— CSV 批量导入

从支付宝 / 券商导出的 CSV 批量导入历史交易，支持费用列映射。

```bash
holdings import --file trades.csv --group 养老金 --fee-column 手续费
```

| 参数 | 说明 |
|------|------|
| `--file` | CSV 文件路径 |
| `--group` | 组合分组（如「养老金」「压岁钱」） |
| `--fee-column` | CSV 中的费用列名，映射到 `fee` 字段 |

---

### 5. `holdings sync` —— 同步最新价格

```bash
holdings sync --market 全部     # 也可指定 A股 / 美股 / 黄金
```

同步会更新 `price_cache` 与持仓市值。同一标的 5 分钟内不会重复请求网络。

---

### 6. `holdings report` —— 生成综合报表

```bash
holdings report --verbose
```

终端显示持仓表格、配置占比柱状图，并单独汇总费用支出。

---

### 7. `holdings snapshot` —— 记录资产快照

```bash
holdings snapshot --note "月度定投第12期"
```

用于净值追踪，写入 `snapshots` 表。

---

### 8. `holdings chart` —— 生成净值曲线图

```bash
holdings chart --output networth.html --start 2025-01-01
```

生成交互式 HTML，自动打开浏览器预览。

---

### 9. `holdings remove` —— 删除交易

```bash
holdings remove --id 3
```

需二次确认后删除指定 ID 的交易记录。