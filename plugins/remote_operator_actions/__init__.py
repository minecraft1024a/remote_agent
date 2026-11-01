"""remote_operator_actions 插件。

向主程序注册一组远程服务器操作 Action。它们通过 ``go_activate()``
返回 False 从普通聊天的 LLM 工具列表中筛除，不接入 remote_operator Agent。
"""
