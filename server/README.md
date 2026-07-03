# remote_agent_server

远程服务器代理后端服务。部署在被控服务器上，提供文件操作与终端执行的 HTTP API。

## 定位

独立运行的 FastAPI 服务，**不依赖** Neo-MoFox 框架。它只负责执行，不参与业务决策。

## 技术栈

- Python >= 3.11
- FastAPI + Uvicorn
- Pydantic v2（请求/响应模型）
- aiofiles（异步文件读写）

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置

复制配置示例并修改：

```bash
cp config.toml.example config.toml
```

编辑 `config.toml`，至少修改 `[auth]` 下的 `token`：

```toml
[server]
host = "0.0.0.0"
port = 8421

[auth]
token = "your-secret-token"

[limits]
max_file_read = 5242880
max_file_write = 10485760
max_command_output = 1048576
max_command_timeout = 120
terminal_idle_timeout = 1800
max_terminals = 16

[sudo]
# 启用后，exec_command 请求 use_sudo=true 时以 sudo 执行命令
enabled = false
password = ""
```

也可通过环境变量覆盖（`RAS_` 前缀，双下划线分隔层级）：

```bash
export RAS_AUTH__token="my-token"
export RAS_SERVER__port=9000
```

### 3. 启动服务

两种方式均可：

```bash
python -m src
# 或
python run.py
```

### 4. 验证

```bash
curl http://127.0.0.1:8421/api/health
# {"code":200,"data":{"status":"ok","version":"1.0.0"},"message":"success"}
```

## API 概览

所有业务接口需在请求头携带 `Authorization: Bearer <token>`，健康检查除外。

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查（无需鉴权） |

### 文件操作

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/files/list` | 列出目录 |
| POST | `/api/files/read` | 读取文件 |
| POST | `/api/files/write` | 写入文件 |
| POST | `/api/files/edit` | diff 编辑文件（搜索/替换） |
| POST | `/api/files/delete` | 删除文件/目录 |

### 终端操作

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/terminals` | 创建终端 |
| GET | `/api/terminals` | 列出所有终端 |
| GET | `/api/terminals/{id}` | 获取终端信息 |
| POST | `/api/terminals/{id}/exec` | 执行命令 |
| DELETE | `/api/terminals/{id}` | 关闭终端 |

## 统一响应结构

```json
{
  "code": 200,
  "data": {},
  "message": "success"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `int` | `200` 成功，其余为错误码 |
| `data` | `Any \| null` | 业务数据 |
| `message` | `str` | 状态描述 |

## 安全限制

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| 文件读取大小上限 | 5 MB | 超限返回 413 |
| 文件写入大小上限 | 10 MB | 超限返回 413 |
| 命令输出捕获上限 | 1 MB | 超出部分截断 |
| 命令超时上限 | 120 秒 | 请求体 `timeout` 不得超过 |
| 终端空闲超时 | 1800 秒 | 超时自动关闭 |
| 最大并发终端数 | 16 | 超出返回 429 |

## sudo 执行

终端命令支持以 sudo 执行。在请求 `POST /api/terminals/{id}/exec` 的 Body 中传入 `use_sudo: true` 即可。

需在后端 `[sudo]` 配置段中启用并设置密码：

```toml
[sudo]
enabled = true
password = "your-sudo-password"
```

实现机制：后端通过 `sudo -S -p '' bash -c '<command>'` 执行命令，密码从 stdin 传入，不输出提示符。密码仅在内存中传递，不写入日志。当 `sudo.enabled=false` 或密码为空时，`use_sudo=true` 的请求会返回 500 错误。

## 终端实现

后端使用 `asyncio.subprocess` 维护每个 `terminal_id` 对应的持久 shell 进程，采用「哨兵分隔」方案捕获命令输出：

1. 创建终端时启动 shell 子进程，生成唯一 `terminal_id`。
2. 执行命令时向 stdin 写入命令 + 哨兵回显。
3. 持续读取 stdout/stderr 直到遇到哨兵标记行，解析退出码。
4. 空闲超时自动回收，每条命令有独立超时。

## 目录结构

```
remote_agent_server/
├── pyproject.toml
├── config.toml.example
├── README.md
├── run.py                    # 启动脚本（python run.py）
├── examples/
│   └── demo_usage.py
├── src/
│   ├── __init__.py
│   ├── __main__.py          # 入口：uvicorn 启动
│   ├── app.py               # FastAPI 应用与路由注册
│   ├── limits.py            # 限制常量与校验
│   ├── utils/
│   │   ├── config.py        # 配置加载
│   │   ├── auth.py          # Token 鉴权中间件
│   │   ├── models.py        # 请求/响应 Pydantic 模型
│   │   ├── responses.py     # 统一响应封装
│   │   └── errors.py        # 异常定义
│   ├── routers/
│   │   ├── health.py        # 健康检查路由
│   │   ├── files.py         # 文件操作路由
│   │   └── terminals.py     # 终端操作路由
│   └── services/
│       ├── file_service.py  # 文件操作业务逻辑
│       └── terminal_service.py  # 终端会话管理
└── test/
```

## 部署建议

- 内网或 VPN/SSH 隧道访问，避免公网直接暴露。
- 如需公网暴露，配合反向代理（Nginx/Caddy）启用 TLS。
- Token 通过 `Authorization: Bearer` 头传递，不放在 URL 或 Body。
- 以专用低权限账户运行服务。
