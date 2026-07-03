"""HTTP 客户端封装。

使用 httpx.AsyncClient 发送请求到后端 remote_agent_server。
每次调用创建临时客户端，调用结束后关闭（因 service_api 每次返回新实例）。
"""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from .exceptions import ServerManagerError

T = TypeVar("T", bound=BaseModel)


class RemoteAgentClient:
    """后端 HTTP 客户端。

    封装请求发送与响应解析，统一处理鉴权、超时与错误。
    """

    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        """初始化客户端。

        Args:
            base_url: 后端服务地址（如 http://192.168.1.100:8421）。
            token: Bearer Token。
            timeout: HTTP 请求超时（秒）。
        """
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        server_id: str = "",
    ) -> Any:
        """发送 HTTP 请求并解析统一响应。

        Args:
            method: HTTP 方法（GET/POST/DELETE 等）。
            path: 请求路径（如 /api/files/list）。
            json: 请求体 JSON。
            server_id: 关联的服务器 ID，用于错误定位。

        Returns:
            后端响应中 data 字段的内容。

        Raises:
            ServerManagerError: HTTP 失败或业务 code 非 200。
        """
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        url = f"{self._base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(method, url, json=json, headers=headers)
        except httpx.ConnectError as exc:
            raise ServerManagerError(
                code=503,
                message=f"无法连接到服务器: {exc}",
                server_id=server_id,
            ) from exc
        except httpx.TimeoutException as exc:
            raise ServerManagerError(
                code=504,
                message=f"请求超时: {exc}",
                server_id=server_id,
            ) from exc
        except httpx.HTTPError as exc:
            raise ServerManagerError(
                code=503,
                message=f"HTTP 请求失败: {exc}",
                server_id=server_id,
            ) from exc

        # 解析统一响应结构
        try:
            body = resp.json()
        except ValueError as exc:
            raise ServerManagerError(
                code=500,
                message=f"响应不是有效 JSON: {exc}",
                server_id=server_id,
            ) from exc

        code = body.get("code", resp.status_code)
        message = body.get("message", "")
        data = body.get("data")

        if code != 200:
            raise ServerManagerError(
                code=code,
                message=message or f"后端返回错误码 {code}",
                server_id=server_id,
            )

        return data

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        *,
        server_id: str = "",
        model: type[T] | None = None,
    ) -> T | Any:
        """发送 POST 请求并可选映射到 Pydantic 模型。

        Args:
            path: 请求路径。
            json: 请求体。
            server_id: 关联的服务器 ID。
            model: 可选的 Pydantic 模型类，用于解析 data。

        Returns:
            解析后的模型实例或原始 data。
        """
        data = await self.request("POST", path, json=json, server_id=server_id)
        if model is not None and data is not None:
            return model.model_validate(data)
        return data

    async def get(
        self,
        path: str,
        *,
        server_id: str = "",
        model: type[T] | None = None,
    ) -> T | Any:
        """发送 GET 请求并可选映射到 Pydantic 模型。

        Args:
            path: 请求路径。
            server_id: 关联的服务器 ID。
            model: 可选的 Pydantic 模型类，用于解析 data。

        Returns:
            解析后的模型实例或原始 data。
        """
        data = await self.request("GET", path, server_id=server_id)
        if model is not None and data is not None:
            return model.model_validate(data)
        return data

    async def delete(
        self,
        path: str,
        *,
        server_id: str = "",
        model: type[T] | None = None,
    ) -> T | Any:
        """发送 DELETE 请求并可选映射到 Pydantic 模型。

        Args:
            path: 请求路径。
            server_id: 关联的服务器 ID。
            model: 可选的 Pydantic 模型类，用于解析 data。

        Returns:
            解析后的模型实例或原始 data。
        """
        data = await self.request("DELETE", path, server_id=server_id)
        if model is not None and data is not None:
            return model.model_validate(data)
        return data
