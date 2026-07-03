"""使用 ListServersTool 的示例。

展示其他 Chatter 或插件如何获取并调用 list_servers 工具，
以及 LLM 在远程操控流程中应如何依据返回结果决策 server_id。

注意：本示例假设 Neo-MoFox 框架已加载 server_lister 与 server_manager
插件。实际运行时，工具实例化由框架的 tool call 调度器自动完成，
这里仅展示手动调用的形式用于演示与测试。
"""

from __future__ import annotations

import asyncio

from src.app.plugin_system.api import plugin_api


async def demo_usage() -> None:
    """演示如何获取并执行 list_servers 工具。"""
    # 1. 获取 server_lister 插件实例
    plugin = plugin_api.get_plugin("server_lister")
    if plugin is None:
        print("server_lister 插件实例未找到，请先加载插件")
        return

    # 2. 从插件的 get_components() 获取 Tool 类并实例化
    #    实际使用时，工具由框架的 tool call 调度器自动实例化与执行，
    #    这里仅展示手动调用形式
    component_classes = plugin.get_components()
    tool_cls = component_classes[0]  # ListServersTool
    tool = tool_cls(plugin=plugin)

    # 3. 执行工具
    success, result = await tool.execute()

    if not success:
        print(f"获取服务器列表失败: {result}")
        return

    # 4. 依据返回结果决策（模拟 LLM 的决策逻辑）
    servers = result["servers"]
    count = result["count"]
    print(f"共发现 {count} 台服务器:")
    for s in servers:
        print(f"  - {s['id']}: {s['name']} ({s['base_url']})")

    if count == 0:
        print("没有可用的服务器，请检查 server_manager 配置")
    elif count == 1:
        server_id = servers[0]["id"]
        print(f"\n仅一台服务器，直接使用 server_id={server_id} 调用 remote_operator Agent")
    else:
        print("\n多台服务器，若用户未指定目标，应向用户询问要操作哪一台")


if __name__ == "__main__":
    asyncio.run(demo_usage())
