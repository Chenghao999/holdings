"""领域异常基类与退出码约定。

所有自定义异常都继承 `HoldingsError`，CLI 入口据此统一映射退出码，
契约见 docs/ERROR_HANDLING.md：

    1  数据源不可用 / 网络错误
    2  标的未找到
    3  配置错误
    4  数据库错误
    5  参数校验失败

实现模块（storage / data / utils）只从本模块导入异常类并对外重新导出，
以保证 `from holdings.storage.db import DatabaseError` 这类历史导入路径继续可用。

本模块**不得**导入包内其他任何模块：它是所有层的公共依赖，
一旦引入反向依赖就会形成循环导入，导致 `import holdings.data.fetcher` 整条失败。
"""

from __future__ import annotations


class HoldingsError(Exception):
    """所有 holdings 自定义异常的基类。

    CLI 入口只捕获这一个基类，再按具体类型决定退出码；
    新增异常时继承它即可自动获得统一的中文错误前缀。
    """


class DataSourceUnavailableError(HoldingsError):
    """数据源不可用、超时或未安装。"""


class SymbolNotFoundError(HoldingsError):
    """标的代码不存在或无法识别。"""


class ConfigError(HoldingsError):
    """配置文件缺失、格式错误或字段取值非法。"""


class DatabaseError(HoldingsError):
    """数据库读写失败。"""


class TradeValidationError(HoldingsError):
    """交易数据不合法，例如买入数量非正、卖出超过当时持有量。"""


class MissingDependencyError(HoldingsError):
    """某个可选依赖未安装，当前命令无法执行（如画图缺 plotly）。

    与 `DataSourceUnavailableError` 分开：那是网络/上游的问题，
    这是本机环境缺包，重试没有意义，提示必须给出可执行的安装命令。
    """
