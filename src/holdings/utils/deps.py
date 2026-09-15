"""依赖包检测：检查运行与可选依赖是否已安装（纯函数，无 IO 输出）。"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

# 必需依赖：import 名 -> 包名
REQUIRED = {
    "click": "click",
    "rich": "rich",
    "pandas": "pandas",
    "pydantic": "pydantic",
    "yaml": "pyyaml",
    "numpy": "numpy",
}

# 可选依赖：import 名 -> 用途说明
OPTIONAL = {
    "akshare": "A股行情数据源（akshare）",
    "yfinance": "美股/黄金行情数据源（yfinance）",
    "plotly": "净值曲线图导出（plotly）",
    "pytest": "运行单元测试（pytest）",
}


@dataclass
class PackageStatus:
    """单个包的安装状态。"""

    import_name: str
    package_name: str
    installed: bool
    required: bool
    purpose: str = ""


def _is_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def check_dependencies() -> list[PackageStatus]:
    """返回所有依赖的安装状态。"""
    statuses: list[PackageStatus] = []
    for import_name, package_name in REQUIRED.items():
        statuses.append(
            PackageStatus(
                import_name=import_name,
                package_name=package_name,
                installed=_is_installed(import_name),
                required=True,
                purpose="必需",
            )
        )
    for import_name, purpose in OPTIONAL.items():
        statuses.append(
            PackageStatus(
                import_name=import_name,
                package_name=import_name,
                installed=_is_installed(import_name),
                required=False,
                purpose=purpose,
            )
        )
    return statuses


def missing_required() -> list[str]:
    """返回缺失的必需依赖包名（空列表表示全部就绪）。"""
    return [s.package_name for s in check_dependencies() if s.required and not s.installed]
