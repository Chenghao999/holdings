"""源码树与分发包的完整性：该提交的文件真的提交了，该打进去的文件真的打进去了。

这一条守的是一类**本地测不出来**的故障：文件在磁盘上、测试全绿，
但它从没进过版本库或分发包，直到 CI 或用户那边才炸。

同一个坑这个仓库已经踩过两次（`.gitignore` 里两处都留着说明）：

- `data/` 曾把源码包 `src/holdings/data/` 一并排除，整个包没提交；
- `*.html` 曾把 `src/holdings/web/templates/*.html` 一并排除，
  本地跑得好好的，CI 上每一次请求都是 `TemplateNotFound`。

两次都是「一条通配规则匹配进了源码树」。所以这里不去逐条检查规则写得对不对，
而是**按结果断言**：`src/holdings/` 下的源码文件一个都不该被忽略。
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

import holdings

SRC = pathlib.Path(holdings.__file__).parent
ROOT = SRC.parent.parent

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
