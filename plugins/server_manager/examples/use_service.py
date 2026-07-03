"""其他插件使用 ServerManagerService 的示例。

展示如何通过 service_api 获取 Service 实例并调用文件与终端接口。
"""

from __future__ import annotations

import asyncio

from src.app.plugin_system.api.service_api import get_service

from plugins.server_manager.exceptions import ServerManagerError
from plugins.server_manager.models import FileEditItem


async def demo_usage() -> None:
    """演示如何获取并使用 ServerManagerService。"""
    # 1. 获取 Service 实例
    service = get_service("server_manager:service:server_manager")
    if service is None:
        print("server_manager 服务未注册，请先加载插件")
        return

    # 为类型检查方便，直接访问方法（运行时 service 是 ServerManagerService 实例）
    server_id = "srv-a"

    try:
        # 2. 列出已配置的服务器
        servers = service.list_servers()
        print(f"已配置服务器: {[s.model_dump() for s in servers]}")

        # 3. 列出目录
        file_list = await service.list_files(server_id, "/home")
        print(f"目录内容: {file_list.model_dump()}")

        # 4. 读取文件
        read_result = await service.read_file(server_id, "/home/user/main.py")
        print(f"文件内容（前 200 字符）: {read_result.content[:200]}")

        # 5. 写入文件
        write_result = await service.write_file(
            server_id,
            "/tmp/demo.txt",
            "hello from server_manager\n",
        )
        print(f"写入结果: {write_result.model_dump()}")

        # 6. diff 编辑文件
        edit_result = await service.edit_file(
            server_id,
            "/tmp/demo.txt",
            edits=[FileEditItem(old_text="hello", new_text="你好")],
        )
        print(f"编辑结果: applied={edit_result.applied}/{edit_result.total}")

        # 7. 创建终端（填写有意义的 remark）
        terminal = await service.create_terminal(
            server_id,
            remark="示例：编译项目",
        )
        print(f"终端 ID: {terminal.terminal_id}")

        # 8. 执行命令（上下文保留）
        result1 = await service.exec_command(
            server_id,
            terminal.terminal_id,
            "cd /home/user",
        )
        print(f"cd 结果: exit_code={result1.exit_code}")

        result2 = await service.exec_command(
            server_id,
            terminal.terminal_id,
            "pwd",  # 应显示 /home/user
        )
        print(f"pwd 结果: stdout={result2.stdout.strip()}")

        # 8.5 以 sudo 执行命令（需后端配置 sudo.enabled=true 且 sudo.password）
        result_sudo = await service.exec_command(
            server_id,
            terminal.terminal_id,
            "whoami",  # sudo 执行时应返回 root
            use_sudo=True,
        )
        print(f"sudo whoami 结果: stdout={result_sudo.stdout.strip()}")

        # 9. 列出终端
        terminals = await service.list_terminals(server_id)
        print(f"活跃终端: {[t.terminal_id for t in terminals]}")

        # 10. 关闭终端
        closed = await service.close_terminal(server_id, terminal.terminal_id)
        print(f"终端已关闭: {closed}")

        # 11. 删除文件
        delete_result = await service.delete_file(server_id, "/tmp/demo.txt")
        print(f"删除结果: {delete_result.model_dump()}")

    except ServerManagerError as exc:
        print(f"服务器管理错误: [{exc.server_id}] {exc.code}: {exc.message}")


if __name__ == "__main__":
    asyncio.run(demo_usage())
