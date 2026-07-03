"""后端服务使用示例。

展示如何启动 remote_agent_server 并通过 HTTP 客户端调用文件与终端接口。

运行方式：
    1. 复制 config.toml.example 为 config.toml 并修改 token
    2. python -m src  启动服务
    3. 在另一个终端运行本示例：python examples/demo_usage.py
"""

from __future__ import annotations

import httpx

BASE_URL = "http://127.0.0.1:8421"
TOKEN = "your-secret-token"


def main() -> None:
    """演示如何调用后端 API。"""
    headers = {"Authorization": f"Bearer {TOKEN}"}

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        # 1. 健康检查（无需鉴权）
        resp = client.get("/api/health")
        print(f"[健康检查] {resp.json()}")

        # 2. 列出目录
        resp = client.post("/api/files/list", json={"path": "/tmp"})
        print(f"[列出目录] {resp.json()}")

        # 3. 写入文件
        resp = client.post(
            "/api/files/write",
            json={"path": "/tmp/remote_agent_demo.txt", "content": "hello world\n", "create_dirs": True},
        )
        print(f"[写入文件] {resp.json()}")

        # 4. 读取文件
        resp = client.post(
            "/api/files/read",
            json={"path": "/tmp/remote_agent_demo.txt"},
        )
        print(f"[读取文件] {resp.json()}")

        # 5. diff 编辑文件
        resp = client.post(
            "/api/files/edit",
            json={
                "path": "/tmp/remote_agent_demo.txt",
                "edits": [{"old_text": "hello", "new_text": "你好"}],
            },
        )
        print(f"[编辑文件] {resp.json()}")

        # 6. 创建终端
        resp = client.post("/api/terminals", json={"remark": "示例终端"})
        terminal = resp.json()["data"]
        terminal_id = terminal["terminal_id"]
        print(f"[创建终端] terminal_id={terminal_id}")

        # 7. 执行命令
        resp = client.post(
            f"/api/terminals/{terminal_id}/exec",
            json={"command": "echo $HOME", "timeout": 10},
        )
        print(f"[执行命令] {resp.json()}")

        # 7.5 以 sudo 执行命令（需后端配置 [sudo] enabled=true）
        resp = client.post(
            f"/api/terminals/{terminal_id}/exec",
            json={"command": "whoami", "timeout": 10, "use_sudo": True},
        )
        print(f"[sudo 执行命令] {resp.json()}")

        # 8. 列出终端
        resp = client.get("/api/terminals")
        print(f"[列出终端] {resp.json()}")

        # 9. 关闭终端
        resp = client.delete(f"/api/terminals/{terminal_id}")
        print(f"[关闭终端] {resp.json()}")

        # 10. 删除文件
        resp = client.post(
            "/api/files/delete",
            json={"path": "/tmp/remote_agent_demo.txt"},
        )
        print(f"[删除文件] {resp.json()}")


if __name__ == "__main__":
    main()
