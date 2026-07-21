"""服务器管理工具。

提供列出可用服务器、查询服务器信息的能力，供 Agent 在执行远程
操作前确认目标 server_id。
"""

from __future__ import annotations

from typing import Annotated, Any

from src.app.plugin_system.base import BaseTool

from ._base import get_server_manager_service


class ListServersTool(BaseTool):
    """列出所有已配置的远程服务器。"""

    name: str = "list_servers"
    description: str = (
        "列出所有已配置的远程服务器，返回每台服务器的 id、名称与地址。"
        "在执行任何文件或终端操作前，先调用此工具确认可用的 server_id。"
    )

    async def execute(self) -> tuple[bool, str | dict]:
        """执行列出服务器逻辑。

        Returns:
            tuple[bool, str | dict]: (是否成功, 服务器列表或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            servers: list[Any] = service.list_servers()
        except Exception as exc:
            return False, f"列出服务器失败: {exc}"

        data = [s.model_dump() for s in servers]
        return True, {"servers": data, "count": len(data)}
