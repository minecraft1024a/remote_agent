"""工具共享辅助函数。

提供获取 ServerManagerService 实例的统一入口，供各私有工具复用。

本插件不直接导入 server_manager 插件的源码（遵循插件间禁止源码级
依赖的约束），而是通过 service_api 获取 Service 实例后以鸭子类型
调用其方法。这里定义一个 Protocol 描述所需的 Service 能力形状，
仅用于静态类型检查。
"""

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING, runtime_checkable

from src.app.plugin_system.api import service_api

if TYPE_CHECKING:
    pass


@runtime_checkable
class _ServerManagerLike(Protocol):
    """ServerManagerService 的能力协议（本地抽象，不耦合源码）。

    定义 remote_operator 所需的方法形状，运行时由 service_api 返回
    的真实实例满足此协议。
    """

    def list_servers(self) -> list[Any]:
        """列出所有已配置的服务器。"""
        ...

    def get_server(self, server_id: str) -> Any | None:
        """获取指定服务器的信息。"""
        ...

    async def list_files(self, server_id: str, path: str) -> Any:
        """列出目录内容。"""
        ...

    async def read_file(
        self, server_id: str, path: str, encoding: str = "utf-8"
    ) -> Any:
        """读取文件内容。"""
        ...

    async def write_file(
        self,
        server_id: str,
        path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> Any:
        """写入文件。"""
        ...

    async def edit_file(
        self,
        server_id: str,
        path: str,
        edits: list[Any],
        encoding: str = "utf-8",
    ) -> Any:
        """对文件进行 diff 编辑。"""
        ...

    async def delete_file(
        self, server_id: str, path: str, recursive: bool = False
    ) -> Any:
        """删除文件或目录。"""
        ...

    async def create_terminal(
        self,
        server_id: str,
        shell: str = "/bin/bash",
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        remark: str = "",
    ) -> Any:
        """创建终端会话。"""
        ...

    async def list_terminals(self, server_id: str) -> list[Any]:
        """列出所有活跃终端。"""
        ...

    async def exec_command(
        self,
        server_id: str,
        terminal_id: str,
        command: str,
        timeout: int = 30,
        use_sudo: bool = False,
    ) -> Any:
        """在终端中执行命令。"""
        ...

    async def get_terminal(self, server_id: str, terminal_id: str) -> Any:
        """获取终端信息。"""
        ...

    async def close_terminal(self, server_id: str, terminal_id: str) -> bool:
        """关闭终端。"""
        ...


#: ServerManagerService 的组件签名
_SERVER_MANAGER_SIGNATURE = "server_manager:service:server_manager"


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
