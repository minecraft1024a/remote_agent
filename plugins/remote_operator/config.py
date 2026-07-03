"""remote_operator 插件配置。

存储 Agent 子代理使用的模型任务名、最大工具调用轮数等参数。
配置文件默认路径：config/plugins/remote_operator/config.toml
"""

from __future__ import annotations

from typing import ClassVar

from src.app.plugin_system.base import BaseConfig, Field, SectionBase, config_section


class RemoteOperatorConfig(BaseConfig):
    """remote_operator 插件配置。"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "远程服务器操控 Agent 插件配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件主配置。"""

        enabled: bool = Field(default=True, description="是否启用插件")

    @config_section("agent")
    class AgentSection(SectionBase):
        """Agent 子代理运行参数。"""

        model_task: str = Field(
            default="sub_actor",
            description="Agent 子代理使用的模型任务名（对应 model_config 中的任务名）",
        )
        max_rounds: int = Field(
            default=8,
            description="Agent 单次任务中允许的最大 LLM 工具调用轮数",
        )
        request_name: str = Field(
            default="remote_operator_agent",
            description="LLM 请求名称，用于统计与日志追踪",
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    agent: AgentSection = Field(default_factory=AgentSection)
