# remote_agent

远程服务器代理系统 —— 由独立后端与 Neo-MoFox 插件组成的远程操控方案。

## 组成

| 组件 | 位置 | 说明 |
|------|------|------|
| **remote_agent_server** | [`server/`](server/) | 独立后端服务，部署在被控服务器上，提供文件操作与终端执行的 HTTP API |
| **server_manager** | [`plugins/server_manager/`](plugins/server_manager/) | Neo-MoFox Service 插件，管理多台后端服务器 |
| **server_lister** | [`plugins/server_lister/`](plugins/server_lister/) | Neo-MoFox Tool 插件，查询服务器并协助选择目标 |
| **remote_operator** | [`plugins/remote_operator/`](plugins/remote_operator/) | Neo-MoFox Agent 插件，调用服务器 Service 执行文件与终端操作 |
| **remote_operator_actions** | [`plugins/remote_operator_actions/`](plugins/remote_operator_actions/) | 注册隐藏的 Action 组件，供主程序或其他插件按签名调用，不接入 Agent |

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

也可以使用项目根目录的 Docker Compose 一键构建 Debian 容器、安装远程服务与命令行工具；步骤见 [Docker 部署说明](server/README.md#docker-compose-部署)。

### 2. 安装插件

将 `plugins/server_manager`、`plugins/server_lister`、`plugins/remote_operator` 和 `plugins/remote_operator_actions` 复制到 Neo-MoFox 的插件目录，或分别建立符号链接。`server_lister`、`remote_operator` 和 `remote_operator_actions` 依赖 `server_manager`，需确保该 Service 可用。

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
description = "生产环境，运行正式业务服务"
base_url = "http://192.168.1.100:8421"
token = "your-secret-token"
```

`description` 用来说明服务器的用途、环境、已安装工具或其他区别；`server_manager` 会通过 Service 和服务器列表工具把它传给下游。

如果后端由本仓库的 Docker Compose 启动，Neo-MoFox 直接运行在宿主机时，使用 Compose 的 API Token（`.env` 中的 `RAS_AUTH_TOKEN`）并将 `base_url` 设为 `http://127.0.0.1:8421`。如果 `.env` 修改了 `REMOTE_AGENT_PORT`，这里也要使用对应端口：

```toml
[[servers]]
id = "debian-agent"
name = "Debian 远程环境"
description = "Debian 容器，预装 GitHub CLI、Git、Python 和 npm"
base_url = "http://127.0.0.1:8421"
token = "与 .env 中 RAS_AUTH_TOKEN 相同"
```

如果 Neo-MoFox 也运行在 Docker 中，请将它接入 `remote-agent_default` 网络，并改用 `base_url = "http://remote-agent-server:8421"`。这里的 `token` 是远程服务 API Token；`.env` 中的 `GH_TOKEN_FILE` 是供远程终端里的 `gh` 和 Git 使用的 GitHub 凭据，两者用途不同。

### 4. 使用插件

`server_lister` 提供 `list_servers` Tool，帮助模型确认可用的 `server_id`；每台服务器的 `description` 会一并传给下游，用于区分其用途、环境和工具配置。`remote_operator` 提供远程操作 Agent，Agent 通过 `server_manager` 调用后端。

`remote_operator_actions` 将同类服务器操作注册为主程序 Action。它们的 `go_activate()` 固定返回 `False`，不会暴露给普通聊天模型，也不接入 `remote_operator` Agent；程序和其他插件可按 Action 签名调用。

其他插件也可以通过公开 Service API 直接调用 `server_manager`：

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
    ├── server_manager/        # Service 与服务器配置
    ├── server_lister/         # 查询服务器的 Tool
    ├── remote_operator/       # 远程操作 Agent 与私有工具
    └── remote_operator_actions/ # 注册但对普通聊天隐藏的远程操作 Action
```

## 技术栈

- **后端**：Python >= 3.11, FastAPI, Uvicorn, Pydantic v2, aiofiles
- **插件**：Python >= 3.11, httpx, Neo-MoFox 框架

## 安全

- 后端通过 Bearer Token 鉴权，健康检查除外。
- 终端会话有超时与大小限制，空闲自动回收。
- 建议内网或 VPN/SSH 隧道访问，公网暴露需配合 TLS。
