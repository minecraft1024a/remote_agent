"""remote_operator_actions 插件入口。

注册远程服务器文件、终端和结束任务 Action。每个 Action 的
``go_activate`` 都返回 False，因此不会进入普通聊天的 LLM 工具列表。
"""

from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.base import BasePlugin, register_plugin

from .tools import (
    CloseTerminalTool,
    CreateTerminalTool,
    DeleteFileTool,
    EditFileTool,
    ExecCommandTool,
    ListFilesTool,
    ListServersTool,
    ListTerminalsTool,
    ReadFileTool,
    WriteFileTool,
)

logger = get_logger("remote_operator_actions")


@register_plugin
class RemoteOperatorActionsPlugin(BasePlugin):
    """注册隐藏的远程操作 Action。"""

    plugin_name: str = "remote_operator_actions"

    def get_components(self) -> list[type]:
        """向主程序注册 Action 组件。"""
        return [
            ListServersTool,
            ListFilesTool,
            ReadFileTool,
            WriteFileTool,
            EditFileTool,
            DeleteFileTool,
            CreateTerminalTool,
            ExecCommandTool,
            ListTerminalsTool,
            CloseTerminalTool,
        ]

    async def on_plugin_loaded(self) -> None:
        logger.info(
            "remote_operator_actions 插件已加载，11 个 Action 默认不对 LLM 激活"
        )

    async def on_plugin_unloaded(self) -> None:
        logger.info("remote_operator_actions 插件已卸载")
