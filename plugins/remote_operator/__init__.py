"""remote_operator 插件。

提供基于 Agent 的远程服务器操控能力：通过内部调用 ServerManagerService，
将文件操作与终端执行封装为 Agent 私有工具，供 LLM 在子代理流程中
完成对远程服务器的浏览、编辑、命令执行等任务。
"""
