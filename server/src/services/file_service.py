"""文件操作业务逻辑。

提供目录列举、文件读写、删除与 diff 编辑能力。
所有操作遵循配置中的大小限制，以运行账户的文件系统权限执行。
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from ..limits import Limits
from ..utils.errors import InternalError, NotFoundError
from ..utils.models import (
    FileDeleteResult,
    FileEditItem,
    FileEditResult,
    FileEntry,
    FileListResult,
    FileReadResult,
    FileWriteResult,
)


def _format_modified(ts: float) -> str:
    """将时间戳格式化为 ISO 8601 UTC 字符串。

    Args:
        ts: 文件修改时间戳。

    Returns:
        ISO 8601 格式的时间字符串。
    """
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FileService:
    """文件操作服务。

    封装文件系统操作，统一应用大小限制与错误处理。
    """

    def __init__(self, limits: Limits) -> None:
        """初始化文件服务。

        Args:
            limits: 限制校验器。
        """
        self._limits = limits

    async def list_files(self, path: str) -> FileListResult:
        """列出目录内容。

        Args:
            path: 目录路径。

        Returns:
            目录列表结果。

        Raises:
            NotFoundError: 目录不存在。
            InternalError: 路径不是目录或读取失败。
        """
        target = Path(path).expanduser()
        if not target.exists():
            raise NotFoundError(f"路径不存在: {path}")
        if not target.is_dir():
            raise InternalError(f"路径不是目录: {path}")

        entries: list[FileEntry] = []
        try:
            for item in sorted(target.iterdir(), key=lambda p: p.name):
                stat = item.stat()
                is_dir = item.is_dir()
                entries.append(
                    FileEntry(
                        name=item.name,
                        type="dir" if is_dir else "file",
                        size=None if is_dir else stat.st_size,
                        modified=_format_modified(stat.st_mtime),
                    )
                )
        except PermissionError as exc:
            raise InternalError(f"无权限读取目录: {path}") from exc
        except OSError as exc:
            raise InternalError(f"读取目录失败: {exc}") from exc

        return FileListResult(path=str(target), entries=entries)

    async def read_file(self, path: str, encoding: str = "utf-8") -> FileReadResult:
        """读取文件内容。

        Args:
            path: 文件路径。
            encoding: 文件编码。

        Returns:
            文件读取结果。

        Raises:
            NotFoundError: 文件不存在。
            LimitExceededError: 文件超过读取大小上限。
            InternalError: 路径不是文件或读取失败。
        """
        target = Path(path).expanduser()
        if not target.exists():
            raise NotFoundError(f"文件不存在: {path}")
        if not target.is_file():
            raise InternalError(f"路径不是文件: {path}")

        size = target.stat().st_size
        self._limits.check_file_read_size(size)

        try:
            async with aiofiles.open(target, "r", encoding=encoding) as f:
                content = await f.read()
        except UnicodeDecodeError as exc:
            raise InternalError(f"文件编码解码失败（encoding={encoding}）: {exc}") from exc
        except PermissionError as exc:
            raise InternalError(f"无权限读取文件: {path}") from exc
        except OSError as exc:
            raise InternalError(f"读取文件失败: {exc}") from exc

        return FileReadResult(
            path=str(target),
            content=content,
            size=size,
            encoding=encoding,
        )

    async def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True,
    ) -> FileWriteResult:
        """写入文件内容。

        Args:
            path: 文件路径。
            content: 文件内容。
            encoding: 文件编码。
            create_dirs: 是否自动创建父目录。

        Returns:
            文件写入结果。

        Raises:
            LimitExceededError: 内容超过写入大小上限。
            InternalError: 写入失败。
        """
        target = Path(path).expanduser()
        content_bytes = content.encode(encoding)
        self._limits.check_file_write_size(len(content_bytes))

        if create_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiofiles.open(target, "w", encoding=encoding) as f:
                await f.write(content)
        except PermissionError as exc:
            raise InternalError(f"无权限写入文件: {path}") from exc
        except OSError as exc:
            raise InternalError(f"写入文件失败: {exc}") from exc

        return FileWriteResult(
            path=str(target),
            size=len(content_bytes),
            written=True,
        )

    async def delete_file(self, path: str, recursive: bool = False) -> FileDeleteResult:
        """删除文件或目录。

        Args:
            path: 路径。
            recursive: 是否递归删除目录。

        Returns:
            文件删除结果。

        Raises:
            NotFoundError: 路径不存在。
            InternalError: 删除失败或目录非空但未指定 recursive。
        """
        target = Path(path).expanduser()
        if not target.exists():
            raise NotFoundError(f"路径不存在: {path}")

        try:
            if target.is_dir():
                if recursive:
                    shutil.rmtree(target)
                else:
                    target.rmdir()
            else:
                target.unlink()
        except PermissionError as exc:
            raise InternalError(f"无权限删除: {path}") from exc
        except OSError as exc:
            raise InternalError(f"删除失败: {exc}") from exc

        return FileDeleteResult(path=str(target), deleted=True)

    async def edit_file(
        self,
        path: str,
        edits: list[FileEditItem],
        encoding: str = "utf-8",
    ) -> FileEditResult:
        """对文件进行 diff 编辑（搜索/替换）。

        按 edits 顺序依次应用。每条 old_text 必须精确匹配且唯一，
        否则该条编辑失败，已应用的编辑保留。

        Args:
            path: 文件路径。
            edits: 有序的搜索/替换对列表。
            encoding: 文件编码。

        Returns:
            文件编辑结果，包含修改后的完整内容。

        Raises:
            NotFoundError: 文件不存在。
            LimitExceededError: 文件超过读取大小上限。
            InternalError: 读取或写入失败。
        """
        target = Path(path).expanduser()
        if not target.exists():
            raise NotFoundError(f"文件不存在: {path}")
        if not target.is_file():
            raise InternalError(f"路径不是文件: {path}")

        size = target.stat().st_size
        self._limits.check_file_read_size(size)

        try:
            async with aiofiles.open(target, "r", encoding=encoding) as f:
                content = await f.read()
        except UnicodeDecodeError as exc:
            raise InternalError(f"文件编码解码失败（encoding={encoding}）: {exc}") from exc
        except PermissionError as exc:
            raise InternalError(f"无权限读取文件: {path}") from exc
        except OSError as exc:
            raise InternalError(f"读取文件失败: {exc}") from exc

        applied = 0
        total = len(edits)
        for idx, edit in enumerate(edits):
            if edit.old_text not in content:
                raise InternalError(
                    f"第 {idx + 1} 条编辑失败：old_text 未在文件中找到"
                )
            if content.count(edit.old_text) > 1:
                raise InternalError(
                    f"第 {idx + 1} 条编辑失败：old_text 在文件中出现多次，存在歧义"
                )
            content = content.replace(edit.old_text, edit.new_text, 1)
            applied += 1

        content_bytes = content.encode(encoding)
        self._limits.check_file_write_size(len(content_bytes))

        try:
            async with aiofiles.open(target, "w", encoding=encoding) as f:
                await f.write(content)
        except PermissionError as exc:
            raise InternalError(f"无权限写入文件: {path}") from exc
        except OSError as exc:
            raise InternalError(f"写入文件失败: {exc}") from exc

        return FileEditResult(
            path=str(target),
            applied=applied,
            total=total,
            content=content,
            size=len(content_bytes),
        )
