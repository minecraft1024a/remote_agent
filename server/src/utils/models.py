"""请求/响应 Pydantic 模型。

定义后端所有接口的请求体与响应数据模型，与统一响应结构的 data 字段对应。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 文件操作请求模型
# ---------------------------------------------------------------------------


class FileListRequest(BaseModel):
    """列出目录请求。"""

    path: str = Field(..., description="目录路径")


class FileReadRequest(BaseModel):
    """读取文件请求。"""

    path: str = Field(..., description="文件路径")
    encoding: str = Field(default="utf-8", description="文件编码")


class FileWriteRequest(BaseModel):
    """写入文件请求。"""

    path: str = Field(..., description="文件路径")
    content: str = Field(..., description="文件内容")
    encoding: str = Field(default="utf-8", description="文件编码")
    create_dirs: bool = Field(default=True, description="是否自动创建父目录")


class FileDeleteRequest(BaseModel):
    """删除文件/目录请求。"""

    path: str = Field(..., description="路径")
    recursive: bool = Field(default=False, description="是否递归删除目录")


class FileEditItem(BaseModel):
    """单条 diff 编辑（搜索/替换对）。"""

    old_text: str = Field(..., description="需要被替换的原文")
    new_text: str = Field(..., description="替换后的新文本")


class FileEditRequest(BaseModel):
    """Diff 编辑文件请求。"""

    path: str = Field(..., description="文件路径")
    edits: list[FileEditItem] = Field(..., description="有序的搜索/替换对列表")
    encoding: str = Field(default="utf-8", description="文件编码")


# ---------------------------------------------------------------------------
# 文件操作响应数据模型
# ---------------------------------------------------------------------------


class FileEntry(BaseModel):
    """目录条目。"""

    name: str
    type: str = Field(..., description='"file" 或 "dir"')
    size: int | None = None
    modified: str | None = None


class FileListResult(BaseModel):
    """目录列表结果。"""

    path: str
    entries: list[FileEntry] = Field(default_factory=list)


class FileReadResult(BaseModel):
    """文件读取结果。"""

    path: str
    content: str
    size: int
    encoding: str = "utf-8"


class FileWriteResult(BaseModel):
    """文件写入结果。"""

    path: str
    size: int
    written: bool = True


class FileDeleteResult(BaseModel):
    """文件删除结果。"""

    path: str
    deleted: bool = True


class FileEditResult(BaseModel):
    """文件 diff 编辑结果。"""

    path: str
    applied: int = Field(..., description="成功应用的编辑条数")
    total: int = Field(..., description="总编辑条数")
    content: str = Field(..., description="修改后的完整文件内容")
    size: int


# ---------------------------------------------------------------------------
# 终端操作请求/响应模型
# ---------------------------------------------------------------------------


class TerminalCreateRequest(BaseModel):
    """创建终端请求。"""

    shell: str = Field(default="/bin/bash", description="shell 程序路径")
    cwd: str | None = Field(default=None, description="初始工作目录")
    env: dict[str, str] | None = Field(default=None, description="额外环境变量")
    remark: str = Field(default="", description="终端用途备注")


class TerminalExecRequest(BaseModel):
    """执行命令请求。"""

    command: str = Field(..., description="要执行的命令")
    timeout: int = Field(default=30, description="命令超时（秒）")
    use_sudo: bool = Field(
        default=False,
        description="是否以 sudo 执行该命令（需后端配置 sudo.enabled=true 且 sudo.password）",
    )


class TerminalInfo(BaseModel):
    """终端会话信息。"""

    terminal_id: str
    created_at: str
    cwd: str
    alive: bool = True
    remark: str = ""


class TerminalCloseResult(BaseModel):
    """终端关闭结果。"""

    terminal_id: str
    closed: bool = True


class CommandResult(BaseModel):
    """命令执行结果。"""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


# ---------------------------------------------------------------------------
# 健康检查响应
# ---------------------------------------------------------------------------


class HealthResult(BaseModel):
    """健康检查结果。"""

    status: str = "ok"
    version: str = "1.0.0"
