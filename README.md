# holdings

> *A CLI-first investment tracking tool, architected for future GUI/Web extensions.*

`holdings` 是一款专为 Python 开发者设计的本地化投资管理命令行工具，旨在解决支付宝、券商 APP 数据分散、历史回溯困难的问题。

- **当前阶段（MVP）**：纯命令行交互，支持手动导入 + 自动同步价格，数据全量本地存储（SQLite）。
- **开源协议**：MIT
- **标签**：`#portfolio-cli` `#quant` `#python` `#akshare` `#yfinance`

---

## 核心特性

- 多市场持仓追踪：A 股 / 美股 / 黄金。
- 移动加权平均成本法：买入费用摊入成本、卖出保持成本价，手续费与托管费可逐笔记录并单独汇总。
- 本地 SQLite 存储，单文件便携，隐私安全。
- 价格自动同步：A 股优先 akshare、失败降级 yfinance，美股 / 国际黄金走 yfinance，带 5 分钟缓存防重复请求。
- 持仓盈亏报表、净值快照、交互式净值曲线。
- 严格三层架构，为未来的 GUI / Web 扩展预留接口。

---

## 快速开始

> 具体安装与使用步骤见 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)。

```bash
# 初始化项目（创建数据库、config.yaml）
holdings init

# 添加一笔交易（含手续费）
holdings add --symbol 600519 --market A股 --type BUY --qty 100 --price 1680.5 --fee 5.0

# 查看当前持仓（按盈亏率降序）
holdings list --sort 盈亏率

# 同步最新价格
holdings sync --market 全部
```

命令出错时统一以 `错误（N）：…` 的格式输出到 stderr，并按错误类型返回退出码
（`1` 网络 / 数据源、`2` 标的不存在、`3` 配置错误、`4` 数据库错误、`5` 参数或数据非法），
便于脚本判断。完整含义见 [错误码规范](docs/ERROR_HANDLING.md)。

---

## 完整文档索引

- [架构与模块隔离规范](docs/ARCHITECTURE.md)
- [项目愿景与范围](docs/VISION.md)
- [用户故事与用例](docs/USER_STORIES.md)
- [功能清单](docs/FEATURES.md)
- [数据库设计说明](docs/SCHEMA.md)
- [错误码与异常处理规范](docs/ERROR_HANDLING.md)
- [配置项字典](docs/CONFIG_SPEC.md)
- [开发者贡献指南](CONTRIBUTING.md)
- [代码风格与 Git 提交规范](docs/CODING_STANDARDS.md)
- [测试策略](docs/TESTING_STRATEGY.md)
- [用户手册（CLI 命令大全）](docs/USER_GUIDE.md)
- [常见问题（FAQ）](docs/FAQ.md)
- [详细开发路线图](docs/ROADMAP.md)
- [待办清单](docs/BACKLOG.md)
- [变更日志](CHANGELOG.md)