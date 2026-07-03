"""TerminalService 提权防御检测的单元测试。

覆盖 ``_check_unauthorized_privilege_escalation`` 的正例、负例与边界情况，
确保非 sudo 路径下的 pkexec/su/doas 等提权命令被准确拦截，同时不误伤
包含同名子串的普通命令。
"""

from __future__ import annotations

import pytest

from src.limits import Limits
from src.services.terminal_service import TerminalService
from src.utils.errors import InternalError


@pytest.fixture()
def service() -> TerminalService:
    """构造一个未启用 sudo 的 TerminalService 实例供测试使用。

    Returns:
        未启用 sudo 的终端服务实例。
    """
    return TerminalService(Limits())


class TestPrivilegeEscalationDetection:
    """``_check_unauthorized_privilege_escalation`` 行为测试。"""

    # ------------------------------------------------------------------
    # 正例：应被拦截的提权命令
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "command",
        [
            "pkexec pacman -Syu",
            "su root",
            "doas apk update",
            "gksu gedit /etc/fstab",
            "gksudo gedit /etc/fstab",
            "kdesu dolphin",
            # 日志中出现的实际绕过形态
            'script -q -c "pkexec pacman -Syu --noconfirm" /dev/null 2>&1',
            # 命令链中的提权
            "echo hi; pkexec whoami",
            "echo hi && su -c 'id'",
            "echo hi || doas id",
            "echo hi | pkexec tee /etc/test",
            # 反引号包裹
            "`pkexec id`",
            # 圆括号子shell
            "(pkexec id)",
        ],
    )
    def test_blocks_privilege_escalation_commands(
        self, service: TerminalService, command: str
    ) -> None:
        """所有禁用的提权命令都应被拦截并抛出 InternalError。"""
        with pytest.raises(InternalError) as exc_info:
            service._check_unauthorized_privilege_escalation(command)
        # 错误信息应包含提示使用 use_sudo
        assert "use_sudo" in exc_info.value.message

    # ------------------------------------------------------------------
    # 负例：不应被误伤的普通命令
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "command",
        [
            "ls -la",
            "pacman -Syu --noconfirm",
            "echo suppress the output",
            "cat result.txt",
            # sudo 不在禁用列表（提示词约束，不硬拦截）
            "sudo pacman -Syu",
            # 子串匹配不应误伤：pseudo、resume、result、purple
            "pseudo_command --flag",
            "resume the process",
            "cat result.log",
            "purple-background --enable",
            # 路径中包含 su 段
            "cat /usr/share/su-helper/readme.md",
            "ls /home/user/submissions",
        ],
    )
    def test_allows_normal_commands(
        self, service: TerminalService, command: str
    ) -> None:
        """普通命令（含与禁用词同子串的命令）不应被拦截。"""
        # 不抛异常即通过
        service._check_unauthorized_privilege_escalation(command)

    # ------------------------------------------------------------------
    # 边界：空命令与纯空白
    # ------------------------------------------------------------------

    def test_empty_command_passes(self, service: TerminalService) -> None:
        """空命令不应被拦截。"""
        service._check_unauthorized_privilege_escalation("")

    def test_whitespace_only_command_passes(self, service: TerminalService) -> None:
        """纯空白命令不应被拦截。"""
        service._check_unauthorized_privilege_escalation("   ")

    # ------------------------------------------------------------------
    # 错误信息可读性
    # ------------------------------------------------------------------

    def test_error_message_contains_matched_command(
        self, service: TerminalService
    ) -> None:
        """错误信息应包含被命中的具体命令名，便于定位。"""
        with pytest.raises(InternalError) as exc_info:
            service._check_unauthorized_privilege_escalation("pkexec whoami")
        assert "pkexec" in exc_info.value.message
