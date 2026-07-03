"""server_manager 插件配置。

存储服务器列表（ID/URL/Token）及 HTTP 客户端超时配置。
配置文件默认路径：config/plugins/server_manager/config.toml
"""

from __future__ import annotations

from typing import ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class ServerEntry(SectionBase):
    """单个服务器配置项。"""

    id: str = Field(default="", description="服务器唯一标识")
    name: str = Field(default="", description="服务器显示名称")
    base_url: str = Field(default="", description="后端服务地址")
    token: str = Field(default="", description="Bearer Token")


class ServerManagerConfig(BaseConfig):
    """server_manager 插件配置。"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "远程服务器管理插件配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件主配置。"""

        enabled: bool = Field(default=True, description="是否启用插件")

    @config_section("client")
    class ClientSection(SectionBase):
        """HTTP 客户端配置。"""

        request_timeout: int = Field(
            default=30,
            description="HTTP 请求超时（秒）",
        )

    @config_section("servers")
    class ServersSection(SectionBase):
        """服务器列表配置。

        在 TOML 中以 [[servers]] 数组形式定义多台服务器。
        """

        items: list[ServerEntry] = Field(
            default_factory=list,
            description="服务器配置列表",
        )

    plugin: PluginSection = Field(default_factory=PluginSection)
    client: ClientSection = Field(default_factory=ClientSection)
    servers: ServersSection = Field(default_factory=ServersSection)
