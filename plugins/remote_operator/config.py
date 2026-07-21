"""remote_operator 插件配置。

存储 Agent 子代理使用的模型任务名、最大工具调用轮数等参数。
配置文件默认路径：config/plugins/remote_operator/config.toml
"""

from __future__ import annotations

from typing import ClassVar

from src.app.plugin_system.base import BaseConfig, Field, SectionBase, config_section


class RemoteOperatorConfig(BaseConfig):
    """remote_operator 插件配置。"""

    name: ClassVar[str] = "config"
    description: ClassVar[str] = "远程服务器操控 Agent 插件配置"

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

    @config_section("result_guard")
    class ResultGuardSection(SectionBase):
        """finish_task 结果自包含校验配置。

        用户只能看到 finish_task 提交的 result 这一段文本。若 Agent 在
        result 中使用「上面就是」「见上文」等指代 result 之外内容的措辞，
        那些被指代的内容用户根本看不到。开启后，违规的 result 会被打回，
        要求 Agent 重写为自包含版本。
        """

        enabled: bool = Field(
            default=True,
            description=(
                "是否开启 finish_task 结果自包含校验。开启后，result 中"
                "若出现指代 result 之外内容的措辞（如「上面就是」「见上文」），"
                "会被打回要求 Agent 重写。关闭则放行所有 result。"
            ),
        )
        max_rewrite_attempts: int = Field(
            default=2,
            description=(
                "结果被代称检测打回时允许的最大重写次数。超过此次数后"
                "强制结束任务并附带警告。设为 0 表示不重写、首次违规即放行"
                "（仅记录日志）。"
            ),
        )
        extra_patterns: list[str] = Field(
            default_factory=list,
            description=(
                "除内置代称模式外，额外需要拦截的代称措辞列表。"
                "命中内置模式或额外模式任一即视为违规。"
            ),
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    agent: AgentSection = Field(default_factory=AgentSection)
    result_guard: ResultGuardSection = Field(default_factory=ResultGuardSection)
