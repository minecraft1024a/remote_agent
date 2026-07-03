"""限制常量与校验工具。

集中定义后端服务的各项安全限制，并提供校验方法。
运行时限制值由配置注入，本模块提供默认值与校验逻辑。
"""

from __future__ import annotations

from .utils.config import LimitsSection


class Limits:
    """运行时限制校验器。

    持有当前生效的限制值，提供超限判定方法。
    """

    def __init__(self, limits: LimitsSection | None = None) -> None:
        """初始化限制校验器。

        Args:
            limits: 限制配置段。为 None 时使用默认值。
        """
        section = limits or LimitsSection()
        self.max_file_read: int = section.max_file_read
        self.max_file_write: int = section.max_file_write
        self.max_command_output: int = section.max_command_output
        self.max_command_timeout: int = section.max_command_timeout
        self.terminal_idle_timeout: int = section.terminal_idle_timeout
        self.max_terminals: int = section.max_terminals

    def check_file_read_size(self, size: int) -> None:
        """校验文件读取大小是否超限。

        Args:
            size: 文件大小（字节）。

        Raises:
            LimitExceededError: 超限时抛出。
        """
        from .utils.errors import LimitExceededError

        if size > self.max_file_read:
            raise LimitExceededError(
                code=413,
                message=f"文件大小 {size} 超过读取上限 {self.max_file_read}",
            )

    def check_file_write_size(self, size: int) -> None:
        """校验文件写入大小是否超限。

        Args:
            size: 待写入内容大小（字节）。

        Raises:
            LimitExceededError: 超限时抛出。
        """
        from .utils.errors import LimitExceededError

        if size > self.max_file_write:
            raise LimitExceededError(
                code=413,
                message=f"写入内容大小 {size} 超过写入上限 {self.max_file_write}",
            )

    def check_command_timeout(self, timeout: int) -> None:
        """校验命令超时是否超限。

        Args:
            timeout: 请求的超时秒数。

        Raises:
            LimitExceededError: 超限时抛出。
        """
        from .utils.errors import LimitExceededError

        if timeout > self.max_command_timeout:
            raise LimitExceededError(
                code=400,
                message=f"命令超时 {timeout} 超过上限 {self.max_command_timeout}",
            )

    def check_terminal_count(self, current: int) -> None:
        """校验终端数量是否超限。

        Args:
            current: 当前终端数量。

        Raises:
            LimitExceededError: 超限时抛出。
        """
        from .utils.errors import LimitExceededError

        if current >= self.max_terminals:
            raise LimitExceededError(
                code=429,
                message=f"终端数量 {current} 已达上限 {self.max_terminals}",
            )

    def truncate_output(self, output: str) -> tuple[str, bool]:
        """截断命令输出至捕获上限。

        Args:
            output: 原始输出字符串。

        Returns:
            (截断后的输出, 是否发生了截断)
        """
        encoded = output.encode("utf-8", errors="replace")
        if len(encoded) <= self.max_command_output:
            return output, False
        truncated = encoded[: self.max_command_output].decode("utf-8", errors="replace")
        return truncated, True
