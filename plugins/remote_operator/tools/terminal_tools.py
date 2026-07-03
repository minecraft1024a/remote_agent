"""终端操作工具。

封装 ServerManagerService 的终端能力，提供创建终端、执行命令、
列出终端、关闭终端等工具供 Agent 调用。

终端会话采用「先申请 → 获取 terminal_id → 执行命令」模式，
每个 terminal_id 上下文独立且保持命令历史（环境变量、cd 等会保留）。
"""

from __future__ import annotations

from typing import Annotated, Any

from src.app.plugin_system.base import BaseTool

from ._base import get_server_manager_service


class CreateTerminalTool(BaseTool):
    """在指定服务器上创建新的终端会话。"""

    tool_name: str = "create_terminal"
    tool_description: str = (
        "在指定服务器上创建新的终端会话，返回 terminal_id。"
        "后续的 exec_command 需传入此 terminal_id，同一终端内命令上下文保留。"
        "remark 参数务必填写有意义的用途说明，便于管理多个终端。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
        remark: Annotated[str, "终端用途备注，如「编译前端项目」「查看日志」"],
        shell: Annotated[str, "shell 程序路径，默认 /bin/bash"] = "/bin/bash",
        cwd: Annotated[str, "初始工作目录，默认为用户家目录"] = "",
    ) -> tuple[bool, str | dict]:
        """执行创建终端逻辑。

        Args:
            server_id: 目标服务器 ID。
            remark: 终端用途备注。
            shell: shell 程序路径。
            cwd: 初始工作目录。

        Returns:
            tuple[bool, str | dict]: (是否成功, 终端信息或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            result = await service.create_terminal(
                server_id,
                shell=shell,
                cwd=cwd or None,
                remark=remark,
            )
        except Exception as exc:
            return False, f"创建终端失败: {exc}"

        return True, result.model_dump()


class ExecCommandTool(BaseTool):
    """在指定终端中执行命令。"""

    tool_name: str = "exec_command"
    tool_description: str = (
        "在指定终端中执行命令，保留会话上下文（环境变量、cd 等会保留）。"
        "根据 exit_code 判断成功与否，失败时查看 stderr 分析原因。"
        "timeout 为单条命令超时（秒），上限 120。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
        terminal_id: Annotated[str, "终端 ID（通过 create_terminal 获取）"],
        command: Annotated[str, "要执行的 shell 命令"],
        timeout: Annotated[int, "命令超时秒数，默认 30，上限 120"] = 30,
        use_sudo: Annotated[
            bool, "是否以 sudo 执行（需后端配置 sudo 支持）"
        ] = False,
    ) -> tuple[bool, str | dict]:
        """执行命令逻辑。

        Args:
            server_id: 目标服务器 ID。
            terminal_id: 终端 ID。
            command: 命令文本。
            timeout: 超时秒数。
            use_sudo: 是否 sudo。

        Returns:
            tuple[bool, str | dict]: (是否成功, 命令结果或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            result = await service.exec_command(
                server_id,
                terminal_id,
                command,
                timeout=timeout,
                use_sudo=use_sudo,
            )
        except Exception as exc:
            return False, f"执行命令失败: {exc}"

        data = result.model_dump()
        # 在结果中标注是否成功，便于 LLM 快速判断
        data["success"] = result.exit_code == 0
        return True, data


class ListTerminalsTool(BaseTool):
    """列出指定服务器上所有活跃的终端。"""

    tool_name: str = "list_terminals"
    tool_description: str = (
        "列出指定服务器上所有活跃的终端会话，包含 terminal_id、备注、"
        "工作目录等信息。用于在多个终端间定位或确认状态。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
    ) -> tuple[bool, str | dict]:
        """执行列出终端逻辑。

        Args:
            server_id: 目标服务器 ID。

        Returns:
            tuple[bool, str | dict]: (是否成功, 终端列表或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            terminals: list[Any] = await service.list_terminals(server_id)
        except Exception as exc:
            return False, f"列出终端失败: {exc}"

        data = [t.model_dump() for t in terminals]
        return True, {"terminals": data, "count": len(data)}


class CloseTerminalTool(BaseTool):
    """关闭指定终端会话。"""

    tool_name: str = "close_terminal"
    tool_description: str = (
        "关闭指定终端会话，释放资源。任务完成后应主动关闭不再使用的终端。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
        terminal_id: Annotated[str, "要关闭的终端 ID"],
    ) -> tuple[bool, str | dict]:
        """执行关闭终端逻辑。

        Args:
            server_id: 目标服务器 ID。
            terminal_id: 终端 ID。

        Returns:
            tuple[bool, str | dict]: (是否成功, 关闭结果或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            closed = await service.close_terminal(server_id, terminal_id)
        except Exception as exc:
            return False, f"关闭终端失败: {exc}"

        return True, {"terminal_id": terminal_id, "closed": closed}
