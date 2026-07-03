"""server_lister 插件。

提供独立的 ListServersTool 工具，供 LLM 在调用 remote_operator Agent
执行远程操控前，先获取已配置的远程服务器列表并据此决策 server_id：
单台直接使用，多台且用户未指定时向用户询问。
"""
