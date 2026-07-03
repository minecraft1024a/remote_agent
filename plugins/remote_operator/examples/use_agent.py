"""使用 RemoteOperatorAgent 的示例。

展示其他 Chatter 或插件如何获取 Agent 并执行远程操控任务。
"""

from __future__ import annotations

import asyncio

from src.app.plugin_system.api import agent_api, plugin_api


async def demo_usage() -> None:
    """演示如何获取并执行 RemoteOperatorAgent。"""
    # 1. 通过签名获取 Agent 类
    agent_cls = agent_api.get_agent_class(
        "remote_operator:agent:remote_operator_agent"
    )
    if agent_cls is None:
        print("remote_operator_agent 未注册，请先加载插件")
        return

    # 2. 实例化 Agent（需要 stream_id 和所属插件实例）
    #    实际使用时，stream_id 与 plugin 由 Chatter 框架注入
    #    这里仅展示调用形式
    plugin = plugin_api.get_plugin("remote_operator")
    if plugin is None:
        print("remote_operator 插件实例未找到")
        return

    agent = agent_cls(stream_id="demo_stream", plugin=plugin)

    # 3. 执行远程操控任务
    task = "查看 srv-a 上 /var/log/syslog 的最后 50 行，如果发现 ERROR 就汇总出来"
    success, result = await agent.execute(task_description=task)

    if success:
        print(f"任务完成:\n{result}")
    else:
        print(f"任务失败: {result}")


if __name__ == "__main__":
    asyncio.run(demo_usage())
