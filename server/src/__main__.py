"""uvicorn 启动入口。

通过 `python -m src` 或 `python -m remote_agent_server` 启动服务。
"""

from __future__ import annotations

import logging

import uvicorn

from .app import create_app
from .utils.config import ServerConfig


def main() -> None:
    """启动 remote_agent_server 服务。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = ServerConfig.load()
    app = create_app(config)

    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
