"""ListServersTool 工具实现。

提供「获取已配置远程服务器列表」能力，供 LLM 在调用 remote_operator
Agent 执行远程操控前确认目标 server_id。

工作流约定（写入工具描述，供 LLM 遵循）：
1. 调用本工具获取可用服务器列表。
2. 若仅一台服务器，直接使用其 id 作为后续 server_id。
3. 若多台服务器且用户已指定目标，使用对应 id。
4. 若多台服务器且用户未指定，向用户询问要操作哪台服务器，
   不要自行猜测。
"""

from __future__ import annotations

from typing import Annotated, Any

from src.app.plugin_system.base import BaseTool

from ._base import get_server_manager_service


class ListServersTool(BaseTool):
    """列出所有已配置的远程服务器。

    本工具是远程操控流程的入口探测工具：LLM 在调用 remote_operator
    Agent 之前应先调用本工具，确认可用的 server_id 并据此决定后续动作。
    """

    name: str = "list_servers"
    description: str = (
        "列出所有已配置的远程服务器，返回每台服务器的 id、名称与地址（不含 token）。"
        "\n\n"
        "【使用时机】在调用 remote_operator Agent 执行任何远程服务器操控任务之前，"
        "必须先调用本工具确认可用的 server_id。\n\n"
        "【决策规则】\n"
        "1. 若返回的服务器仅有一台，无需询问用户，直接使用该服务器的 id 作为 "
        "remote_operator Agent 任务的 server_id。\n"
        "2. 若返回多台服务器，且用户已在消息中明确指定了目标服务器（通过名称、"
        "id 或可辨识的描述），则使用对应服务器的 id，无需再次询问。\n"
        "3. 若返回多台服务器，且用户未指定目标服务器，则不要调用 remote_operator "
        "Agent，而是先向用户询问要操作哪一台服务器，列出可选项供用户选择。"
        "待用户明确指定后，再调用 remote_operator Agent 并传入对应的 server_id。\n\n"
        "【返回结构】{\"servers\": [{\"id\":..., \"name\":..., \"base_url\":...}, ...], \"count\": N}。"
    )

    async def execute(self) -> tuple[Annotated[bool, "是否成功"], Annotated[str | dict, "返回结果"]]:
        """执行列出服务器逻辑。

        通过 service_api 获取 ServerManagerService 实例并调用其
        list_servers 方法，返回结构化的服务器列表。

        Returns:
            tuple[bool, str | dict]: (是否成功, 服务器列表或错误信息)。
            成功时 result 形如::

                {
                    "servers": [
                        {"id": "srv-a", "name": "生产服务器 A", "base_url": "http://..."},
                        ...
                    ],
                    "count": 2
                }
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
