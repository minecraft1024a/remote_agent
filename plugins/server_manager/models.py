"""插件 Pydantic 数据模型。

与后端响应的 data 字段结构对应，用于结构化传递数据。
所有 Service 方法返回值使用这些模型，禁止手写 dict。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ServerInfo(BaseModel):
    """服务器配置信息（对外不含 token）。"""

    id: str
    name: str
    base_url: str


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
