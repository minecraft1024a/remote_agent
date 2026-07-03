# remote_agent

远程服务器代理系统 —— 由两部分组成的服务器远程操控方案。

## 组成

| 组件 | 位置 | 说明 |
|------|------|------|
| **remote_agent_server** | [`server/`](server/) | 独立后端服务，部署在被控服务器上，提供文件操作与终端执行的 HTTP API |
| **server_manager** | [`plugins/server_manager/`](plugins/server_manager/) | Neo-MoFox 插件，以 Service 形式管理多台后端服务器 |

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    Neo-MoFox 主程序                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │            server_manager 插件 (Service)          │  │
│  │  ServerManagerService                              │  │
│  │    ├─ list_files(server_id, path)                 │  │
│  │    ├─ read_file / write_file / edit_file          │  │
│  │    ├─ create_terminal(server_id) → terminal_id   │  │
│  │    ├─ exec_command(server_id, terminal_id, cmd)  │  │
│  │    └─ list_servers()                              │  │
│  │         按 server_id 路由到对应后端                 │  │
│  └─────────┬─────────────────────────────────────────┘  │
└────────────┼─────────────────────────────────────────────┘
             │ HTTP (Bearer Token)
     ┌───────┴───────┐
     ▼               ▼
┌─────────┐     ┌─────────┐
│ Server A │     │ Server B │
│ (srv-a)  │     │ (srv-b)  │
└─────────┘     └─────────┘
```

## 快速开始

### 1. 部署后端服务

在被控服务器上：

```bash
cd remote_agent/server
uv sync
cp config.toml.example config.toml
# 编辑 config.toml，设置 token
python -m src
```

详见 [server/README.md](server/README.md)。

### 2. 安装插件

将 `plugins/server_manager` 复制到 Neo-MoFox 的插件目录，或建立符号链接。

### 3. 配置插件

编辑 `config/plugins/server_manager/config.toml`：

```toml
[plugin]
enabled = true

[client]
request_timeout = 30

[[servers]]
id = "srv-a"
name = "生产服务器"
base_url = "http://192.168.1.100:8421"
token = "your-secret-token"
```

### 4. 使用 Service

```python
from src.app.plugin_system.api import service_api

service = service_api.get_service("server_manager:service:server_manager")
if service is not None:
    # 列出目录
    result = await service.list_files("srv-a", "/home")
    # 创建终端并执行命令
    term = await service.create_terminal("srv-a", remark="编译项目")
    out = await service.exec_command("srv-a", term.terminal_id, "ls -la")
```

## 设计文档

完整设计文档见 [docs/remote_server_agent_design.md](docs/remote_server_agent_design.md)。

## 目录结构

```
remote_agent/
├── readme.md
├── docs/
│   └── remote_server_agent_design.md
├── server/                    # 后端服务 remote_agent_server
│   ├── pyproject.toml
│   ├── config.toml.example
│   ├── README.md
│   ├── examples/
│   └── src/
│       ├── __main__.py
│       ├── app.py
│       ├── limits.py
│       ├── utils/
│       ├── routers/
│       └── services/
└── plugins/
    └── server_manager/        # Neo-MoFox 插件
        ├── manifest.json
        ├── plugin.py
        ├── config.py
        ├── service.py
        ├── models.py
        ├── client.py
        ├── exceptions.py
        └── examples/
```

## 技术栈

- **后端**：Python >= 3.11, FastAPI, Uvicorn, Pydantic v2, aiofiles
- **插件**：Python >= 3.11, httpx, Neo-MoFox 框架

## 安全

- 后端通过 Bearer Token 鉴权，健康检查除外。
- 终端会话有超时与大小限制，空闲自动回收。
- 建议内网或 VPN/SSH 隧道访问，公网暴露需配合 TLS。
