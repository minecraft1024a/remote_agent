# server_lister

Neo-MoFox 插件，以 **Tool** 形式对外提供「获取已配置远程服务器列表」能力。

## 定位

`server_lister` 只注册一个 Tool 组件 [`ListServersTool`](tool.py:36)，不提供 Service、Action 或 Agent。

它的核心价值是作为远程操控流程的**入口探测工具**：LLM 在调用 [`remote_operator`](../remote_operator/agent.py:68) Agent 之前，应先调用本工具确认可用的 `server_id`，并按以下规则决策：

| 服务器数量 | 用户是否指定 | LLM 应采取的动作 |
|------------|--------------|------------------|
| 1 台 | — | 直接使用该服务器的 `id`，无需询问用户 |
| 多台 | 是 | 使用用户指定的服务器 `id`，无需再次询问 |
| 多台 | 否 | **不要**调用 Agent，先向用户询问要操作哪台服务器，列出可选项供选择 |

通过 [`service_api`](../../Neo-MoFox/src/app/plugin_system/api/service_api.py:76) 获取 [`ServerManagerService`](../server_manager/service.py:34) 实例后调用其 [`list_servers()`](../server_manager/service.py:102) 方法，**不直接导入** `server_manager` 插件源码（遵循插件间禁止源码级依赖的约束）。

## 配置

配置文件路径：`config/plugins/server_lister/config.toml`

```toml
[plugin]
enabled = true
```

本插件仅包含启用开关，不持有额外运行参数。服务器列表由 `server_manager` 插件管理，配置见 [`config/plugins/server_manager/config.toml`](../server_manager/README.md)。

## Tool

| 工具 | 说明 |
|------|------|
| `list_servers()` | 列出所有已配置的远程服务器（不含 token），返回 `{"servers": [...], "count": N}` |

### 返回结构

```json
{
  "servers": [
    {"id": "srv-a", "name": "生产服务器 A", "base_url": "http://192.168.1.100:8421"},
    {"id": "srv-b", "name": "开发服务器 B", "base_url": "http://10.0.0.50:8421"}
  ],
  "count": 2
}
```

## 与 remote_operator 的协作流程

```
用户提出远程操控需求
      │
      ▼
LLM 调用 list_servers 工具
      │
      ▼
判断服务器数量与用户意图
      │
      ├─ 单台 ──────────────────────┐
      │                              │
      ├─ 多台 + 用户已指定 ──────────┤
      │                              ▼
      └─ 多台 + 用户未指定 ──→ 向用户询问目标服务器
                                     │
                                     ▼ 用户明确指定
                             调用 remote_operator Agent
                             传入确定的 server_id
                                     │
                                     ▼
                             Agent 执行远程操控任务
```

## 依赖

- `server_manager` 插件（提供 `ServerManagerService`）
- Neo-MoFox 框架（`src.app.plugin_system`）

`manifest.json` 中已声明组件级依赖：

```json
"dependencies": {
  "plugins": ["server_manager"],
  "components": ["server_manager:service:server_manager"]
}
```

## 目录结构

```
plugins/server_lister/
├── __init__.py
├── manifest.json
├── plugin.py        # 插件入口
├── config.py        # 配置类
├── _base.py         # Service 获取辅助 + Protocol
├── tool.py          # ListServersTool
├── README.md
├── examples/
│   └── use_tool.py
└── tests/
    ├── __init__.py
    ├── test_tool.py
    └── test_plugin.py
```

## 使用示例

参见 [`examples/use_tool.py`](examples/use_tool.py)，展示了如何获取并调用 `list_servers` 工具。
