"""Token 鉴权中间件。

通过 FastAPI Dependency 校验请求头中的 Bearer Token。
健康检查接口无需鉴权。
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .errors import AuthError


class TokenAuth:
    """Bearer Token 鉴权器。

    持有期望的 Token 值，通过 verify 方法校验请求。
    当配置 Token 为空时，鉴权降级为放行（便于本地开发）。
    """

    def __init__(self, expected_token: str) -> None:
        """初始化鉴权器。

        Args:
            expected_token: 期望的 Bearer Token。
        """
        self._expected_token = expected_token

    @property
    def enabled(self) -> bool:
        """鉴权是否启用（Token 非空时启用）。"""
        return bool(self._expected_token)

    def verify(self, credentials: HTTPAuthorizationCredentials | None) -> None:
        """校验 Bearer Token。

        Args:
            credentials: 从请求头解析出的凭证。

        Raises:
            AuthError: Token 缺失或不匹配时抛出。
        """
        if not self.enabled:
            # Token 未配置，降级放行（仅限本地开发）
            return

        if credentials is None:
            raise AuthError("缺少 Authorization 头")

        if credentials.scheme.lower() != "bearer":
            raise AuthError("鉴权方案必须为 Bearer")

        if not secrets.compare_digest(credentials.credentials, self._expected_token):
            raise AuthError("Token 无效")


# 全局鉴权器实例，由 app 在启动时注入
_auth_instance: TokenAuth | None = None


def configure_auth(expected_token: str) -> None:
    """配置全局鉴权器。

    Args:
        expected_token: 期望的 Bearer Token。
    """
    global _auth_instance
    _auth_instance = TokenAuth(expected_token)


def get_auth_instance() -> TokenAuth:
    """获取全局鉴权器实例。

    Returns:
        当前生效的鉴权器。未配置时返回空 Token 鉴权器。
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = TokenAuth("")
    return _auth_instance


_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """FastAPI 依赖：校验 Bearer Token。

    在需要鉴权的路由上使用 ``Depends(require_auth)``。

    Args:
        credentials: 自动解析的凭证。

    Raises:
        AuthError: 鉴权失败时抛出。
    """
    get_auth_instance().verify(credentials)


def is_auth_required(request: Request) -> bool:
    """判断请求是否需要鉴权。

    健康检查路径免鉴权。

    Args:
        request: FastAPI 请求对象。

    Returns:
        是否需要鉴权。
    """
    path = request.url.path
    if path == "/api/health":
        return False
    return True
