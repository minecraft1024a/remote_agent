"""server_manager 插件入口。

以 Service 形式对外提供多服务器远程管理能力。
不注册 Tool/Action，仅通过 get_components() 返回 [ServerManagerService]。
"""

from __future__ import annotations

from src.core.components.base.plugin import BasePlugin
from src.core.components.loader import register_plugin
from src.kernel.logger import get_logger

from .config import ServerManagerConfig
from .service import ServerManagerService

logger = get_logger("server_manager")


@register_plugin
class ServerManagerPlugin(BasePlugin):
    """server_manager 插件。

    管理多台后端服务器，通过 Service 提供文件操作与终端会话管理。
    """

    plugin_name: str = "server_manager"
    plugin_description: str = "远程服务器文件与终端管理服务（多服务器路由）"
    plugin_version: str = "1.0.0"

    configs: list[type] = [ServerManagerConfig]
    dependent_components: list[str] = []

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
