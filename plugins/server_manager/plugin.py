"""server_manager 插件入口。

以 Service 形式对外提供多服务器远程管理能力。
不注册 Tool/Action，仅通过 get_components() 返回 [ServerManagerService]。
"""

from __future__ import annotations

from src.app.plugin_system.base import BasePlugin, register_plugin
from src.app.plugin_system.api.log_api import get_logger

from .config import ServerManagerConfig
from .service import ServerManagerService

logger = get_logger("server_manager")


@register_plugin
class ServerManagerPlugin(BasePlugin):
    """server_manager 插件。

    管理多台后端服务器，通过 Service 提供文件操作与终端会话管理。
    """

    plugin_name: str = "server_manager"
    configs: list[type] = [ServerManagerConfig]

    def get_components(self) -> list[type]:
        """返回插件提供的组件类。

        Returns:
            仅包含 ServerManagerService 的列表。
        """
        return [ServerManagerService]

    async def on_plugin_loaded(self) -> None:
        """插件加载完成后记录服务器数量。"""
        cfg = self.config
        if isinstance(cfg, ServerManagerConfig):
            count = len(cfg.servers.items)
            ids = [s.id for s in cfg.servers.items]
            logger.info(f"server_manager 已加载，管理 {count} 台服务器: {ids}")
        else:
            logger.warning("server_manager 配置未正确加载")
