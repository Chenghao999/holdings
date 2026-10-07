"""源码树与分发包的完整性：该提交的文件真的提交了，该打进去的文件真的打进去了。

这一条守的是一类**本地测不出来**的故障：文件在磁盘上、测试全绿，
但它从没进过版本库或分发包，直到 CI 或用户那边才炸。

同一个坑这个仓库已经踩过两次（`.gitignore` 里两处都留着说明）：

- `data/` 曾把源码包 `src/holdings/data/` 一并排除，整个包没提交；
- `*.html` 曾把 `src/holdings/web/templates/*.html` 一并排除，
  本地跑得好好的，CI 上每一次请求都是 `TemplateNotFound`。

两次都是「一条通配规则匹配进了源码树」。所以这里不去逐条检查规则写得对不对，
而是**按结果断言**：`src/holdings/` 下的源码文件一个都不该被忽略。

`pyproject.toml` 的元数据也归这里（见本文件后半），理由是同一条：
它们是**只在别人拿到分发包时才被读到**的东西。写错了本地一切照常，
PyPI 页面上是一片空白，或者更糟——把用户引到别人的仓库去（B-34 的另一半）。
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest
import yaml

import holdings

try:  # Python 3.10 没有 tomllib
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

SRC = pathlib.Path(holdings.__file__).parent
ROOT = SRC.parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

#: 会被 git 忽略、也确实不该提交的东西，不进这项检查。
_SKIP_DIRS = {"__pycache__"}
#: 只检查真正属于源码的后缀。`.pyc` 之类由上面那行覆盖。
_SOURCE_SUFFIXES = {".py", ".html"}

requires_git = pytest.mark.skipif(
    subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        capture_output=True,
    ).returncode
    != 0,
    reason="需要 git 工作区（这项检查问的就是「这些文件进没进版本库」）",
)


def _source_files() -> list[str]:
    return sorted(
        path.relative_to(ROOT).as_posix()
        for path in SRC.rglob("*")
        if path.is_file() and path.suffix in _SOURCE_SUFFIXES and not _SKIP_DIRS & set(path.parts)
    )


@requires_git
def test_no_source_file_is_swallowed_by_gitignore():
    """`src/holdings/` 下的源码必须全都能被 git 看见。

    被测的对象是 `.gitignore` 的**效果**而不是它的文本：规则可以随便写，
    只要没有源码文件被它挡住。
    """
    files = _source_files()
    assert files, "没扫到任何源码文件，路径多半写错了"

    # `--stdin` 把被忽略的那些逐行打出来；退出码 1 表示一个都没有，属于正常结果。
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=ROOT,
        input="\n".join(files),
        capture_output=True,
        text=True,
        check=False,
    )
    ignored = [line for line in result.stdout.splitlines() if line.strip()]

    assert ignored == [], f"这些源码文件被 .gitignore 挡住了，不会进版本库：{ignored}"


@requires_git
def test_the_web_templates_are_tracked():
    """模板是 web 层的代码，必须进版本库。

    比上一条更直接地对着踩过的坑：即便将来 `.gitignore` 换了写法，
    这一条也要求那几个 `.html` 真的在 `git ls-files` 里。
    """
    templates = sorted((SRC / "web" / "templates").glob("*.html"))
    assert templates, "没扫到模板文件，路径多半写错了"

    tracked = subprocess.run(
        ["git", "ls-files", "src/holdings/web/templates"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    missing = [p.name for p in templates if p.relative_to(ROOT).as_posix() not in tracked]
    assert missing == [], f"这些模板没有进版本库：{missing}"


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _repository_slugs() -> list[str]:
    """工作区里每个远端地址的 `owner/repo`。

    `https://github.com/owner/repo.git` 与 `git@github.com:owner/repo.git`
    两种写法都认：取末尾两段，与协议无关。
    """
    result = subprocess.run(
        ["git", "remote", "-v"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    slugs = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or ("://" not in parts[1] and "@" not in parts[1]):
            continue  # 本地路径形式的 remote 没有 owner/repo 可言
        match = re.search(r"([^/:\s]+)/([^/\s]+?)(?:\.git)?$", parts[1])
        if match:
            slugs.add(f"{match.group(1)}/{match.group(2)}")
    return sorted(slugs)


@requires_git
def test_the_project_urls_point_at_this_repository():
    """PyPI 项目页上那三个链接必须指向本仓库。

    **这是 B-34 的另一半**：那一次修的是 `pip install` 里的名字把人带到别人的
    同名包去，这里修的是页面上的 Homepage / Repository / Issues。元数据通常是从
    模板或别的项目抄来的，抄漏一处就把用户引到别处——而 wheel 照样构建成功、
    `twine check` 照样通过，**没有任何东西会响**。

    对的是 `git remote` 里的地址，不是把 URL 再抄一遍：抄一遍只能证明「这两处
    写的一样」，证明不了它指对了地方。

    在 fork 里跑这条会红（远端是你的 fork，而 URL 该指向上游）。那是**对的**：
    贡献者不该把自己的仓库地址改进 `pyproject.toml`。
    """
    slugs = _repository_slugs()
    if not slugs:
        pytest.skip("这个工作区没配远端（多半是解压出来的源码包），无从比对")

    urls = _pyproject()["project"].get("urls", {})
    assert urls, "pyproject 里没有 [project.urls]，PyPI 页面上会一个链接都没有"

    wrong = {name: url for name, url in urls.items() if not any(s in url for s in slugs)}
    assert wrong == {}, f"这些链接没指向本仓库 {slugs}：{wrong}"


def test_the_declared_python_versions_are_the_ones_ci_tests():
    """`classifiers` 声明的版本必须与 CI 矩阵跑的版本**完全一致**。

    「支持 Python 3.x」是给用户看的承诺，而承诺的证据只有 CI 上真跑过。
    两个方向都会出事，所以这条是双向的：

    - 声明了却没测 → 用户在某个你从没验过的版本组合上踩坑；
    - 测了却没声明 → PyPI 上少一个版本号，按版本搜索的人不认为你支持它。

    真发生过的正是第二种：矩阵里跳过了 3.11，而 `requires-python` 写着 `>=3.10`
    ——一边说支持，一边从没跑过。
    """
    declared = {
        classifier.rsplit(" :: ", 1)[1]
        for classifier in _pyproject()["project"]["classifiers"]
        if classifier.startswith("Programming Language :: Python :: 3.")
    }
    # `yaml` 是运行期依赖（`pyyaml`），读 workflow 不必为它再进一个 dev 依赖。
    # 注意 YAML 1.1 会把裸 `on:` 读成布尔 `True`——这里只碰 `jobs`，不受影响。
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    tested = set(workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"])

    assert declared == tested, (
        f"pyproject 声明 {sorted(declared)}，CI 只跑 {sorted(tested)}；"
        f"只在声明里：{sorted(declared - tested)}；只在 CI 里：{sorted(tested - declared)}"
    )
