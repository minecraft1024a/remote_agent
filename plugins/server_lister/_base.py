"""工具共享辅助函数。

提供获取 ServerManagerService 实例的统一入口，供 ListServersTool 复用。

本插件不直接导入 server_manager 插件的源码（遵循插件间禁止源码级
依赖的约束），而是通过 service_api 获取 Service 实例后以鸭子类型
调用其方法。这里定义一个 Protocol 描述所需的 Service 能力形状，
仅用于静态类型检查。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.app.plugin_system.api import service_api


@runtime_checkable
class _ServerManagerLike(Protocol):
    """ServerManagerService 的能力协议（本地抽象，不耦合源码）。

    定义 server_lister 所需的方法形状，运行时由 service_api 返回
    的真实实例满足此协议。本插件仅需 list_servers 能力。
    """

    def list_servers(self) -> list[Any]:
        """列出所有已配置的服务器（不含 token）。"""
        ...


#: ServerManagerService 的组件签名
_SERVER_MANAGER_SIGNATURE: str = "server_manager:service:server_manager"


def get_server_manager_service() -> _ServerManagerLike:
    """获取 ServerManagerService 实例。

    通过 service_api 按签名获取，不直接导入 server_manager 插件源码。

    Returns:
        满足 _ServerManagerLike 协议的 Service 实例。

    Raises:
        RuntimeError: server_manager 插件未加载或 Service 未注册时抛出。
    """
    service = service_api.get_service(_SERVER_MANAGER_SIGNATURE)
    if service is None:
        raise RuntimeError(
            "server_manager 服务未注册，请先加载 server_manager 插件"
        )
    return service  # type: ignore[return-value]
