"""server_manager 插件包。

以 Service 形式对外提供多服务器远程管理能力（文件操作 + 终端会话）。
不注册 Tool/Action，仅通过 service_api.get_service() 供其他插件调用。
"""
