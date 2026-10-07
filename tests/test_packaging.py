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

import fnmatch
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
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"

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


def _workflow(path: pathlib.Path) -> dict:
    """解析一个 workflow 文件。

    YAML 1.1 会把裸 `on:` 读成布尔 `True`，所以取触发器要用 `_triggers()`，
    不能直接 `spec["on"]`——那是 None，看着像「这个 workflow 没有触发器」。
    """
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(spec: dict) -> dict:
    triggers = spec.get("on", spec.get(True))
    assert triggers is not None, "没解析到 on:，这个 workflow 不会被任何事件触发"
    return triggers


def _strings(node: object) -> list[str]:
    """把一份解析结果里所有的字符串摊平——用来在配置里找某个值的存在 / 不存在。"""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in _strings(value)]
    if isinstance(node, list):
        return [s for item in node for s in _strings(item)]
    return []


def test_the_release_workflow_fires_on_a_version_tag():
    """发布流程必须真的会被版本 tag 触发，且 tag 的形状与版本号对得上。

    **写错了不会有人告诉你**：GitHub 对不匹配任何分支 / tag 过滤器的 workflow
    既不报错也不警告——tag 推上去了，什么也没发生，而你以为发布正在进行。
    所以这里拿 `pyproject.toml` 里那个**真实的版本号**拼出 `v1.0.0` 去对过滤器，
    而不是把过滤器再抄一遍：抄一遍只能证明两处写得一样。
    """
    patterns = _triggers(_workflow(RELEASE_WORKFLOW))["push"]["tags"]
    tag = f"v{_pyproject()['project']['version']}"

    assert any(fnmatch.fnmatchcase(tag, pattern) for pattern in patterns), (
        f"tag `{tag}` 不匹配任何过滤器 {patterns}——推上去什么都不会发生"
    )


def test_the_release_workflow_stores_no_credential():
    """上传靠 OIDC，不靠存在仓库里的密钥。

    这条直接钉住 B-35 的一条判据「上传用的凭据不是长期 Entire-account token」。
    换回 `twine upload` 加一个 API token 的话，workflow 里必然出现一处取密钥的
    写法——那种做法要人手轮换、会过期、也会泄漏，而 OIDC 的令牌是一次性的。

    找的是**解析结果里的字符串**，不是文件全文：否则这段说明里提一句
    「别用 secrets」都会让它自己红。
    """
    spec = _workflow(RELEASE_WORKFLOW)
    leaked = [text for text in _strings(spec) if "secrets." in text]
    assert leaked == [], f"发布流程里出现了仓库密钥：{leaked}"

    publish = spec["jobs"]["publish"]
    assert publish.get("environment"), "publish 没绑 environment，拿不到 OIDC 令牌"
    assert publish["permissions"].get("id-token") == "write", (
        "缺 `id-token: write`——没有它 PyPI 认不出这次上传是谁，会被拒"
    )


def test_the_readme_teaches_installing_before_using():
    """README 的「快速开始」第一步必须是安装。

    README 同时是 PyPI 页面上的正文（wheel 元数据里就是
    `Description-Content-Type: text/markdown`），所以它归这个文件管。

    此前的快速开始**直接从 `holdings init` 开始，连安装那一步都没写**，
    而全仓库的文档都在让用户 `pip install 'holdings-cli[…]'`。照着 README 敲的
    人，第一行命令就会得到 `command not found`。

    比的是**位置**而不是「出现过 `pip install`」：安装写在文末的「常见问题」
    里一点用都没有。这里也**不检查**那段「尚未上传 PyPI」的说明——它是要被删掉
    的，而一条强制它留在原地的用例，会在删掉它之后逼着人把假话写回去。
    """
    text = README.read_text(encoding="utf-8")
    assert "## 快速开始" in text, "README 里没有「快速开始」这一节"

    section = text[text.index("## 快速开始") :]
    end = section.find("\n## ", 1)  # 下一个二级标题，避免把全文都算进来
    if end != -1:
        section = section[:end]

    install = section.find("pip install")
    run = section.find("holdings init")
    assert install != -1, "「快速开始」里没有安装步骤"
    assert run != -1, "「快速开始」里没找到 `holdings init`，多半是抓错段落了"
    assert install < run, "安装写在使用之后——用户第一眼看到的是 `holdings init`"
