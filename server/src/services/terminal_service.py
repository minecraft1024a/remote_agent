"""终端会话管理。

使用 asyncio.subprocess 维护每个 terminal_id 对应的持久 shell 进程，
采用「哨兵分隔」方案捕获命令输出。

会话生命周期：
1. 创建终端时启动 shell 子进程，生成唯一 terminal_id。
2. 执行命令时向 stdin 写入命令 + 哨兵回显，读取 stdout/stderr 直到哨兵。
3. 空闲超过配置阈值后自动回收。
4. 显式关闭或进程退出后销毁会话。
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import shlex
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..limits import Limits
from ..utils.config import SudoSection
from ..utils.errors import CommandTimeoutError, InternalError, LimitExceededError, NotFoundError
from ..utils.models import CommandResult, TerminalInfo


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 UTC 字符串。

    Returns:
        ISO 8601 格式的时间字符串。
    """
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_terminal_id() -> str:
    """生成全局唯一的终端 ID。

    Returns:
        格式为 term_ + 8 位随机十六进制的终端 ID。
    """
    return f"term_{secrets.token_hex(4)}"


@dataclass
class TerminalSession:
    """单个终端会话的运行时状态。"""

    terminal_id: str
    created_at: str
    cwd: str
    remark: str = ""
    process: asyncio.subprocess.Process | None = None
    last_active: float = field(default_factory=time.monotonic)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _closed: bool = False

    @property
    def alive(self) -> bool:
        """终端是否仍然存活。"""
        if self._closed:
            return False
        if self.process is None:
            return False
        return self.process.returncode is None


