"""健康检查路由。

提供无需鉴权的 /api/health 端点，用于探活。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..utils.models import HealthResult
from ..utils.responses import BaseResponse

router = APIRouter(prefix="/api", tags=["health"])

_VERSION = "1.0.0"


@router.get("/health", response_model=BaseResponse)
async def health_check() -> BaseResponse:
    """健康检查端点。

    无需鉴权。返回服务状态与版本。

    Returns:
        包含 HealthResult 的统一响应。
    """
    return BaseResponse.ok(data=HealthResult(status="ok", version=_VERSION).model_dump())
