"""后端配置加载。

支持通过 config.toml 或环境变量（RAS_ 前缀）配置服务器参数。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomllib
from pydantic import BaseModel, Field


class ServerSection(BaseModel):
    """服务器监听配置。"""

    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8421, description="监听端口")


class AuthSection(BaseModel):
    """鉴权配置。"""

    token: str = Field(default="", description="Bearer Token")


class LimitsSection(BaseModel):
    """安全限制配置。"""

    max_file_read: int = Field(default=5_242_880, description="文件读取大小上限（字节）")
    max_file_write: int = Field(default=10_485_760, description="文件写入大小上限（字节）")
    max_command_output: int = Field(default=1_048_576, description="命令输出捕获上限（字节）")
    max_command_timeout: int = Field(default=120, description="命令超时上限（秒）")
    terminal_idle_timeout: int = Field(default=1800, description="终端空闲超时（秒）")
    max_terminals: int = Field(default=16, description="最大并发终端数")


class SudoSection(BaseModel):
    """sudo 配置。

    当 exec_command 请求 use_sudo=True 时，后端使用 sudo -S 从 stdin
    读取密码来执行命令。密码仅在内存中传递，不写入日志。
    """

    enabled: bool = Field(default=False, description="是否允许 sudo 执行")
    password: str = Field(default="", description="sudo 密码（仅内存传递，不记日志）")


class ServerConfig(BaseModel):
    """remote_agent_server 完整配置。"""

    server: ServerSection = Field(default_factory=ServerSection)
    auth: AuthSection = Field(default_factory=AuthSection)
    limits: LimitsSection = Field(default_factory=LimitsSection)
    sudo: SudoSection = Field(default_factory=SudoSection)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "ServerConfig":
        """加载配置。

        优先级：环境变量 > config.toml > 默认值。

        Args:
            config_path: 配置文件路径。为 None 时依次尝试 config.toml、环境变量 RAS_CONFIG。

        Returns:
            加载后的配置实例。
        """
        data: dict[str, Any] = {}

        resolved_path = cls._resolve_config_path(config_path)
        if resolved_path is not None and resolved_path.exists():
            with open(resolved_path, "rb") as f:
                data = tomllib.load(f)

        # 环境变量覆盖（RAS_ 前缀，双下划线分隔层级）
        env_overrides = cls._collect_env_overrides()
        cls._deep_merge(data, env_overrides)

        return cls.model_validate(data)

    @staticmethod
    def _resolve_config_path(config_path: str | Path | None) -> Path | None:
        """解析配置文件路径。"""
        if config_path is not None:
            return Path(config_path)

        env_path = os.environ.get("RAS_CONFIG")
        if env_path:
            return Path(env_path)

        return Path("config.toml")

    @staticmethod
    def _collect_env_overrides() -> dict[str, Any]:
        """收集 RAS_ 前缀的环境变量覆盖。

        格式：RAS_<section>__<field>，例如 RAS_AUTH__token、RAS_SERVER__port。
        """
        result: dict[str, Any] = {}
        prefix = "RAS_"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            parts = key[len(prefix):].lower().split("__")
            if len(parts) != 2:
                continue
            section, field_name = parts
            result.setdefault(section, {})[field_name] = ServerConfig._coerce_env_value(value)
        return result

    @staticmethod
    def _coerce_env_value(value: str) -> Any:
        """尝试将环境变量值转为合适的类型。"""
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            return int(value)
        except ValueError:
            return value

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
        """将 override 深度合并到 base 中。"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ServerConfig._deep_merge(base[key], value)
            else:
                base[key] = value