class TerminalService:
    """终端会话管理服务。

    维护所有活跃终端会话，提供创建、执行、列举、查询与关闭能力。
    """

    def __init__(self, limits: Limits, sudo: SudoSection | None = None) -> None:
        """初始化终端服务。

        Args:
            limits: 限制校验器。
            sudo: sudo 配置段。为 None 时禁用 sudo 执行。
        """
        self._limits = limits
        self._sudo = sudo or SudoSection()
        self._sessions: dict[str, TerminalSession] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._cleanup_started = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start_cleanup_loop(self) -> None:
        """启动空闲终端自动回收后台任务。

        幂等，多次调用只启动一次。
        """
        if self._cleanup_started:
            return
        self._cleanup_started = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 无事件循环时跳过（测试场景）
            return
        self._cleanup_task = loop.create_task(self._cleanup_loop(), name="terminal_idle_cleanup")

    async def shutdown(self) -> None:
        """关闭所有终端会话并停止回收任务。"""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        self._cleanup_started = False

        for session in list(self._sessions.values()):
            await self._terminate_session(session)
        self._sessions.clear()

    # ------------------------------------------------------------------
    # 终端操作
    # ------------------------------------------------------------------

    async def create_terminal(
        self,
        shell: str = "/bin/bash",
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        remark: str = "",
    ) -> TerminalInfo:
        """创建新的终端会话。

        Args:
            shell: shell 程序路径。
            cwd: 初始工作目录。为 None 时使用进程当前目录。
            env: 额外环境变量。
            remark: 终端用途备注。

        Returns:
            终端会话信息。

        Raises:
            LimitExceededError: 终端数量超限。
            InternalError: shell 启动失败。
        """
        self._limits.check_terminal_count(len(self._sessions))

        resolved_cwd = cwd or os.getcwd()
        if not os.path.isdir(resolved_cwd):
            raise InternalError(f"工作目录不存在: {resolved_cwd}")

        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)

        terminal_id = _generate_terminal_id()
        created_at = _now_iso()

        try:
            process = await asyncio.create_subprocess_exec(
                shell,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=resolved_cwd,
                env=merged_env,
            )
        except FileNotFoundError as exc:
            raise InternalError(f"shell 程序不存在: {shell}") from exc
        except OSError as exc:
            raise InternalError(f"启动 shell 失败: {exc}") from exc

        session = TerminalSession(
            terminal_id=terminal_id,
            created_at=created_at,
            cwd=resolved_cwd,
            remark=remark,
            process=process,
        )
        self._sessions[terminal_id] = session

        # 探测真实工作目录
        await self._probe_cwd(session)

        return self._to_info(session)

    async def list_terminals(self) -> list[TerminalInfo]:
        """列出所有活跃的终端会话。

        Returns:
            终端会话信息列表。
        """
        # 先清理已退出的会话
        self._purge_dead()
        return [self._to_info(session) for session in self._sessions.values()]

    async def get_terminal(self, terminal_id: str) -> TerminalInfo:
        """获取终端会话信息。

        Args:
            terminal_id: 终端 ID。

        Returns:
            终端会话信息。

        Raises:
            NotFoundError: 终端不存在或已关闭。
        """
        session = self._sessions.get(terminal_id)
        if session is None:
            raise NotFoundError(f"终端不存在: {terminal_id}")
        self._purge_dead()
        if not session.alive:
            raise NotFoundError(f"终端已关闭: {terminal_id}")
        return self._to_info(session)

    async def exec_command(
        self,
        terminal_id: str,
        command: str,
        timeout: int = 30,
        use_sudo: bool = False,
    ) -> CommandResult:
        """在指定终端中执行命令。

        命令在持久 shell 上下文中运行，环境变量与工作目录变更会保留。

        Args:
            terminal_id: 终端 ID。
            command: 要执行的命令。
            timeout: 命令超时（秒）。
            use_sudo: 是否以 sudo 执行（需后端配置 sudo.enabled=true 且 sudo.password）。

        Returns:
            命令执行结果。

        Raises:
            NotFoundError: 终端不存在或已关闭。
            LimitExceededError: 超时值超限。
            CommandTimeoutError: 命令执行超时。
            InternalError: 终端 I/O 异常或 sudo 未启用/未配置。
        """
        self._limits.check_command_timeout(timeout)

        # sudo 校验
        if use_sudo:
            if not self._sudo.enabled:
                raise InternalError("后端未启用 sudo 执行（sudo.enabled=false）")
            if not self._sudo.password:
                raise InternalError("后端未配置 sudo 密码（sudo.password 为空）")

        session = self._sessions.get(terminal_id)
        if session is None:
            raise NotFoundError(f"终端不存在: {terminal_id}")
        self._purge_dead()
        if not session.alive:
            raise NotFoundError(f"终端已关闭: {terminal_id}")

        async with session._lock:
            result = await self._exec_in_session(session, command, timeout, use_sudo=use_sudo)
            session.last_active = time.monotonic()
            # 探测可能变更的工作目录
            await self._probe_cwd(session)
            return result

    async def close_terminal(self, terminal_id: str) -> bool:
        """关闭指定终端会话。

        Args:
            terminal_id: 终端 ID。

        Returns:
            是否成功关闭。

        Raises:
            NotFoundError: 终端不存在。
        """
        session = self._sessions.get(terminal_id)
        if session is None:
            raise NotFoundError(f"终端不存在: {terminal_id}")
        await self._terminate_session(session)
        self._sessions.pop(terminal_id, None)
        return True

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    async def _exec_in_session(
        self,
        session: TerminalSession,
        command: str,
        timeout: int,
        *,
        use_sudo: bool = False,
    ) -> CommandResult:
        """在会话中执行单条命令（哨兵分隔方案）。

        Args:
            session: 终端会话。
            command: 命令文本。
            timeout: 超时秒数。
            use_sudo: 是否以 sudo 执行。

        Returns:
            命令执行结果。

        Raises:
            CommandTimeoutError: 命令超时。
            InternalError: I/O 异常。
        """
        assert session.process is not None
        assert session.process.stdin is not None
        assert session.process.stdout is not None
        assert session.process.stderr is not None

        # 防御性检测：非 sudo 路径下禁止使用会挂起的提权命令。
        # 后端服务通常以 systemd 运行，无 polkit 认证代理、无可交互 TTY，
        # pkexec/su/doas 等会卡在认证步骤永久挂起，导致命令超时并占用会话。
        # 这类命令必须改走 use_sudo=True（由后端 sudo -S 安全提权）。
        if not use_sudo:
            self._check_unauthorized_privilege_escalation(command)

        sentinel = f"__CMD_DONE_{secrets.token_hex(8)}__"
        start = time.monotonic()

        # 向 stdin 写入命令 + 哨兵回显
        if use_sudo:
            # 关键：持久 shell 逐行消费 stdin，不能用「先写密码行再写 sudo 行」的方式
            # —— 那样密码会被 bash 当普通命令执行，且 sudo 启动后会吃掉下一行（哨兵行）当密码。
            # 正确做法：通过 echo <密码> | sudo -S ... 把密码经由子管道喂给 sudo，
            # 密码不进 shell 主 stdin，哨兵行仍由 bash 正常执行。
            escaped_cmd = command.replace("'", "'\"'\"'")
            quoted_pwd = shlex.quote(self._sudo.password)
            payload = f"echo {quoted_pwd} | sudo -S -p '' bash -c '{escaped_cmd}'\n"
            payload += f'echo "{sentinel}:$?"\n'
        else:
            payload = f"{command}\n"
            payload += f'echo "{sentinel}:$?"\n'
        # 调试日志：打印实际写入 stdin 的 payload（屏蔽 sudo 密码）
        safe_payload = payload.replace(self._sudo.password, "***") if use_sudo else payload
        print(f"[{session.terminal_id}][stdin-payload] {safe_payload!r}")
        session.process.stdin.write(payload.encode())
        try:
            await session.process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise InternalError(f"终端 stdin 写入失败: {exc}") from exc

        # 读取 stdout 直到哨兵行
        stdout_buf: list[str] = []
        stderr_buf: list[str] = []
        sentinel_pattern = re.compile(re.escape(sentinel) + r":(\d+)")
        exit_code = 0
        sentinel_found = False

        async def _read_stderr() -> None:
            assert session.process is not None
            assert session.process.stderr is not None
            try:
                while True:
                    line_bytes = await session.process.stderr.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace")
                    stderr_buf.append(line)
                    print(f"[{session.terminal_id}][stderr] {line.rstrip()}")
            except Exception as exc:
                pass  # stderr 读取异常不影响 stdout 主流程

        stderr_task = asyncio.create_task(_read_stderr())

        try:
            while True:
                try:
                    line_bytes = await asyncio.wait_for(
                        session.process.stdout.readline(), timeout=timeout
                    )
                except asyncio.TimeoutError as exc:
                    # 超时时打印已读取的部分输出，便于诊断 sudo 卡住的原因
                    elapsed = time.monotonic() - start
                    partial = "".join(stdout_buf)
                    print(
                        f"[{session.terminal_id}][TIMEOUT] "
                        f"命令执行超时（{timeout}秒），已耗时 {elapsed:.2f}s, "
                        f"use_sudo={use_sudo}, command={command!r}, "
                        f"已读取 stdout 行数={len(stdout_buf)}, "
                        f"stderr 行数={len(stderr_buf)}, "
                        f"部分 stdout 输出:\n{partial}"
                    )
                    raise CommandTimeoutError(
                        f"命令执行超时（{timeout}秒），会话已保留"
                    ) from exc

                if not line_bytes:
                    # stdout EOF，shell 可能已退出
                    raise InternalError("终端 stdout 意外关闭")

                line = line_bytes.decode("utf-8", errors="replace")
                # 调试日志：实时打印 stdout 每一行
                print(f"[{session.terminal_id}][stdout] {line.rstrip()}")
                match = sentinel_pattern.search(line)
                if match:
                    exit_code = int(match.group(1))
                    sentinel_found = True
                    break
                stdout_buf.append(line)
        finally:
            # 给 stderr 一点时间排空
            try:
                await asyncio.wait_for(stderr_task, timeout=0.5)
            except asyncio.TimeoutError:
                stderr_task.cancel()

        if not sentinel_found:
            raise InternalError("未捕获到命令完成哨兵")

        stdout = "".join(stdout_buf)
        stderr = "".join(stderr_buf)

        # 输出截断
        stdout, stdout_truncated = self._limits.truncate_output(stdout)
        stderr, stderr_truncated = self._limits.truncate_output(stderr)

        if stdout_truncated:
            stderr += f"\n[stdout 已截断，超过 {self._limits.max_command_output} 字节]"
        if stderr_truncated:
            stderr += f"\n[stderr 已截断，超过 {self._limits.max_command_output} 字节]"

        duration_ms = int((time.monotonic() - start) * 1000)
        # 调试日志：命令执行结束汇总
        print(
            f"[{session.terminal_id}][done] exit_code={exit_code}, "
            f"duration={duration_ms}ms, use_sudo={use_sudo}, "
            f"stdout_bytes={len(stdout)}, stderr_bytes={len(stderr)}, "
            f"command={command!r}"
        )
        return CommandResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
        )

    # 禁止在非 sudo 路径下使用的提权命令词。
    # 选取在 systemd/无 TTY/无 polkit 环境下几乎必然挂起或无法认证的程序；
    # sudo 不在此列，因为 use_sudo=True 才是受支持的提权路径，而手动 sudo
    # 已由提示词约束，且无密码 sudo 仍可能工作，不在此硬拦截。
    _FORBIDDEN_PRIV_ESCALATION_CMDS: tuple[str, ...] = (
        "pkexec",
        "gksu",
        "gksudo",
        "kdesu",
        "doas",
        "su",
    )

    def _check_unauthorized_privilege_escalation(self, command: str) -> None:
        """检测非 sudo 路径下是否使用了会挂起的提权命令。

        后端服务通常以 systemd 服务运行，没有图形会话、没有 polkit 认证
        代理、也没有可交互 TTY。此时 pkexec/su/doas 等会卡在认证步骤
        永久挂起，导致命令超时并长时间占用终端会话。这类命令必须改走
        use_sudo=True，由后端通过 sudo -S 在子管道内安全提权。

        采用词边界匹配，避免误伤包含这些子串的普通命令（如 ``suppress``、
        ``result``）。命中时抛出 InternalError，由全局异常处理器转换为
        统一错误响应，使调用方（Agent）能立即得到明确反馈而非超时。

        Args:
            command: 待执行的命令文本。

        Raises:
            InternalError: 命令中检测到禁用的提权程序时抛出。
        """
        # 构建词边界正则：匹配作为独立命令词出现的禁用程序名。
        # 前缀允许：字符串起始、空白、或 shell 命令/参数分隔符
        # （含引号，以覆盖 script -c "pkexec ..." 这类间接调用形态）。
        # 后缀允许：空白或字符串结束（这些命令后必然跟参数或结束）。
        pattern = re.compile(
            r"(?:^|[\s;&|`(\"'])("
            + "|".join(re.escape(c) for c in self._FORBIDDEN_PRIV_ESCALATION_CMDS)
            + r")(?=\s|$)"
        )
        match = pattern.search(command)
        if match is None:
            return
        matched = match.group(1)
        raise InternalError(
            f"检测到禁用的提权命令 '{matched}'：在非 sudo 路径下使用 "
            f"{self._FORBIDDEN_PRIV_ESCALATION_CMDS} 等提权程序会导致后端"
            "在 systemd/无 TTY 环境下永久挂起。请改用 exec_command 的 "
            "use_sudo=true 参数提权，不要在 command 中拼接提权命令。"
        )

    async def _probe_cwd(self, session: TerminalSession) -> None:
        """探测终端当前工作目录并更新会话状态。

        通过执行 pwd 获取，失败时保持原值不变。

        Args:
            session: 终端会话。
        """
        if not session.alive or session.process is None:
            return
        assert session.process.stdin is not None
        assert session.process.stdout is not None

        sentinel = f"__PWD_PROBE_{secrets.token_hex(8)}__"
        payload = f'pwd; echo "{sentinel}"\n'
        session.process.stdin.write(payload.encode())
        try:
            await session.process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            return

        try:
            while True:
                line_bytes = await asyncio.wait_for(
                    session.process.stdout.readline(), timeout=5
                )
                if not line_bytes:
                    return
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line == sentinel:
                    return
                if line and not line.startswith(sentinel):
                    session.cwd = line
        except asyncio.TimeoutError:
            return

    async def _terminate_session(self, session: TerminalSession) -> None:
        """终止终端会话的 shell 进程。

        Args:
            session: 终端会话。
        """
        if session._closed:
            return
        session._closed = True
        process = session.process
        if process is None:
            return
        if process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=3)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
                except Exception:
                    pass
        # 关闭管道（stdin 可直接关闭，stdout/stderr 通过 feed_eof 标记结束）
        if process.stdin is not None:
            try:
                process.stdin.close()
            except Exception:
                pass
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.feed_eof()
                except Exception:
                    pass

    def _purge_dead(self) -> None:
        """清理已退出的终端会话。"""
        dead_ids = [
            tid for tid, session in self._sessions.items() if not session.alive
        ]
        for tid in dead_ids:
            self._sessions.pop(tid, None)

    async def _cleanup_loop(self) -> None:
        """空闲终端自动回收循环。"""
        while True:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            now = time.monotonic()
            timeout = self._limits.terminal_idle_timeout
            expired_ids = [
                tid
                for tid, session in self._sessions.items()
                if session.alive and (now - session.last_active) > timeout
            ]
            for tid in expired_ids:
                session = self._sessions.pop(tid, None)
                if session is not None:
                    await self._terminate_session(session)

    @staticmethod
    def _to_info(session: TerminalSession) -> TerminalInfo:
        """将会话状态转为 TerminalInfo 模型。

        Args:
            session: 终端会话。

        Returns:
            终端会话信息。
        """
        return TerminalInfo(
            terminal_id=session.terminal_id,
            created_at=session.created_at,
            cwd=session.cwd,
            alive=session.alive,
            remark=session.remark,
        )
