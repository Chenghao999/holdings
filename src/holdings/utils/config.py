"""配置的加载与写入（YAML）。

支持读/写，供 CLI 与未来 GUI 共用。
文件缺失时返回默认值，但仅在显式调用 save() 时落盘。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from holdings.exceptions import ConfigError

DEFAULT_CONFIG: dict = {
    "default_market": "全部",
    "cache_ttl_seconds": 300,
    "data_sources": {
        "priority": {
            "A股": ["akshare", "yfinance"],
            "美股": ["yfinance"],
            "黄金": ["akshare", "yfinance"],
        }
    },
    "sync": {"timeout_seconds": 10, "retry_count": 1},
    "database_path": "data/holdings.db",
    "default_group": "默认",
}


@dataclass
class Config:
    """配置对象，内部维护一份字典。"""

    _data: dict = field(default_factory=lambda: dict(DEFAULT_CONFIG))
    _path: Path | None = None

    # 便捷访问
    @property
    def default_market(self) -> str:
        return str(self._data["default_market"])

    @property
    def cache_ttl_seconds(self) -> int:
        return int(self._data["cache_ttl_seconds"])

    @property
    def database_path(self) -> str:
        return str(self._data["database_path"])

    @property
    def default_group(self) -> str:
        return str(self._data["default_group"])

    @property
    def data_sources(self) -> dict:
        return self._data["data_sources"]

    @property
    def sync(self) -> dict:
        return self._data["sync"]

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def to_dict(self) -> dict:
        return dict(self._data)

    def save(self) -> None:
        """将当前配置写入 YAML 文件（若未指定路径则写入默认位置）。"""
        if self._path is None:
            raise ConfigError("未指定配置文件路径，无法保存")
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, allow_unicode=True, sort_keys=False)


def _default_config_path() -> Path:
    return Path("config.yaml")


def load_config(path: str | os.PathLike | None = None) -> Config:
    """加载配置。文件不存在时返回默认配置（不落盘）。"""
    cfg_path = Path(path) if path else _default_config_path()
    data = dict(DEFAULT_CONFIG)
    if cfg_path.exists():
        try:
            raw = cfg_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(f"配置文件无法读取：{cfg_path}（{exc}）") from exc
        try:
            loaded = yaml.safe_load(raw) or {}
        except yaml.YAMLError as exc:
            # YAML 语法错误由 yaml 库自己先抛 ParserError，必须在这里转成 ConfigError，
            # 否则 CLI 拿不到「退出码 3」的契约，用户只会看到裸 traceback。
            raise ConfigError(f"配置文件格式错误：{cfg_path}（{_brief_yaml_error(exc)}）") from exc
        if not isinstance(loaded, dict):
            raise ConfigError(f"配置文件格式错误：{cfg_path}")
        _deep_merge(data, loaded)
    return Config(_data=data, _path=cfg_path)


def _brief_yaml_error(exc: yaml.YAMLError) -> str:
    """取 YAML 异常的一行摘要。

    PyYAML 的 str() 会把整段出错现场（前后若干行原文）都带上，
    直接塞进 CLI 提示会刷屏；这里只保留出错位置与原因。
    """
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None)
    if problem and mark is not None:
        return f"第 {mark.line + 1} 行第 {mark.column + 1} 列：{problem}"
    return str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__


def _deep_merge(base: dict, override: dict) -> None:
    """递归合并 override 到 base，保留 base 的默认结构。"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
