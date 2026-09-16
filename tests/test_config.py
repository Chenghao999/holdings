"""配置加载测试（utils 层此前零覆盖）。

重点锁两条：YAML 语法错误必须转成 ConfigError（否则退出码 3 的契约失效），
以及深合并要保留默认结构。
"""

from __future__ import annotations

import pytest

from holdings.exceptions import ConfigError
from holdings.utils.config import DEFAULT_CONFIG, load_config


def test_missing_file_returns_defaults(tmp_path):
    cfg = load_config(tmp_path / "nope.yaml")
    assert cfg.database_path == DEFAULT_CONFIG["database_path"]
    assert cfg.cache_ttl_seconds == 300


def test_missing_file_does_not_create_it(tmp_path):
    path = tmp_path / "nope.yaml"
    load_config(path)
    assert not path.exists()


def test_malformed_yaml_raises_config_error(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("database_path: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="配置文件格式错误"):
        load_config(path)


def test_malformed_yaml_message_stays_on_one_line(tmp_path):
    """PyYAML 的原始异常带整段出错现场，提示里只该留一行摘要。"""
    path = tmp_path / "config.yaml"
    path.write_text("database_path: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        load_config(path)
    assert len(str(excinfo.value).splitlines()) == 1


def test_non_mapping_document_raises_config_error(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="配置文件格式错误"):
        load_config(path)


def test_user_values_override_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("cache_ttl_seconds: 60\ndatabase_path: custom.db\n", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.cache_ttl_seconds == 60
    assert cfg.database_path == "custom.db"


def test_nested_merge_keeps_untouched_defaults(tmp_path):
    """只覆盖 data_sources.priority 的一项时，其余嵌套默认值必须还在。"""
    path = tmp_path / "config.yaml"
    path.write_text("data_sources:\n  priority:\n    美股: [yfinance]\n", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.data_sources["priority"]["美股"] == ["yfinance"]
    assert cfg.data_sources["priority"]["A股"] == DEFAULT_CONFIG["data_sources"]["priority"]["A股"]


def test_load_config_does_not_mutate_module_defaults(tmp_path):
    """深合并若原地改 DEFAULT_CONFIG，会把改动泄漏给后续所有调用。"""
    path = tmp_path / "config.yaml"
    path.write_text("cache_ttl_seconds: 7\n", encoding="utf-8")
    load_config(path)
    assert DEFAULT_CONFIG["cache_ttl_seconds"] == 300


def test_save_without_path_raises(tmp_path):
    cfg = load_config(tmp_path / "nope.yaml")
    cfg._path = None
    with pytest.raises(ConfigError, match="未指定配置文件路径"):
        cfg.save()


def test_save_then_reload_round_trips(tmp_path):
    path = tmp_path / "config.yaml"
    cfg = load_config(path)
    cfg.set("cache_ttl_seconds", 42)
    cfg.save()
    assert load_config(path).cache_ttl_seconds == 42


def test_loading_a_config_does_not_mutate_the_module_defaults(tmp_path):
    """加载配置不能改到全局 DEFAULT_CONFIG。

    `Config._data` 此前是 `dict(DEFAULT_CONFIG)` —— 浅拷贝。嵌套的
    `data_sources` / `sync` 仍是同一批对象，`_deep_merge` 会顺着它们就地改到
    模块级默认值上。于是「加载过一份配置」这件事本身改变了此后所有加载得到的
    默认值：同一进程内先读 A 再读 B，B 拿到的默认值已经被 A 污染过。
    CLI 每次只跑一条命令，看不出来；GUI 与测试里立刻现形。
    """
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n  priority:\n    A股: [sina]\n", encoding="utf-8"
    )

    load_config(tmp_path / "config.yaml")

    assert DEFAULT_CONFIG["data_sources"]["priority"]["A股"] == ["akshare", "yfinance"]


def test_two_consecutive_loads_are_independent(tmp_path):
    """同一进程里连续读两份配置，第二份不该继承第一份的残留。"""
    (tmp_path / "a.yaml").write_text("sync:\n  retry_count: 9\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("database_path: b.db\n", encoding="utf-8")

    first = load_config(tmp_path / "a.yaml")
    second = load_config(tmp_path / "b.yaml")

    assert first.sync_retry_count == 9
    assert second.sync_retry_count == 1, "b.yaml 没写 retry_count，应拿到默认值 1"


# --------------------------------------------------------------- 字段取值校验


def _write(tmp_path, body: str):
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "body",
    [
        "database_path: data/h.db\n",
        "default_group: 养老金\n",
        "default_market: 美股\n",
        "cache_ttl_seconds: 300\n",
        "cache_ttl_seconds: 0\n",
        "sync:\n  timeout_seconds: 0\n  retry_count: 0\n",
        "data_sources:\n  priority:\n    A股: [akshare, yfinance]\n",
    ],
)
def test_legal_values_are_accepted(tmp_path, body):
    cfg = load_config(_write(tmp_path, body))

    assert cfg.database_path


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ("cache_ttl_seconds: abc\n", "cache_ttl_seconds"),
        ("cache_ttl_seconds: -1\n", "cache_ttl_seconds"),
        ("database_path: [a, b]\n", "database_path"),
        ("default_group: 3\n", "default_group"),
        ("default_market: [美股]\n", "default_market"),
        ("sync:\n  timeout_seconds: abc\n", "sync.timeout_seconds"),
        ("sync:\n  timeout_seconds: -1\n", "sync.timeout_seconds"),
        ("sync:\n  retry_count: abc\n", "sync.retry_count"),
        ("sync:\n  retry_count: -1\n", "sync.retry_count"),
        ("data_sources:\n  priority: [akshare]\n", "data_sources.priority"),
        ("data_sources:\n  priority:\n    A股: akshare\n", "A股"),
        ("data_sources:\n  priority:\n    A股: [1, 2]\n", "A股"),
    ],
)
def test_illegal_values_raise_config_error(tmp_path, body, field):
    """取值不合法要当场按配置错误的契约报出来，并说清是哪个字段。

    此前它会一路走到某条命令里才炸成 `ValueError: invalid literal for int()`，
    退出码退化成 1，用户看到的是一段 traceback。
    """
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, body))

    assert field in str(exc.value)


def test_unknown_fields_are_kept(tmp_path):
    """只校验我们认识的字段。未知字段原样保留——用户可能给别的工具留着。"""
    cfg = load_config(_write(tmp_path, "some_future_option: 42\n"))

    assert cfg.get("some_future_option") == 42


def test_the_error_exits_3_without_a_traceback(tmp_path, monkeypatch, capsys):
    """端到端：这是 B-14 的判据。"""
    import sys

    from holdings.cli.main import main

    monkeypatch.chdir(tmp_path)
    _write(tmp_path, "cache_ttl_seconds: abc\n")
    monkeypatch.setattr(sys, "argv", ["holdings", "list"])

    try:
        main()
    except SystemExit as exc:
        code = int(exc.code or 0)
    else:
        code = 0

    err = capsys.readouterr().err
    assert code == 3
    assert "错误（3）：" in err
    assert "cache_ttl_seconds" in err
    assert "Traceback" not in err
