"""remote_operator 插件入口。

注册 RemoteOperatorAgent 组件，对外提供基于 Agent 的远程服务器操控能力。
Agent 内部通过 service_api 调用 ServerManagerService，将文件操作与
终端执行封装为私有工具供 LLM 在子代理流程中调用。
"""

from src.app.plugin_system.base import BasePlugin, register_plugin
from src.kernel.logger import get_logger

from .agent import RemoteOperatorAgent
from .config import RemoteOperatorConfig

logger = get_logger("remote_operator")


@register_plugin
class RemoteOperatorPlugin(BasePlugin):
    """远程服务器操控 Agent 插件。"""

    plugin_name: str = "remote_operator"
    plugin_description: str = (
        "以 Agent 组件形式提供远程服务器操控能力。通过内部调用 "
        "ServerManagerService，将文件操作与终端执行封装为 Agent 私有工具，"
        "供 LLM 在子代理流程中完成对远程服务器的浏览、编辑、命令执行等任务。"
    )
    plugin_version: str = "1.0.0"

    configs: list[type] = [RemoteOperatorConfig]
    dependent_components: list[str] = ["server_manager:service:server_manager"]

    def get_components(self) -> list[type]:
        """返回插件组件类。"""

        return [RemoteOperatorAgent]

    async def on_plugin_loaded(self) -> None:
        """插件加载后记录日志。"""
        logger.info("remote_operator 插件已加载，Agent: remote_operator_agent")

    async def on_plugin_unloaded(self) -> None:
        """插件卸载时记录日志。"""
        logger.info("remote_operator 插件已卸载")
