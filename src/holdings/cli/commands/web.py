"""holdings web 命令：启动只读看板。

命令在这里，界面本体在 `holdings/web/`——两者是平级的表现层，都只经 `services/`
取数。与 `holdings tui` 同一套组织方式，好处是 Web 界面可以脱离 CLI 演进：
`create_app(db_path)` 本身不认 `click`，任何 ASGI 服务器都能挂它。
"""

from __future__ import annotations

import click


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="监听地址")
@click.option("--port", default=8420, show_default=True, type=int, help="监听端口")
def web_cmd(host: str, port: int) -> None:
    """启动只读看板（持仓 / 报表 / 净值曲线）。"""
    from holdings.utils.config import load_config

    # 缺依赖要按契约报（退出码 6），而不是漏一个 ImportError 出去——那会绕过
    # main() 的映射层，用户看到的只是裸 traceback。
    try:
        import uvicorn
    except ImportError as exc:
        from holdings.exceptions import MissingDependencyError

        raise MissingDependencyError(
            "未安装 fastapi / uvicorn，无法启动看板；请运行 pip install 'holdings[web]'"
        ) from exc

    from holdings.web.app import create_app

    app = create_app(load_config().database_path)
    # 不在这里 print 一行「已启动 http://…」：uvicorn 自己会打出真实的监听地址
    # （端口被占用时它打的是失败信息），再印一行只会在那种时候自相矛盾。
    uvicorn.run(app, host=host, port=port)
