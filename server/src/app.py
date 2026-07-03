"""FastAPI 应用与路由注册。

创建应用实例、初始化鉴权与服务层、注册路由、配置全局异常处理器。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .limits import Limits
from .routers import files, health, terminals
from .services.file_service import FileService
from .services.terminal_service import TerminalService
from .utils.auth import configure_auth
from .utils.config import ServerConfig
from .utils.errors import ApiError
from .utils.responses import BaseResponse

logger = logging.getLogger("remote_agent_server")

# 全局服务实例（在 create_app 中初始化）
_file_service: FileService | None = None
_terminal_service: TerminalService | None = None


def _ensure_services() -> tuple[FileService, TerminalService]:
    """确保服务实例已初始化并返回。

    Returns:
        (文件服务, 终端服务) 元组。

    Raises:
        RuntimeError: 服务未初始化。
    """
    if _file_service is None or _terminal_service is None:
        raise RuntimeError("服务未初始化，请先调用 create_app")
    return _file_service, _terminal_service


def get_file_service() -> FileService:
    """获取全局文件服务实例。

    Returns:
        文件服务实例。

    Raises:
        RuntimeError: 服务未初始化。
    """
    if _file_service is None:
        raise RuntimeError("FileService 未初始化")
    return _file_service


def get_terminal_service() -> TerminalService:
    """获取全局终端服务实例。

    Returns:
        终端服务实例。

    Raises:
        RuntimeError: 服务未初始化。
    """
    if _terminal_service is None:
        raise RuntimeError("TerminalService 未初始化")
    return _terminal_service


def create_app(config: ServerConfig | None = None) -> FastAPI:
    """创建并配置 FastAPI 应用。

    Args:
        config: 服务器配置。为 None 时从默认路径加载。

    Returns:
        配置好的 FastAPI 应用实例。
    """
    global _file_service, _terminal_service

    if config is None:
        config = ServerConfig.load()

    # 初始化鉴权
    configure_auth(config.auth.token)

    # 初始化服务层
    limits = Limits(config.limits)
    file_svc = FileService(limits)
    terminal_svc = TerminalService(limits, sudo=config.sudo)
    _file_service = file_svc
    _terminal_service = terminal_svc

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """应用生命周期管理。"""
        # 启动：开启终端空闲回收
        terminal_svc.start_cleanup_loop()
        logger.info(
            "remote_agent_server 已启动: %s:%s",
            config.server.host,
            config.server.port,
        )
        yield
        # 关闭：清理所有终端会话
        await terminal_svc.shutdown()
        logger.info("remote_agent_server 已关闭")

    app = FastAPI(
        title="remote_agent_server",
        description="远程服务器代理后端服务，提供文件操作与终端执行能力",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 注册路由
    app.include_router(health.router)
    app.include_router(files.router)
    app.include_router(terminals.router)

    # 全局异常处理器
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        """处理业务异常，返回统一响应结构。"""
        return JSONResponse(
            status_code=exc.code,
            content=BaseResponse.error(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """处理未捕获异常，返回 500。"""
        logger.exception("未处理的异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content=BaseResponse.error(code=500, message="服务器内部错误").model_dump(),
        )

    return app
