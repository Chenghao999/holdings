"""`utils/deps.py`：依赖检测。

`check` 命令直接依赖这三个函数，此前零测试。
"""

from __future__ import annotations

from holdings.utils import deps


def test_is_installed_for_a_package_that_cannot_exist():
    assert deps.is_installed("holdings_no_such_package_9f3a") is False


def test_is_installed_for_the_standard_library():
    assert deps.is_installed("json") is True


def test_check_dependencies_covers_every_declared_package():
    statuses = deps.check_dependencies()

    assert {s.import_name for s in statuses} == set(deps.REQUIRED) | set(deps.OPTIONAL)


def test_every_status_has_complete_fields():
    for status in deps.check_dependencies():
        assert status.package_name, "包名不能为空"
        assert isinstance(status.installed, bool)
        assert isinstance(status.required, bool)
        assert status.purpose, "必需与否都要有一句说明"


def test_package_name_can_differ_from_the_import_name():
    """`yaml` 的 pip 包名是 `pyyaml`——安装提示里给用户的是包名，不是 import 名。"""
    by_name = {s.import_name: s for s in deps.check_dependencies()}

    assert by_name["yaml"].package_name == "pyyaml"


def test_required_and_optional_are_marked_correctly():
    by_name = {s.import_name: s for s in deps.check_dependencies()}

    assert by_name["click"].required is True
    assert by_name["akshare"].required is False
    assert "akshare" in by_name["akshare"].purpose, "可选包的说明要带上是哪个包"


def test_missing_required_is_empty_when_everything_is_installed(monkeypatch):
    monkeypatch.setattr(deps, "is_installed", lambda _name: True)

    assert deps.missing_required() == []


def test_missing_required_names_the_missing_packages(monkeypatch):
    """`check` 命令靠它决定报哪些包名。"""
    monkeypatch.setattr(deps, "is_installed", lambda name: name != "pandas")

    assert deps.missing_required() == ["pandas"]


def test_missing_optional_packages_are_not_reported(monkeypatch):
    """可选包缺失不算缺依赖——只有必需包才该让 check 返回非零。"""
    monkeypatch.setattr(deps, "is_installed", lambda name: name in deps.REQUIRED or name == "click")

    assert deps.missing_required() == []
    assert any(not s.installed for s in deps.check_dependencies() if not s.required)
