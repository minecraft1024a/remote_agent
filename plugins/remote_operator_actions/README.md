# remote_operator_actions

本插件向主程序注册 11 个 Action，复用 `remote_operator` 原有私有工具的服务器查询、文件操作、终端管理和任务结果提交逻辑。每个 Action 都继承 `HiddenRemoteAction`，其 `go_activate()` 固定返回 `False`，主程序筛选普通聊天可用组件时会将它们剔除，不会把 schema 发给大模型。

组件仍注册在主程序中，程序或其他插件可通过组件签名调用。它们不接入 `remote_operator` Agent。

本插件依赖 `server_manager:service:server_manager`。插件清单中的 Action 保持 `enabled: true`，以便注册和程序调用；隐藏由 Action 的运行时激活筛选实现。

| Action 签名 | 功能 |
|---|---|
| `remote_operator_actions:action:list_servers` | 列出配置的服务器及用途描述 |
| `remote_operator_actions:action:list_files` | 列出远程目录 |
| `remote_operator_actions:action:read_file` | 读取远程文件 |
| `remote_operator_actions:action:write_file` | 写入远程文件 |
| `remote_operator_actions:action:edit_file` | 搜索替换方式编辑文件 |
| `remote_operator_actions:action:delete_file` | 删除远程文件或目录 |
| `remote_operator_actions:action:create_terminal` | 创建终端会话 |
| `remote_operator_actions:action:exec_command` | 在终端中执行命令 |
| `remote_operator_actions:action:list_terminals` | 列出终端会话 |
| `remote_operator_actions:action:close_terminal` | 关闭终端会话 |
| `remote_operator_actions:action:finish_task` | 提交任务结果 |

其他插件可通过 `action_api.execute_action()` 和对应签名执行这些组件。执行时需要传入所属插件实例与触发消息；具体参数与结果结构由各 Action 的 `execute()` 声明。
