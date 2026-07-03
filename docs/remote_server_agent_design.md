# 远程服务器代理系统设计文档

> 本文档描述一个由两部分组成的服务器远程操控方案：独立后端服务 `remote_agent_server` 与 Neo-MoFox 插件 `server_manager`。插件以 **Service** 形式对外提供能力（不注册 Tool/Action），允许一个插件实例管理多台后端服务器，通过指定 `server_id` 调用对应后端完成文件操作与终端命令执行。

---

## 目录

- [1. 背景与目标](#1-背景与目标)
- [2. 总体架构](#2-总体架构)
- [3. 后端服务 remote_agent_server](#3-后端服务-remote_agent_server)
- [4. 插件 server_manager](#4-插件-server_manager)
- [5. 通讯协议](#5-通讯协议)
- [6. 终端会话生命周期](#6-终端会话生命周期)
- [7. 安全模型](#7-安全模型)
- [8. 错误处理](#8-错误处理)
- [9. 目录结构](#9-目录结构)
- [10. 开发约束](#10-开发约束)
- [11. 待确认事项](#11-待确认事项)

---

## 1. 背景与目标

### 1.1 需求

- 后端服务挂载在被控服务器上，暴露文件浏览与终端执行能力。
- Neo-MoFox 侧插件**不直接注册 Tool/Action**，而是以 **Service** 形式对外提供能力，由其他插件（如 Chatter、Agent）通过 `service_api.get_service()` 获取后调用。
- 一个插件实例可以管理**多台后端服务器**，调用时通过 `server_id` 路由到目标。
- 终端能力采用「先申请 → 获取 terminal_id → 执行命令」模式，每个 terminal_id 上下文独立且保持命令历史。

### 1.2 设计原则

| 原则 | 说明 |
|---|---|
| **职责分离** | 后端服务只做执行，不做业务决策；插件只做路由与聚合，不直接执行 |
| **Service 而非 Tool** | 插件对外仅暴露 Service，不注册 LLM 可见的 Tool，避免被误用为通用能力 |
| **显式生命周期** | 终端会话必须显式创建与销毁，不存在隐式全局终端 |
| **强类型约束** | 后端使用 Pydantic 模型，插件使用类型注解，杜绝手写 dict 传递业务数据 |
| **安全优先** | 后端通过 Token 鉴权，终端会话有超时与大小限制 |

---

## 2. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Neo-MoFox 主程序                      │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │            server_manager 插件 (Service)          │  │
│  │                                                   │  │
│  │  ServerManagerService                             │  │
│  │    ├─ list_files(server_id, path)                 │  │
│  │    ├─ read_file(server_id, path)                  │  │
│  │    ├─ write_file(server_id, path, content)        │  │
│  │    ├─ create_terminal(server_id) → terminal_id   │  │
│  │    ├─ exec_command(server_id, terminal_id, cmd)  │  │
│  │    ├─ close_terminal(server_id, terminal_id)     │  │
│  │    └─ list_servers()                              │  │
│  │         │                                         │  │
│  │    按 server_id 路由到对应后端                     │  │
│  └─────────┼─────────────────────────────────────────┘  │
│            │                                             │
└────────────┼─────────────────────────────────────────────┘
             │ HTTP (Bearer Token)
             │
     ┌───────┴───────┐
     ▼               ▼
┌─────────┐     ┌─────────┐
│ 后端 A   │     │ 后端 B   │
│ Server A │     │ Server B │
│ (srv-a)  │     │ (srv-b)  │
└─────────┘     └─────────┘
```

### 2.1 角色划分

| 组件 | 位置 | 职责 |
|---|---|---|
| `remote_agent_server` | 被控服务器 | 提供文件操作与终端执行的 HTTP API |
| `ServerManagerService` | Neo-MoFox 插件 | 管理多服务器连接、路由请求、会话聚合 |
| `ServerManagerConfig` | Neo-MoFox 插件 | 存储服务器列表（ID/URL/Token）及超时配置 |

---

## 3. 后端服务 remote_agent_server

### 3.1 定位

独立运行的 FastAPI 服务，部署在被控服务器上。它**不依赖** Neo-MoFox 框架，是纯粹的执行端。

### 3.2 技术栈

- Python >= 3.11
- FastAPI + Uvicorn
- Pydantic v2（请求/响应模型）
- aiofiles（异步文件读写）

### 3.3 鉴权

所有业务接口需在请求头携带：

```
Authorization: Bearer <token>
```

Token 在后端启动时通过配置文件或环境变量设定。验证失败返回 `401`。

健康检查接口 `/api/health` 无需鉴权。

### 3.4 API 接口清单

#### 3.4.1 健康检查

```
GET /api/health
```

无需鉴权。返回：

```json
{"status": "ok", "version": "1.0.0"}
```

#### 3.4.2 文件操作

**列出目录**

```
POST /api/files/list
Body: { "path": "/home/user/projects" }
Response: {
  "path": "/home/user/projects",
  "entries": [
    {"name": "main.py", "type": "file", "size": 1024, "modified": "2026-07-03T10:00:00Z"},
    {"name": "src", "type": "dir", "size": null, "modified": "2026-07-02T08:00:00Z"}
  ]
}
```

**读取文件**

```
POST /api/files/read
Body: { "path": "/home/user/projects/main.py", "encoding": "utf-8" }
Response: { "path": "...", "content": "...", "size": 1024, "encoding": "utf-8" }
```

**写入文件**

```
POST /api/files/write
Body: { "path": "/home/user/projects/main.py", "content": "...", "encoding": "utf-8", "create_dirs": true }
Response: { "path": "...", "size": 1024, "written": true }
```

**删除文件/目录**

```
POST /api/files/delete
Body: { "path": "/home/user/projects/old_dir", "recursive": true }
Response: { "path": "...", "deleted": true }
```

**Diff 编辑文件**

允许 AI 以搜索/替换的方式对文件进行精确修改，而非重写整个文件。适用于大文件中的局部修改场景。

```
POST /api/files/edit
Body: {
  "path": "/home/user/projects/main.py",
  "edits": [
    {
      "old_text": "def hello():\n    print('world')",
      "new_text": "def hello():\n    print('hello')"
    }
  ],
  "encoding": "utf-8"
}
Response: {
  "path": "/home/user/projects/main.py",
  "applied": 1,
  "total": 1,
  "content": "... (修改后的完整文件内容)",
  "size": 1024
}
```

行为说明：
- `edits` 是有序的搜索/替换对列表，按顺序依次应用。
- 每个 `old_text` 必须在文件中精确匹配（含缩进和空白），否则该条编辑失败。
- 如果某条编辑的 `old_text` 在文件中出现多次，该条编辑失败（避免歧义）。
- 所有编辑均成功时 `applied == total`，否则返回部分失败信息并在 `message` 中说明哪条失败及原因。
- 返回修改后的完整文件内容，便于 AI 确认修改结果。

#### 3.4.3 终端操作

**创建终端**

```
POST /api/terminals
Body: { "shell": "/bin/bash", "cwd": "/home/user", "env": {"KEY": "value"}, "remark": "编译前端项目" }
Response: {
  "terminal_id": "term_a1b2c3",
  "created_at": "2026-07-03T10:00:00Z",
  "cwd": "/home/user",
  "remark": "编译前端项目"
}
```

`remark` 为可选字段，由调用方（通常是 AI）填写用于标识该终端用途的备注信息。AI 创建终端时应主动填写有意义的备注，便于后续管理多个终端时区分用途。

**执行命令**

```
POST /api/terminals/{terminal_id}/exec
Body: { "command": "ls -la", "timeout": 30 }
Response: {
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "duration_ms": 120
}
```

执行命令在对应 terminal_id 的持久 shell 上下文中运行，环境变量、工作目录变更（`cd`）会保留。

**列出所有终端**

```
GET /api/terminals
Response: {
  "terminals": [
    {
      "terminal_id": "term_a1b2c3",
      "created_at": "2026-07-03T10:00:00Z",
      "cwd": "/home/user",
      "alive": true,
      "remark": "编译前端项目"
    },
    {
      "terminal_id": "term_d4e5f6",
      "created_at": "2026-07-03T10:05:00Z",
      "cwd": "/var/log",
      "alive": true,
      "remark": "查看日志"
    }
  ]
}
```

返回当前服务器上所有活跃的终端会话列表，包含备注信息，便于 AI 管理多个终端时快速定位。

**获取终端信息**

```
GET /api/terminals/{terminal_id}
Response: {
  "terminal_id": "term_a1b2c3",
  "created_at": "...",
  "cwd": "/home/user",
  "alive": true
    "remark": "查看日志"
}
```

**关闭终端**

```
DELETE /api/terminals/{terminal_id}
Response: { "terminal_id": "...", "closed": true }
```

### 3.5 终端实现机制

后端使用 `asyncio.subprocess` 维护每个 terminal_id 对应的持久 shell 进程，采用「哨兵分隔」方案捕获命令输出：

1. 创建终端时，启动 `asyncio.create_subprocess_exec(shell, ...)`，获取 stdin/stdout/stderr 句柄，并生成全局唯一 `terminal_id`（如 `term_` + 8 位随机十六进制）。
2. 执行命令 `cmd` 时，向 stdin 依次写入：
   - 命令本身 `cmd\n`
   - 哨兵回显：`echo "__CMD_DONE_<random>__:$?"\n`
3. 持续读取 stdout/stderr 直到遇到哨兵标记行，截取哨兵之前的输出作为命令输出，解析 `$?` 得到退出码。
4. 同步执行 `pwd` 探测当前工作目录并更新会话状态。
5. 终端空闲超过配置的 `idle_timeout`（默认 1800 秒）后自动回收。
6. 每条命令有独立 `timeout`，超时则终止当前命令但保留会话。

### 3.6 安全限制

| 限制项 | 默认值 | 说明 |
|---|---|---|
| 文件读取大小上限 | 5 MB | 超限返回 `413` |
| 文件写入大小上限 | 10 MB | 超限返回 `413` |
| 命令输出捕获上限 | 1 MB | 超出部分截断，并在 stderr 标注 |
| 命令超时上限 | 120 秒 | 请求体 `timeout` 不得超过此值 |
| 终端空闲超时 | 1800 秒 | 超时自动关闭终端 |
| 最大并发终端数 | 16 | 超出返回 `429` |

### 3.7 配置

后端通过 `config.toml` 或环境变量配置：

```toml
[server]
host = "0.0.0.0"
port = 8421

[auth]
token = "your-secret-token"

[limits]
max_file_read = 5242880        # 5 MB
max_file_write = 10485760      # 10 MB
max_command_output = 1048576   # 1 MB
max_command_timeout = 120
terminal_idle_timeout = 1800
max_terminals = 16
```

### 3.8 统一响应结构

后端所有业务接口遵循统一响应（错误也走此结构，HTTP 状态码辅助区分）：

```json
{
  "code": 200,
  "data": {},
  "message": "success"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | `int` | `200` 成功，其余为错误码 |
| `data` | `Any | null` | 业务数据 |
| `message` | `str` | 状态描述 |

---

## 4. 插件 server_manager

### 4.1 定位

`server_manager` 是 Neo-MoFox 插件，以 **Service** 组件形式对外提供多服务器管理能力。它**不注册** Tool、Action 或其他 LLM 直接可见的组件，仅通过 `get_components()` 返回 `[ServerManagerService]`。

其他插件通过以下方式获取 Service：

```python
from src.app.plugin_system.api import service_api

service = service_api.get_service("server_manager:service:server_manager")
if service is not None:
    result = await service.list_files(server_id="srv-a", path="/home")
```

### 4.2 配置模型

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

配置类继承 `BaseConfig`，使用 `config_section` 与 `Field` 定义。

### 4.3 ServerManagerService 方法签名

所有方法均带有完整类型注解。返回值为 Pydantic 模型或基础类型，**禁止返回手写 dict**。

```python
class ServerManagerService(BaseService):
    """远程服务器管理服务。

    通过指定 server_id 路由到对应后端，提供文件操作与终端会话管理。
    """

    service_name: str = "server_manager"
    service_description: str = "远程服务器文件与终端管理服务"
    version: str = "1.0.0"

    # --- 服务器管理 ---

    def list_servers(self) -> list[ServerInfo]:
        """列出所有已配置的服务器（不含 token）。"""

    def get_server(self, server_id: str) -> ServerInfo | None:
        """获取指定服务器的信息。"""

    # --- 文件操作 ---

    async def list_files(self, server_id: str, path: str) -> FileListResult:
        """列出指定服务器上的目录内容。"""

    async def read_file(
        self, server_id: str, path: str, encoding: str = "utf-8"
    ) -> FileReadResult:
        """读取指定服务器上的文件内容。"""

    async def write_file(
        self, server_id: str, path: str, content: str, encoding: str = "utf-8"
    ) -> FileWriteResult:
        """向指定服务器写入文件。"""

    async def edit_file(
        self,
        server_id: str,
        path: str,
        edits: list[FileEditItem],
        encoding: str = "utf-8",
    ) -> FileEditResult:
        """对指定服务器上的文件进行 diff 编辑（搜索/替换）。

        适用于大文件中的局部修改，避免重写整个文件。
        """

    async def delete_file(
        self, server_id: str, path: str, recursive: bool = False
    ) -> FileDeleteResult:
        """删除指定服务器上的文件或目录。"""

    # --- 终端操作 ---

    async def create_terminal(
        self,
        server_id: str,
        shell: str = "/bin/bash",
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        remark: str = "",
    ) -> TerminalInfo:
        """在指定服务器上创建新的终端会话，返回 terminal_id。

        remark 参数由调用方填写，用于标识终端用途（如"编译前端项目"），
        便于管理多个终端时区分。AI 创建终端时应主动填写有意义的备注。
        """

    async def list_terminals(self, server_id: str) -> list[TerminalInfo]:
        """列出指定服务器上所有活跃的终端会话。"""

    async def exec_command(
        self,
        server_id: str,
        terminal_id: str,
        command: str,
        timeout: int = 30,
    ) -> CommandResult:
        """在指定终端中执行命令，保留会话上下文。"""

    async def get_terminal(self, server_id: str, terminal_id: str) -> TerminalInfo:
        """获取终端会话信息。"""

    async def close_terminal(self, server_id: str, terminal_id: str) -> bool:
        """关闭指定终端会话。"""
```

### 4.4 数据模型（Pydantic）

插件内部定义以下 Pydantic 模型，用于结构化传递数据。这些模型与后端响应的 `data` 字段结构对应：

```python
class ServerInfo(BaseModel):
    """服务器配置信息（对外不含 token）。"""
    id: str
    name: str
    base_url: str

class FileEntry(BaseModel):
    """目录条目。"""
    name: str
    type: str  # "file" | "dir"
    size: int | None
    modified: str | None

class FileListResult(BaseModel):
    """目录列表结果。"""
    path: str
    entries: list[FileEntry]

class FileReadResult(BaseModel):
    """文件读取结果。"""
    path: str
    content: str
    size: int
    encoding: str

class FileWriteResult(BaseModel):
    """文件写入结果。"""
    path: str
    size: int
    written: bool

class FileDeleteResult(BaseModel):
    """文件删除结果。"""
    path: str
    deleted: bool

class FileEditItem(BaseModel):
    """单条 diff 编辑（搜索/替换对）。"""
    old_text: str
    new_text: str

class FileEditResult(BaseModel):
    """文件 diff 编辑结果。"""
    path: str
    applied: int
    total: int
    content: str
    size: int

class TerminalInfo(BaseModel):
    """终端会话信息。"""
    terminal_id: str
    created_at: str
    cwd: str
    alive: bool = True
    remark: str = ""

class CommandResult(BaseModel):
    """命令执行结果。"""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
```

### 4.5 HTTP 客户端

插件使用 `httpx` 的异步客户端（`httpx.AsyncClient`）发送请求：

- 每次 Service 方法调用时创建临时客户端发送请求，调用结束后关闭。
- 不依赖跨调用的连接池复用（因为 `service_api.get_service()` 每次返回新实例）。
- 统一超时由配置 `client.request_timeout` 控制。

### 4.6 路由逻辑

```python
def _resolve_server(self, server_id: str) -> tuple[str, str]:
    """根据 server_id 解析出 (base_url, token)。

    Raises:
        ServerManagerError: server_id 不存在时抛出。
    """
```

每个业务方法第一步调用 `_resolve_server` 获取目标后端地址与凭证，再发起 HTTP 请求。

---

## 5. 通讯协议

### 5.1 请求流

```
插件 ServerManagerService
    │
    ├─ 校验 server_id 是否存在于配置
    ├─ 取出对应 base_url + token
    ├─ 构造 HTTP 请求（Bearer Token + JSON Body）
    ├─ 发送到后端
    │
    └─ 后端 remote_agent_server
         ├─ 鉴权
         ├─ 校验参数（Pydantic）
         ├─ 执行操作
         └─ 返回统一响应
```

### 5.2 响应解析

插件侧收到后端响应后：

1. 检查 HTTP 状态码，非 2xx 抛出 `ServerManagerError`。
2. 解析 JSON Body，检查 `code` 字段。
3. `code == 200` 时将 `data` 映射到对应 Pydantic 模型返回。
4. `code != 200` 时抛出 `ServerManagerError`，携带 `message`。

### 5.3 错误码约定

| code | HTTP | 含义 |
|---|---|---|
| 200 | 200 | 成功 |
| 400 | 400 | 请求参数错误 |
| 401 | 401 | 鉴权失败 |
| 404 | 404 | 资源不存在（文件/终端） |
| 413 | 413 | 请求体过大 |
| 408 | 408 | 命令执行超时 |
| 429 | 429 | 终端数量超限 |
| 500 | 500 | 服务器内部错误 |

---

## 6. 终端会话生命周期

```
create_terminal(server_id)
        │
        ▼
   返回 terminal_id  ──────────────┐
        │                          │
        ▼                          │
exec_command(server_id,            │
             terminal_id, cmd)     │  可多次调用
        │                          │  上下文保留
        ▼                          │
   返回 CommandResult              │
        │                          │
        ▼                          │
   ... (更多命令)  ────────────────┘
        │
        ▼
close_terminal(server_id, terminal_id)
        │
        ▼
   终端会话销毁
```

### 6.1 上下文独立性

- 每个 `terminal_id` 对应一个独立的 shell 进程。
- 环境变量（`export`）、工作目录（`cd`）、shell 变量等在同一个 terminal_id 内保留。
- 不同 `terminal_id` 之间完全隔离，互不影响。
- 不同 `server_id` 的终端自然也完全隔离。

### 6.2 自动回收

- 后端维护每个终端的最后活跃时间。
- 后台任务定期扫描，超过 `terminal_idle_timeout` 的终端自动关闭。
- 插件侧调用已自动回收的 terminal_id 会收到 `404` 错误，调用方应据此重新创建终端。

---

## 7. 安全模型

### 7.1 传输安全

- 后端建议部署在内网或通过 VPN/SSH 隧道访问。
- 如需公网暴露，应配合反向代理（Nginx/Caddy）启用 TLS。
- Token 通过 `Authorization: Bearer` 头传递，不放在 URL 或 Body。

### 7.2 权限边界

- 后端以运行账户的文件系统权限执行操作，不额外做路径白名单（保持灵活）。
- 如需限制可访问目录，可在后端配置 `allowed_roots`（后续扩展项）。
- 终端命令以运行账户身份执行，遵循操作系统权限模型。

### 7.3 审计

- 后端对所有文件操作与命令执行记录日志（路径/命令/退出码/耗时）。
- 日志不记录文件内容与命令输出（避免敏感数据泄露到日志）。

---

## 8. 错误处理

### 8.1 后端

- 参数校验失败：返回 `code=400`，HTTP 400。
- 鉴权失败：返回 `code=401`，HTTP 401。
- 资源不存在：返回 `code=404`，HTTP 404。
- 超限：返回 `code=413` 或 `code=408`，对应 HTTP 状态码。
- 内部异常：返回 `code=500`，HTTP 500，`message` 携带错误摘要（不泄露堆栈）。

### 8.2 插件

- 定义统一异常 `ServerManagerError`，包含 `code`、`message`、`server_id` 字段。
- `server_id` 不存在：抛出 `ServerManagerError(code=404)`。
- HTTP 请求失败（网络层）：抛出 `ServerManagerError(code=503, message="无法连接到服务器")`。
- 后端业务错误：透传后端 `code` 与 `message`。
- 调用方应捕获 `ServerManagerError` 进行处理。

```python
class ServerManagerError(Exception):
    """服务器管理服务异常。"""

    def __init__(self, code: int, message: str, server_id: str = "") -> None:
        self.code = code
        self.message = message
        self.server_id = server_id
        super().__init__(f"[{server_id}] {code}: {message}")
```

---

## 9. 目录结构

### 9.1 后端服务 remote_agent_server

```
remote_agent_server/
├── pyproject.toml
├── README.md
├── config.toml.example          # 配置示例
├── src/
│       ├── __init__.py
│       ├── __main__.py          # 入口：uvicorn 启动
│       ├── app.py               # FastAPI 应用与路由注册
│       ├── utils/
│       ├── ├─ config.py            # 配置加载（Pydantic Settings）
│       ├── ├─ auth.py              # Token 鉴权中间件
│       ├──├─ models.py            # 请求/响应 Pydantic 模型
│       ├──├─  responses.py         # 统一响应封装 BaseResponse
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── files.py         # 文件操作路由（含 list/read/write/edit/delete）
│       │   ├── terminals.py     # 终端操作路由（含 create/list/exec/info/close）
│       │   └── health.py        # 健康检查路由
│       ├── services/
│       │   ├── __init__.py
│       │   ├── file_service.py  # 文件操作业务逻辑
│       │   └── terminal_service.py  # 终端会话管理
│       └── limits.py            # 限制常量与校验
└── test/
    └── ...
```

### 9.2 插件 server_manager

```
plugins/server_manager/
├── __init__.py
├── manifest.json
├── plugin.py                    # 插件入口
├── config.py                    # 配置类
├── service.py                   # ServerManagerService
├── models.py                    # Pydantic 数据模型
├── client.py                    # HTTP 客户端封装
├── exceptions.py                # 异常定义
└── README.md
```

---

## 10. 开发约束

### 10.1 后端

- 所有请求体与响应使用 Pydantic 模型，禁止手写 dict。
- 所有接口返回统一 `BaseResponse` 结构。
- 函数必须有类型注解与文档字符串。
- 文件开头必须注明文件简介。

### 10.2 插件

- 遵循 Neo-MoFox 插件编写规范：
  - 使用 `@register_plugin` 注册插件类。
  - `manifest.name` 与 `plugin_name` 一致。
  - 配置类放入 `configs`，不放入 `get_components()`。
  - Service 组件定义 `service_name`、`service_description`。
  - 插件内部使用相对导入。
  - 禁止直接导入其他插件模块。
- Service 方法必须有完整类型注解与文档字符串。
- 返回值使用 Pydantic 模型，禁止手写 dict。
- 不注册 Tool、Action 等其他 LLM 可见组件。
- `manifest.json` 的 `include` 必须手工维护且与 `get_components()` 一致。

### 10.3 测试

- 后端：使用 FastAPI TestClient 对每个路由进行单元测试，覆盖率 100%。
- 插件：使用 `httpx.MockTransport` 或 `respx` mock 后端响应，测试 Service 各方法的正确性与错误处理。
- 终端会话：测试创建、执行、关闭、超时、上下文保留。

### 10.4 示例

- 后端：提供 `examples/demo_usage.py` 展示如何启动与调用。
- 插件：提供 `examples/use_service.py` 展示其他插件如何获取并使用 ServerManagerService。

---

## 11. 待确认事项

以下设计决策已按默认方案处理，如有调整请在确认时指出：

1. **HTTP 客户端库**：插件侧默认使用 `httpx`（异步）。若需用 `aiohttp` 请说明。
2. **后端配置方式**：默认 `config.toml` + 环境变量覆盖。若需纯环境变量或其他方式请说明。
3. **后端部署位置**：后端服务 `remote_agent_server` 作为独立项目放在 `Neo-MoFox/` 之外（与 `remote_agent_server/` 平级）。若需放在 Neo-MoFox 仓库内请说明。
4. **终端实现**：默认使用「持久 shell + 哨兵分隔」方案。若需 PTY 方案（如 `ptyprocess`）请说明。
5. **文件操作范围**：默认不限制可访问路径（遵循系统权限）。若需 `allowed_roots` 白名单请说明。
6. **HTTP 客户端生命周期**：因 `service_api.get_service()` 每次返回新实例，默认每次请求创建临时客户端。若需在插件实例上缓存客户端请说明。
