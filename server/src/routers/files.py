"""文件操作路由。

提供目录列举、文件读写、删除与 diff 编辑的 HTTP 端点。
所有端点需 Bearer Token 鉴权。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..services.file_service import FileService
from ..utils.auth import require_auth
from ..utils.models import (
    FileDeleteRequest,
    FileDeleteResult,
    FileEditRequest,
    FileEditResult,
    FileListRequest,
    FileListResult,
    FileReadRequest,
    FileReadResult,
    FileWriteRequest,
    FileWriteResult,
)
from ..utils.responses import BaseResponse

router = APIRouter(prefix="/api/files", tags=["files"], dependencies=[Depends(require_auth)])


def _get_service() -> FileService:
    """获取全局文件服务实例。

    Returns:
        文件服务实例。
    """
    from ..app import get_file_service

    return get_file_service()


@router.post("/list", response_model=BaseResponse)
async def list_files(request: FileListRequest) -> BaseResponse:
    """列出目录内容。

    Args:
        request: 列目录请求。

    Returns:
        包含 FileListResult 的统一响应。
    """
    service = _get_service()
    result = await service.list_files(request.path)
    return BaseResponse.ok(data=result.model_dump())


@router.post("/read", response_model=BaseResponse)
async def read_file(request: FileReadRequest) -> BaseResponse:
    """读取文件内容。

    Args:
        request: 读文件请求。

    Returns:
        包含 FileReadResult 的统一响应。
    """
    service = _get_service()
    result = await service.read_file(request.path, request.encoding)
    return BaseResponse.ok(data=result.model_dump())


@router.post("/write", response_model=BaseResponse)
async def write_file(request: FileWriteRequest) -> BaseResponse:
    """写入文件内容。

    Args:
        request: 写文件请求。

    Returns:
        包含 FileWriteResult 的统一响应。
    """
    service = _get_service()
    result = await service.write_file(
        request.path,
        request.content,
        request.encoding,
        request.create_dirs,
    )
    return BaseResponse.ok(data=result.model_dump())


@router.post("/delete", response_model=BaseResponse)
async def delete_file(request: FileDeleteRequest) -> BaseResponse:
    """删除文件或目录。

    Args:
        request: 删除请求。

    Returns:
        包含 FileDeleteResult 的统一响应。
    """
    service = _get_service()
    result = await service.delete_file(request.path, request.recursive)
    return BaseResponse.ok(data=result.model_dump())


@router.post("/edit", response_model=BaseResponse)
async def edit_file(request: FileEditRequest) -> BaseResponse:
    """对文件进行 diff 编辑（搜索/替换）。

    Args:
        request: 编辑请求。

    Returns:
        包含 FileEditResult 的统一响应。
    """
    service = _get_service()
    result = await service.edit_file(request.path, request.edits, request.encoding)
    return BaseResponse.ok(data=result.model_dump())
