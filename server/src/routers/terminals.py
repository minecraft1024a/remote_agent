"""终端操作路由。

提供终端创建、命令执行、列举、查询与关闭的 HTTP 端点。
所有端点需 Bearer Token 鉴权。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..services.terminal_service import TerminalService
from ..utils.auth import require_auth
from ..utils.models import (
    TerminalCloseResult,
    TerminalCreateRequest,
    TerminalExecRequest,
    TerminalInfo,
)
from ..utils.responses import BaseResponse

router = APIRouter(
    prefix="/api/terminals",
    tags=["terminals"],
    dependencies=[Depends(require_auth)],
)


def _get_service() -> TerminalService:
    """获取全局终端服务实例。

    Returns:
        终端服务实例。
    """
    from ..app import get_terminal_service

    return get_terminal_service()


@router.post("", response_model=BaseResponse)
async def create_terminal(request: TerminalCreateRequest) -> BaseResponse:
    """创建新的终端会话。

    Args:
        request: 创建终端请求。

    Returns:
        包含 TerminalInfo 的统一响应。
    """
    service = _get_service()
    result = await service.create_terminal(
        shell=request.shell,
        cwd=request.cwd,
        env=request.env,
        remark=request.remark,
    )
    return BaseResponse.ok(data=result.model_dump())


@router.get("", response_model=BaseResponse)
async def list_terminals() -> BaseResponse:
    """列出所有活跃的终端会话。

    Returns:
        包含终端列表的统一响应。
    """
    service = _get_service()
    terminals = await service.list_terminals()
    return BaseResponse.ok(
        data={"terminals": [t.model_dump() for t in terminals]}
    )


@router.get("/{terminal_id}", response_model=BaseResponse)
async def get_terminal(terminal_id: str) -> BaseResponse:
    """获取终端会话信息。

    Args:
        terminal_id: 终端 ID。

    Returns:
        包含 TerminalInfo 的统一响应。
    """
    service = _get_service()
    result = await service.get_terminal(terminal_id)
    return BaseResponse.ok(data=result.model_dump())


@router.post("/{terminal_id}/exec", response_model=BaseResponse)
async def exec_command(terminal_id: str, request: TerminalExecRequest) -> BaseResponse:
    """在指定终端中执行命令。

    当 request.use_sudo=True 时，以 sudo 执行该命令（需后端配置 sudo）。

    Args:
        terminal_id: 终端 ID。
        request: 命令执行请求。

    Returns:
        包含 CommandResult 的统一响应。
    """
    service = _get_service()
    result = await service.exec_command(
        terminal_id,
        request.command,
        request.timeout,
        use_sudo=request.use_sudo,
    )
    return BaseResponse.ok(data=result.model_dump())


@router.delete("/{terminal_id}", response_model=BaseResponse)
async def close_terminal(terminal_id: str) -> BaseResponse:
    """关闭指定终端会话。

    Args:
        terminal_id: 终端 ID。

    Returns:
        包含 TerminalCloseResult 的统一响应。
    """
    service = _get_service()
    closed = await service.close_terminal(terminal_id)
    return BaseResponse.ok(
        data=TerminalCloseResult(terminal_id=terminal_id, closed=closed).model_dump()
    )
