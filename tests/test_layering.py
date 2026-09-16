"""分层铁律的可执行版本：把「UI 可复用」从口号变成 CI 里的红线。

VISION 的成功标准第 3 条写着「核心计算逻辑为纯函数，可直接被 GUI / Web 层复用」，
ARCHITECTURE 也列了六条铁律、逐条宣称已达成——但在此之前，**这些声明没有任何
用例守着**：往 `portfolio/` 里写一句 `print`、给 `storage/` 加一个 `rich` 依赖，
CI 不会有任何反应，直到真的去接 UI 的那一天才发现核心层早就黏上了终端。

本文件用 AST 检查而不是文本匹配：注释与文档字符串里出现 `print` / `click` 是
正常的（它们恰恰是在解释为什么不这么做），文本匹配会把这些说明也判成违反。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import holdings

SRC = pathlib.Path(holdings.__file__).parent

#: 各层允许 import 的 holdings 子包。同层内部的 import 一律允许。
#: 这张表就是 ARCHITECTURE 「二、依赖方向」那幅图的可执行版本。
ALLOWED_IMPORTS: dict[str, set[str]] = {
    "exceptions": set(),
    "models": {"exceptions"},
    "utils": {"exceptions"},
    "portfolio": {"exceptions", "models", "utils"},
    "storage": {"exceptions", "models", "utils"},
    "data": {"exceptions", "models", "utils"},
    "services": {"exceptions", "models", "utils", "portfolio", "storage", "data"},
    # 表现层只经 services 触碰核心层；utils / models / exceptions 是基础层，
    # 任何层都可以直接取用（命令解析配置、构造 DTO 都要用）。
    # 已知的越界由 ALLOWED_CLI_CORE_TOUCHES 给出，见下方拼装。
    "cli": {"exceptions", "models", "utils", "services"},
}

#: cli 已知的直接触碰核心层之处。这是一份**待办镜像**而不是许可证：
#: 用例断言「实际违反集合 == 这份名单」，因此既拦得住新违反，也逼着名单
#: 随修复一起缩小——修好一处却不删这一行，用例会红。
ALLOWED_CLI_CORE_TOUCHES: set[tuple[str, str]] = {
    # 唯一的豁免：引导命令，它要建的正是其它 service 赖以工作的数据库。
    # ARCHITECTURE 的「铁律 3 执行情况」把它记为例外条款，不是待办。
    ("commands/init.py", "storage"),
}

#: cli 的允许集合：基础层 + services，再加上明确登记过的越界。
#: 越界只能从 `ALLOWED_CLI_CORE_TOUCHES` 那一处来，因此「偷偷放行」要让
#: 那个集合变大，而 `test_cli_reaches_core_layers_only_through_services`
#: 断言的是它的精确内容——两处对不上就会红。
ALLOWED_IMPORTS["cli"] |= {imported for _file, imported in ALLOWED_CLI_CORE_TOUCHES}

#: 核心层与编排层：这些层要被 UI 复用，不许有任何表现层行为。
NON_UI_LAYERS = ("portfolio", "storage", "data", "services", "models", "utils")


def _modules(layer: str) -> list[pathlib.Path]:
    """该层的所有 Python 文件。`exceptions` 是单文件，其余都是包。"""
    package = SRC / layer
    if package.is_dir():
        return sorted(package.rglob("*.py"))
    single = SRC / f"{layer}.py"
    return [single] if single.exists() else []


def _relative(path: pathlib.Path) -> str:
    return path.relative_to(SRC).as_posix()


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_layers(path: pathlib.Path) -> set[str]:
    """该文件 import 了哪些 holdings 子包（只看第二段，如 `holdings.storage`）。"""
    layers = set()
    for node in ast.walk(_tree(path)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        layers.update(n.split(".")[1] for n in names if n.startswith("holdings."))
    return layers


def _output_calls(path: pathlib.Path) -> list[str]:
    """文件里调用了哪些「往外输出」的函数（`print` / `xxx.print` / `echo`）。"""
    found = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name in {"print", "echo"}:
            found.append(name)
    return found


def _ui_imports(path: pathlib.Path) -> set[str]:
    """文件 import 了哪些终端/表现层库。"""
    ui = set()
    for node in ast.walk(_tree(path)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        ui.update(n.split(".")[0] for n in names if n.split(".")[0] in {"rich", "click"})
    return ui


# --------------------------------------------------------------- 自我校验


def test_the_guard_actually_looks_at_files():
    """防止「路径写错 → 什么都没扫到 → 一路绿灯」这种假通过。"""
    for layer in ALLOWED_IMPORTS:
        assert _modules(layer), f"没扫到 {layer}/ 下的任何文件，路径多半写错了"


# ------------------------------------------------- 核心层与编排层的纯度


@pytest.mark.parametrize("layer", NON_UI_LAYERS)
def test_non_ui_layers_never_write_to_the_terminal(layer):
    """铁律 1：这些层不许有 `print` / `click.echo` 等任何输出。

    UI 要复用的是它们的返回值；一旦这里往外打印，接 UI 时就会多出一堆
    没人想要的控制台噪声，而且没办法从外部关掉。
    """
    offenders = [
        f"{_relative(path)}: {name}()" for path in _modules(layer) for name in _output_calls(path)
    ]

    assert offenders == [], f"这些地方在往终端输出：{offenders}"


@pytest.mark.parametrize("layer", NON_UI_LAYERS)
def test_non_ui_layers_do_not_depend_on_terminal_libraries(layer):
    """这些层不许 import `rich` / `click`。

    依赖一旦进来，装 UI 的人就得连终端渲染库一起装；反过来，将来换成
    Web 或桌面端时也没法把它们摘掉。终端相关的库只该出现在 `cli/`。
    """
    offenders = [
        f"{_relative(path)}: {sorted(_ui_imports(path))}"
        for path in _modules(layer)
        if _ui_imports(path)
    ]

    assert offenders == [], f"这些地方 import 了终端库：{offenders}"


# --------------------------------------------------------------- 依赖方向


@pytest.mark.parametrize("layer", sorted(ALLOWED_IMPORTS))
def test_imports_follow_the_layer_diagram(layer):
    """ARCHITECTURE「二、依赖方向」的可执行版本。

    反向或跨层 import 是循环依赖与「改一处动全身」的源头。
    """
    allowed = ALLOWED_IMPORTS[layer]
    offenders = [
        f"{_relative(path)} → holdings.{imported}"
        for path in _modules(layer)
        for imported in _imported_layers(path)
        if imported != layer and imported not in allowed
    ]

    assert offenders == [], f"{layer} 层出现了越界 import：{offenders}"


def test_cli_reaches_core_layers_only_through_services():
    """铁律 3：`cli` 不直接触碰 `storage` / `data` / `portfolio`。

    允许清单里既记着合理豁免（`init`），也记着待办（`remove`，见 B-11）。
    断言的是**相等**而不是「包含」：修好一处就删一行，名单不会烂在原地。
    """
    core = {"storage", "data", "portfolio"}
    actual = {
        (_relative(path).removeprefix("cli/"), imported)
        for path in _modules("cli")
        for imported in _imported_layers(path)
        if imported in core
    }

    assert actual == ALLOWED_CLI_CORE_TOUCHES, (
        "cli 直接触碰核心层的清单变了。新增的越界要改回经 services 调用；"
        "已修好的请从 ALLOWED_CLI_CORE_TOUCHES 里删掉对应行。"
    )


# --------------------------------------------------------------- 可复用性


def test_services_can_be_used_without_touching_the_cli():
    """服务层必须能在不 import 任何 CLI 代码的前提下取用。

    这条正是「同一套 Service 层从 CLI 演进到 TUI / Web」成立的前提：
    未来的界面只需要 import services，不该被拖进 click 命令树。
    """
    offenders = [
        f"{_relative(path)} → holdings.{imported}"
        for path in _modules("services")
        for imported in _imported_layers(path)
        if imported == "cli"
    ]

    assert offenders == [], f"服务层反向依赖了 cli：{offenders}"


def test_core_layers_import_cleanly_without_the_cli_package():
    """核心层模块单独 import 不应触发 click / rich 的加载。

    这是「可直接被 GUI / Web 复用」的最直接检验：解释器里没装 click
    也应当能算成本、读数据库。
    """
    import subprocess
    import sys

    probe = (
        "import sys;"
        "import holdings.portfolio.calculator, holdings.portfolio.metrics,"
        "holdings.storage.db, holdings.data.fetcher, holdings.services.portfolio_service;"
        "loaded = sorted(m for m in sys.modules if m.split('.')[0] in {'click', 'rich'});"
        "print(','.join(loaded))"
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=SRC.parent.parent,  # 仓库根，保证 pythonpath 生效
    )

    assert result.stdout.strip() == "", f"核心层把终端库带进来了：{result.stdout.strip()}"
