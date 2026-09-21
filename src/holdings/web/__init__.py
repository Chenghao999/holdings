"""Web 界面层：FastAPI 只读看板。

与 `cli/`、`tui/` 平级的表现层，**三者互不 import**——各写各的界面，
共用同一套 `services/`。`tests/test_layering.py` 守着这条。
"""
