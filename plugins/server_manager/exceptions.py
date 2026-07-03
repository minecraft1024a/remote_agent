"""server_manager 插件异常定义。

统一异常 ServerManagerError，包含 code、message、server_id 字段。
调用方应捕获此异常进行错误处理。
"""

from __future__ import annotations


class ServerManagerError(Exception):
    """服务器管理服务异常。

    Attributes:
        code: 业务状态码（与后端 code 对齐，404/401/408/413/429/500/503 等）。
        message: 可读的错误描述。
        server_id: 关联的服务器 ID，便于定位（可能为空）。
    """

    def __init__(self, code: int, message: str, server_id: str = "") -> None:
        """初始化服务器管理异常。

        Args:
            code: 业务状态码。
            message: 错误描述。
            server_id: 关联的服务器 ID。
        """
        self.code = code
        self.message = message
        self.server_id = server_id
        super().__init__(f"[{server_id}] {code}: {message}")
