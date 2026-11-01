"""server_lister 插件入口。

注册 ListServersTool 组件，对外提供「获取已配置远程服务器列表」能力。
LLM 在调用 remote_operator Agent 之前，应先调用本工具确认目标 server_id。

本插件不直接导入 server_manager 插件源码，而是通过 service_api
获取 ServerManagerService 实例后以鸭子类型调用其 list_servers 方法。
"""

from __future__ import annotations

from src.app.plugin_system.base import BasePlugin, register_plugin
from src.app.plugin_system.api.log_api import get_logger

from .config import ServerListerConfig
from .tool import ListServersTool

logger = get_logger("server_lister")


@register_plugin
class ServerListerPlugin(BasePlugin):
    """server_lister 插件。

    提供独立的 ListServersTool 工具，供 LLM 在远程操控流程中
    探测可用的服务器列表并据此决策 server_id。
    """

    plugin_name: str = "server_lister"
    configs: list[type] = [ServerListerConfig]

    def get_components(self) -> list[type]:
        """返回插件提供的组件类。

        Returns:
            仅包含 ListServersTool 的列表。
        """
        return [ListServersTool]

    async def on_plugin_loaded(self) -> None:
        """插件加载完成后记录日志。"""
        logger.info("server_lister 插件已加载，Tool: list_servers")

    async def on_plugin_unloaded(self) -> None:
        """插件卸载时记录日志。"""
        logger.info("server_lister 插件已卸载")
