"""后端统一异常定义。

所有业务异常继承 ApiError，携带 code 与 message，
由全局异常处理器转换为统一响应结构。
"""

from __future__ import annotations


class ApiError(Exception):
    """后端业务异常基类。

    Attributes:
        code: 业务状态码（与 HTTP 状态码对齐）。
        message: 可读的错误描述。
    """

    def __init__(self, code: int, message: str) -> None:
        """初始化业务异常。

        Args:
            code: 业务状态码。
            message: 错误描述。
        """
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class AuthError(ApiError):
    """鉴权失败异常。"""

    def __init__(self, message: str = "鉴权失败") -> None:
        """初始化鉴权异常。

        Args:
            message: 错误描述。
        """
        super().__init__(code=401, message=message)


class NotFoundError(ApiError):
    """资源不存在异常。"""

    def __init__(self, message: str = "资源不存在") -> None:
        """初始化资源不存在异常。

        Args:
            message: 错误描述。
        """
        super().__init__(code=404, message=message)


class LimitExceededError(ApiError):
    """超限异常（大小、数量、超时等）。"""

    def __init__(self, code: int, message: str) -> None:
        """初始化超限异常。

        Args:
            code: 业务状态码（通常为 413 或 429）。
            message: 错误描述。
        """
        super().__init__(code=code, message=message)


class CommandTimeoutError(ApiError):
    """命令执行超时异常。"""

    def __init__(self, message: str = "命令执行超时") -> None:
        """初始化命令超时异常。

        Args:
            message: 错误描述。
        """
        super().__init__(code=408, message=message)


class InternalError(ApiError):
    """服务器内部错误异常。"""

    def __init__(self, message: str = "服务器内部错误") -> None:
        """初始化内部错误异常。

        Args:
            message: 错误描述（不泄露堆栈）。
        """
        super().__init__(code=500, message=message)
