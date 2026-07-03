"""ServerManagerService 服务实现。

通过指定 server_id 路由到对应后端 remote_agent_server，
提供文件操作与终端会话管理能力。

其他插件通过 service_api.get_service("server_manager:service:server_manager") 获取实例。
"""

from __future__ import annotations

from typing import cast

from src.core.components.base.service import BaseService
from src.kernel.logger import get_logger

from .client import RemoteAgentClient
from .config import ServerManagerConfig
from .exceptions import ServerManagerError
from .models import (
    CommandResult,
    FileDeleteResult,
    FileEditItem,
    FileEditResult,
    FileListResult,
    FileReadResult,
    FileWriteResult,
    ServerInfo,
    TerminalInfo,
)

logger = get_logger("server_manager")


class ServerManagerService(BaseService):
    """远程服务器管理服务。

    通过指定 server_id 路由到对应后端，提供文件操作与终端会话管理。
    一个插件实例可管理多台后端服务器，调用时通过 server_id 路由。
    """

    service_name: str = "server_manager"
    service_description: str = "远程服务器文件与终端管理服务"
    version: str = "1.0.0"

    # ------------------------------------------------------------------
    # 配置与路由
    # ------------------------------------------------------------------

    def _cfg(self) -> ServerManagerConfig:
        """获取插件配置实例。

        Returns:
            当前生效的配置实例。

        Raises:
            RuntimeError: 配置未正确加载。
        """
        cfg = self.plugin.config
        if not isinstance(cfg, ServerManagerConfig):
            raise RuntimeError("server_manager plugin config 未正确加载")
        return cfg

    def _resolve_server(self, server_id: str) -> tuple[str, str]:
        """根据 server_id 解析出 (base_url, token)。

        Args:
            server_id: 服务器标识。

        Returns:
            (base_url, token) 元组。

        Raises:
            ServerManagerError: server_id 不存在时抛出。
        """
        cfg = self._cfg()
        for entry in cfg.servers.items:
            if entry.id == server_id:
                return entry.base_url, entry.token
        raise ServerManagerError(
            code=404,
            message=f"服务器不存在: {server_id}",
            server_id=server_id,
        )

    def _get_client(self, server_id: str) -> RemoteAgentClient:
        """为指定服务器创建 HTTP 客户端。

        Args:
            server_id: 服务器标识。

        Returns:
            配置好的客户端实例。
        """
        base_url, token = self._resolve_server(server_id)
        timeout = self._cfg().client.request_timeout
        return RemoteAgentClient(base_url=base_url, token=token, timeout=timeout)

    # ------------------------------------------------------------------
    # 服务器管理
    # ------------------------------------------------------------------

    def list_servers(self) -> list[ServerInfo]:
        """列出所有已配置的服务器（不含 token）。

        Returns:
            服务器信息列表。
        """
        cfg = self._cfg()
        return [
            ServerInfo(id=entry.id, name=entry.name, base_url=entry.base_url)
            for entry in cfg.servers.items
        ]

    def get_server(self, server_id: str) -> ServerInfo | None:
        """获取指定服务器的信息。

        Args:
            server_id: 服务器标识。

        Returns:
            服务器信息，不存在时返回 None。
        """
        cfg = self._cfg()
        for entry in cfg.servers.items:
            if entry.id == server_id:
                return ServerInfo(id=entry.id, name=entry.name, base_url=entry.base_url)
        return None

    # ------------------------------------------------------------------
    # 文件操作
    # ------------------------------------------------------------------

    async def list_files(self, server_id: str, path: str) -> FileListResult:
        """列出指定服务器上的目录内容。

        Args:
            server_id: 服务器标识。
            path: 目录路径。

        Returns:
            目录列表结果。
        """
        client = self._get_client(server_id)
        result = await client.post(
            "/api/files/list",
            json={"path": path},
            server_id=server_id,
            model=FileListResult,
        )
        return cast(FileListResult, result)

    async def read_file(
        self,
        server_id: str,
        path: str,
        encoding: str = "utf-8",
    ) -> FileReadResult:
        """读取指定服务器上的文件内容。

        Args:
            server_id: 服务器标识。
            path: 文件路径。
            encoding: 文件编码。

        Returns:
            文件读取结果。
        """
        client = self._get_client(server_id)
        result = await client.post(
            "/api/files/read",
            json={"path": path, "encoding": encoding},
            server_id=server_id,
            model=FileReadResult,
        )
        return cast(FileReadResult, result)

    async def write_file(
        self,
        server_id: str,
        path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> FileWriteResult:
        """向指定服务器写入文件。

        Args:
            server_id: 服务器标识。
            path: 文件路径。
            content: 文件内容。
            encoding: 文件编码。

        Returns:
            文件写入结果。
        """
        client = self._get_client(server_id)
        result = await client.post(
            "/api/files/write",
            json={"path": path, "content": content, "encoding": encoding, "create_dirs": True},
            server_id=server_id,
            model=FileWriteResult,
        )
        return cast(FileWriteResult, result)

    async def edit_file(
        self,
        server_id: str,
        path: str,
        edits: list[FileEditItem],
        encoding: str = "utf-8",
    ) -> FileEditResult:
        """对指定服务器上的文件进行 diff 编辑（搜索/替换）。

        适用于大文件中的局部修改，避免重写整个文件。

        Args:
            server_id: 服务器标识。
            path: 文件路径。
            edits: 有序的搜索/替换对列表。
            encoding: 文件编码。

        Returns:
            文件编辑结果，包含修改后的完整内容。
        """
        client = self._get_client(server_id)
        result = await client.post(
            "/api/files/edit",
            json={
                "path": path,
                "edits": [e.model_dump() for e in edits],
                "encoding": encoding,
            },
            server_id=server_id,
            model=FileEditResult,
        )
        return cast(FileEditResult, result)

    async def delete_file(
        self,
        server_id: str,
        path: str,
        recursive: bool = False,
    ) -> FileDeleteResult:
        """删除指定服务器上的文件或目录。

        Args:
            server_id: 服务器标识。
            path: 路径。
            recursive: 是否递归删除目录。

        Returns:
            文件删除结果。
        """
        client = self._get_client(server_id)
        result = await client.post(
            "/api/files/delete",
            json={"path": path, "recursive": recursive},
            server_id=server_id,
            model=FileDeleteResult,
        )
        return cast(FileDeleteResult, result)

    # ------------------------------------------------------------------
    # 终端操作
    # ------------------------------------------------------------------

    async def create_terminal(
        self,
        server_id: str,
        shell: str = "/bin/bash",
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        remark: str = "",
    ) -> TerminalInfo:
        """在指定服务器上创建新的终端会话，返回 terminal_id。

        Args:
            server_id: 服务器标识。
            shell: shell 程序路径。
            cwd: 初始工作目录。
            env: 额外环境变量。
            remark: 终端用途备注，AI 创建终端时应主动填写。

        Returns:
            终端会话信息。
        """
        client = self._get_client(server_id)
        result = await client.post(
            "/api/terminals",
            json={
                "shell": shell,
                "cwd": cwd,
                "env": env,
                "remark": remark,
            },
            server_id=server_id,
            model=TerminalInfo,
        )
        return cast(TerminalInfo, result)

    async def list_terminals(self, server_id: str) -> list[TerminalInfo]:
        """列出指定服务器上所有活跃的终端会话。

        Args:
            server_id: 服务器标识。

        Returns:
            终端会话信息列表。
        """
        client = self._get_client(server_id)
        data = await client.get("/api/terminals", server_id=server_id)
        terminals = data.get("terminals", []) if isinstance(data, dict) else []
        return [TerminalInfo.model_validate(t) for t in terminals]

    async def exec_command(
        self,
        server_id: str,
        terminal_id: str,
        command: str,
        timeout: int = 30,
        use_sudo: bool = False,
    ) -> CommandResult:
        """在指定终端中执行命令，保留会话上下文。

        Args:
            server_id: 服务器标识。
            terminal_id: 终端 ID。
            command: 要执行的命令。
            timeout: 命令超时（秒）。
            use_sudo: 是否以 sudo 执行该命令（需后端配置 sudo.enabled=true 且 sudo.password）。

        Returns:
            命令执行结果。
        """
        client = self._get_client(server_id)
        result = await client.post(
            f"/api/terminals/{terminal_id}/exec",
            json={"command": command, "timeout": timeout, "use_sudo": use_sudo},
            server_id=server_id,
            model=CommandResult,
        )
        return cast(CommandResult, result)

    async def get_terminal(self, server_id: str, terminal_id: str) -> TerminalInfo:
        """获取终端会话信息。

        Args:
            server_id: 服务器标识。
            terminal_id: 终端 ID。

        Returns:
            终端会话信息。
        """
        client = self._get_client(server_id)
        result = await client.get(
            f"/api/terminals/{terminal_id}",
            server_id=server_id,
            model=TerminalInfo,
        )
        return cast(TerminalInfo, result)

    async def close_terminal(self, server_id: str, terminal_id: str) -> bool:
        """关闭指定终端会话。

        Args:
            server_id: 服务器标识。
            terminal_id: 终端 ID。

        Returns:
            是否成功关闭。
        """
        client = self._get_client(server_id)
        data = await client.delete(
            f"/api/terminals/{terminal_id}",
            server_id=server_id,
        )
        if isinstance(data, dict):
            return bool(data.get("closed", False))
        return True
