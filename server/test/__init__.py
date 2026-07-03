"""terminal_service 提权防御检测的单元测试。

覆盖 TerminalService._check_unauthorized_privilege_escalation 的
正例、负例与边界情况，确保非 sudo 路径下的 pkexec/su/doas 等提权
命令被准确拦截，同时不误伤普通命令。
"""
