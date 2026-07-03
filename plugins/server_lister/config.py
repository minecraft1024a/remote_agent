"""server_lister 插件配置。

仅包含插件启用开关，不持有额外运行参数。
配置文件默认路径：config/plugins/server_lister/config.toml
"""

from __future__ import annotations

from typing import ClassVar

from src.app.plugin_system.base import BaseConfig, Field, SectionBase, config_section


class ServerListerConfig(BaseConfig):
    """server_lister 插件配置。"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "服务器列表查询工具插件配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件主配置。"""

        enabled: bool = Field(default=True, description="是否启用插件")

    plugin: PluginSection = Field(default_factory=PluginSection)
