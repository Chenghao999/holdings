"""holdings —— 个人投资持仓追踪工具。"""

from importlib.metadata import PackageNotFoundError, version

try:
    #: 版本号的唯一来源是打包元数据，也就是 `pyproject.toml` 的 `version`。
    #: 在这里另写一份常量等于同一个数有两个来源：发布时改一处漏一处，不会有
    #: 任何东西会响。`holdings --version`（`click.version_option`）读的也是这里，
    #: 两边说的必须是同一个版本。
    __version__ = version("holdings-cli")
except PackageNotFoundError:
    # 只有「源码树里直接 import、包没装过」才会走到这里（`pytest` 的
    # `pythonpath = ["src"]` 正是这种情形）。拿不到版本号就说拿不到，
    # 不能因此让 `import holdings` 本身失败。
    __version__ = "0.0.0+unknown"
