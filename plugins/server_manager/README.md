# server_manager

Neo-MoFox 插件，以 **Service** 形式对外提供多服务器远程管理能力。

## 定位

`server_manager` 不注册 Tool、Action 或其他 LLM 直接可见的组件，仅通过 `get_components()` 返回 `[ServerManagerService]`。

其他插件通过以下方式获取 Service 并调用：

```python
from src.app.plugin_system.api import service_api

service = service_api.get_service("server_manager:service:server_manager")
if service is not None:
    result = await service.list_files(server_id="srv-a", path="/home")
```

## 配置

配置文件路径：`config/plugins/server_manager/config.toml`

```toml
[plugin]
enabled = true

[client]
request_timeout = 30   # HTTP 请求超时（秒）

[[servers]]
id = "srv-a"
name = "生产服务器 A"
base_url = "http://192.168.1.100:8421"
token = "secret-token-a"

[[servers]]
id = "srv-b"
name = "开发服务器 B"
base_url = "http://10.0.0.50:8421"
token = "secret-token-b"
```

## Service 方法

### 服务器管理

| 方法 | 说明 |
|------|------|
| `list_servers() -> list[ServerInfo]` | 列出所有已配置的服务器（不含 token） |
| `get_server(server_id) -> ServerInfo \| None` | 获取指定服务器信息 |

### 文件操作

| 方法 | 说明 |
|------|------|
| `list_files(server_id, path) -> FileListResult` | 列出目录内容 |
| `read_file(server_id, path, encoding) -> FileReadResult` | 读取文件 |
| `write_file(server_id, path, content, encoding) -> FileWriteResult` | 写入文件 |
| `edit_file(server_id, path, edits, encoding) -> FileEditResult` | diff 编辑文件 |
| `delete_file(server_id, path, recursive) -> FileDeleteResult` | 删除文件/目录 |

### 终端操作

| 方法 | 说明 |
|------|------|
| `create_terminal(server_id, shell, cwd, env, remark) -> TerminalInfo` | 创建终端 |
| `list_terminals(server_id) -> list[TerminalInfo]` | 列出所有终端 |
| `exec_command(server_id, terminal_id, command, timeout, use_sudo) -> CommandResult` | 执行命令（use_sudo=true 时以 sudo 执行，需后端配置 sudo） |
| `get_terminal(server_id, terminal_id) -> TerminalInfo` | 获取终端信息 |
| `close_terminal(server_id, terminal_id) -> bool` | 关闭终端 |

## 错误处理

所有方法在失败时抛出 `ServerManagerError`，包含 `code`、`message`、`server_id` 字段：

```python
from plugins.server_manager.exceptions import ServerManagerError

try:
    result = await service.read_file("srv-a", "/nonexistent")
except ServerManagerError as exc:
    print(f"错误: [{exc.server_id}] {exc.code}: {exc.message}")
```

| code | 含义 |
|------|------|
| 404 | 服务器或资源不存在 |
| 401 | 鉴权失败 |
| 408 | 命令执行超时 |
| 413 | 请求体过大 |
| 429 | 终端数量超限 |
| 500 | 服务器内部错误 |
| 503 | 无法连接到服务器 |
| 504 | 请求超时 |

## 目录结构

```
plugins/server_manager/
├── __init__.py
├── manifest.json
├── plugin.py        # 插件入口
├── config.py        # 配置类
├── service.py       # ServerManagerService
├── models.py        # Pydantic 数据模型
├── client.py        # HTTP 客户端封装
├── exceptions.py    # 异常定义
├── README.md
└── examples/
    └── use_service.py
```

## 依赖

- `httpx`（异步 HTTP 客户端）
- Neo-MoFox 框架（`src.core.components`）

## 使用示例

参见 `examples/use_service.py`，展示了完整的文件操作与终端会话管理流程。
