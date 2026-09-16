"""配置的加载与写入（YAML）。

支持读/写，供 CLI 与未来 GUI 共用。
文件缺失时返回默认值，但仅在显式调用 save() 时落盘。
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from holdings.exceptions import ConfigError

DEFAULT_CONFIG: dict = {
    "default_market": "全部",
    "cache_ttl_seconds": 300,
    "data_sources": {
        # 各市场的数据源顺序。
        # **黄金故意不在此列**：它的两个源是两种不同的标的（国内现货/ETF 与
        # 国际 GC=F），不是彼此的备份，按优先级互相回退会把 GC=F 的价格存成
        # 518880 的行情。详见 data/gold.py 的模块说明。
        "priority": {
            "A股": ["akshare", "yfinance"],
            "美股": ["yfinance"],
        }
    },
    "sync": {"timeout_seconds": 10, "retry_count": 1},
    "database_path": "data/holdings.db",
    "default_group": "默认",
}

#: 已知字段的取值约束：(点号路径, 期望类型, 人类可读的说明)。
#: 放成一张表而不是一串 if：新增配置项时照着加一行，不容易漏。
_FIELD_RULES: tuple[tuple[str, str, str], ...] = (
    ("database_path", "str", "字符串"),
    ("default_group", "str", "字符串"),
    ("default_market", "str", "字符串"),
    ("cache_ttl_seconds", "non_negative_int", "非负整数"),
    ("sync.timeout_seconds", "non_negative_number", "非负数字"),
    ("sync.retry_count", "non_negative_int", "非负整数"),
)


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

    # 这两个属性此前各自做取值兜底（`timeout_seconds: abc` 回落到默认值）。
    # 现在 `load_config()` 会当场校验并抛 ConfigError，兜底就成了不可达代码——
    # 留着它反而会掩盖「配置被静默忽略」这件事。只留一套机制。
    @property
    def sync_timeout_seconds(self) -> float:
        return float(self.sync["timeout_seconds"])

    @property
    def sync_retry_count(self) -> int:
        return int(self.sync["retry_count"])

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
    # 必须深拷贝：`dict(DEFAULT_CONFIG)` 只复制了顶层，嵌套的 data_sources /
    # sync 仍是同一批对象，_deep_merge 会顺着它们就地改到模块级的
    # DEFAULT_CONFIG 上。后果是「加载过一次配置」这件事本身改变了此后所有
    # 加载得到的默认值——进程内（GUI、测试）尤其明显。
    data = copy.deepcopy(DEFAULT_CONFIG)
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
        _validate(loaded, cfg_path)
        _deep_merge(data, loaded)
    return Config(_data=data, _path=cfg_path)


def _validate(raw: dict, path: Path) -> None:
    """校验**取值**，不合法抛 ConfigError（退出码 3）。

    语法错误由 yaml 拦住了，但取值不合法此前会一路走到某条命令里才炸成裸
    traceback（退出码退化成 1），用户看到的是 `ValueError: invalid literal for
    int()`。配置错了就该按配置错误的契约当场报出来，并说清是哪个字段。

    只校验写进来的、且我们认识的字段；未知字段原样保留（用户可能给未来的版本
    或别的工具留着）。
    """
    for dotted, kind, expectation in _FIELD_RULES:
        present, value = _lookup(raw, dotted)
        if not present:
            continue
        if not _matches(value, kind):
            raise ConfigError(
                f"配置文件字段取值非法：{path} 的 {dotted} 应为{expectation}，当前为 {value!r}"
            )
    if "data_sources" in raw:
        _validate_priority(raw["data_sources"], path)


def _lookup(raw: dict, dotted: str) -> tuple[bool, object]:
    """按点号路径取值，返回 (是否存在, 值)。中间层不是字典时视为不存在。"""
    node: object = raw
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _matches(value: object, kind: str) -> bool:
    if kind == "str":
        return isinstance(value, str)
    if kind == "non_negative_int":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if kind == "non_negative_number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
    raise AssertionError(f"未知的校验类型：{kind}")


def _validate_priority(data_sources: object, path: Path) -> None:
    """`data_sources.priority` 是「市场 → 数据源名列表」。"""
    if not isinstance(data_sources, dict):
        raise ConfigError(f"配置文件字段取值非法：{path} 的 data_sources 应为映射")
    priority = data_sources.get("priority")
    if priority is None:
        return
    if not isinstance(priority, dict):
        raise ConfigError(f"配置文件字段取值非法：{path} 的 data_sources.priority 应为映射")
    for market, names in priority.items():
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise ConfigError(
                f"配置文件字段取值非法：{path} 的 data_sources.priority.{market} "
                f"应为字符串列表，当前为 {names!r}"
            )


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
