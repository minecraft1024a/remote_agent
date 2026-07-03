"""统一响应封装。

所有业务接口返回 BaseResponse 结构，错误也通过此结构返回。
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class BaseResponse(BaseModel):
    """统一响应模型。

    Attributes:
        code: 业务状态码，200 为成功，其余为错误码。
        data: 实际业务数据，失败时可为 null。
        message: 可读的状态描述。
    """

    code: int = 200
    data: Any = None
    message: str = "success"

    @classmethod
    def ok(cls, data: Any = None, message: str = "success") -> "BaseResponse":
        """构造成功响应。

        Args:
            data: 业务数据。
            message: 状态描述。

        Returns:
            成功响应实例。
        """
        return cls(code=200, data=data, message=message)

    @classmethod
    def error(cls, code: int, message: str) -> "BaseResponse":
        """构造错误响应。

        Args:
            code: 错误状态码。
            message: 错误描述。

        Returns:
            错误响应实例。
        """
        return cls(code=code, data=None, message=message)


class TypedResponse(BaseModel, Generic[T]):
    """带类型的响应模型，用于内部类型推导。

    与 BaseResponse 结构一致，但 data 具有具体类型。
    """

    code: int = 200
    data: T | None = None
    message: str = "success"
