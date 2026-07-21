"""文件操作工具。

封装 ServerManagerService 的文件操作能力，提供列目录、读文件、
写文件、diff 编辑、删除等工具供 Agent 调用。

本插件不直接导入 server_manager 插件源码，而是在本地定义结构兼容的
FileEditItem 模型，避免跨插件源码级依赖。
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel

from src.app.plugin_system.base import BaseTool

from ._base import get_server_manager_service


class _LocalFileEditItem(BaseModel):
    """本地 diff 编辑项模型。

    与 server_manager 的 FileEditItem 结构一致（old_text + new_text），
    用于满足 Service.edit_file 内部调用 e.model_dump() 的需求，
    避免直接导入其他插件源码。
    """

    old_text: str
    new_text: str


class ListFilesTool(BaseTool):
    """列出指定服务器上的目录内容。"""

    name: str = "list_files"
    description: str = (
        "列出指定服务器上某目录的内容，返回文件与子目录列表。"
        "操作前先用 list_servers 确认 server_id。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID（通过 list_servers 获取）"],
        path: Annotated[str, "要列出的目录绝对路径"],
    ) -> tuple[bool, str | dict]:
        """执行列目录逻辑。

        Args:
            server_id: 目标服务器 ID。
            path: 目录路径。

        Returns:
            tuple[bool, str | dict]: (是否成功, 目录内容或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            result = await service.list_files(server_id, path)
        except Exception as exc:
            return False, f"列目录失败: {exc}"

        return True, result.model_dump()


class ReadFileTool(BaseTool):
    """读取指定服务器上的文件内容。"""

    name: str = "read_file"
    description: str = (
        "读取指定服务器上某文件的内容。适用于查看配置、源码、日志等。"
        "大文件会被后端截断，关注关键部分即可。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
        path: Annotated[str, "文件绝对路径"],
        encoding: Annotated[str, "文件编码，默认 utf-8"] = "utf-8",
    ) -> tuple[bool, str | dict]:
        """执行读文件逻辑。

        Args:
            server_id: 目标服务器 ID。
            path: 文件路径。
            encoding: 文件编码。

        Returns:
            tuple[bool, str | dict]: (是否成功, 文件内容或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            result = await service.read_file(server_id, path, encoding)
        except Exception as exc:
            return False, f"读取文件失败: {exc}"

        return True, result.model_dump()


class WriteFileTool(BaseTool):
    """向指定服务器写入文件。"""

    name: str = "write_file"
    description: str = (
        "向指定服务器写入文件，若父目录不存在会自动创建。"
        "用于创建脚本、配置文件或覆盖更新内容。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
        path: Annotated[str, "文件绝对路径"],
        content: Annotated[str, "要写入的完整文件内容"],
        encoding: Annotated[str, "文件编码，默认 utf-8"] = "utf-8",
    ) -> tuple[bool, str | dict]:
        """执行写文件逻辑。

        Args:
            server_id: 目标服务器 ID。
            path: 文件路径。
            content: 文件内容。
            encoding: 文件编码。

        Returns:
            tuple[bool, str | dict]: (是否成功, 写入结果或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            result = await service.write_file(
                server_id, path, content, encoding
            )
        except Exception as exc:
            return False, f"写入文件失败: {exc}"

        return True, result.model_dump()


class EditFileTool(BaseTool):
    """对指定服务器上的文件进行 diff 编辑。"""

    name: str = "edit_file"
    description: str = (
        "以搜索/替换方式对服务器上的文件进行精确局部修改，避免重写整个文件。"
        "edits 为有序列表，每项包含 old_text（需精确匹配，含缩进）与 new_text。"
        "若 old_text 在文件中出现多次或未匹配，该条编辑会失败。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
        path: Annotated[str, "文件绝对路径"],
        edits: Annotated[
            list[dict[str, str]],
            "编辑列表，每项形如 {\"old_text\": \"...\", \"new_text\": \"...\"}",
        ],
        encoding: Annotated[str, "文件编码，默认 utf-8"] = "utf-8",
    ) -> tuple[bool, str | dict]:
        """执行 diff 编辑逻辑。

        Args:
            server_id: 目标服务器 ID。
            path: 文件路径。
            edits: 搜索/替换对列表。
            encoding: 文件编码。

        Returns:
            tuple[bool, str | dict]: (是否成功, 编辑结果或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        # 将 dict 列表转换为 Service 期望的 FileEditItem 模型
        # 使用本地定义的结构兼容模型，避免跨插件源码导入
        try:
            edit_items = [_LocalFileEditItem.model_validate(e) for e in edits]
        except Exception as exc:
            return False, f"编辑项格式无效: {exc}"

        try:
            result = await service.edit_file(
                server_id, path, edit_items, encoding
            )
        except Exception as exc:
            return False, f"编辑文件失败: {exc}"

        return True, result.model_dump()


class DeleteFileTool(BaseTool):
    """删除指定服务器上的文件或目录。"""

    name: str = "delete_file"
    description: str = (
        "删除指定服务器上的文件或目录。recursive=true 时递归删除目录。"
        "破坏性操作，执行前务必确认路径正确。"
    )

    async def execute(
        self,
        server_id: Annotated[str, "目标服务器 ID"],
        path: Annotated[str, "要删除的路径"],
        recursive: Annotated[bool, "是否递归删除目录（删除目录时需为 true）"] = False,
    ) -> tuple[bool, str | dict]:
        """执行删除逻辑。

        Args:
            server_id: 目标服务器 ID。
            path: 路径。
            recursive: 是否递归删除。

        Returns:
            tuple[bool, str | dict]: (是否成功, 删除结果或错误信息)。
        """
        try:
            service = get_server_manager_service()
        except RuntimeError as exc:
            return False, str(exc)

        try:
            result = await service.delete_file(server_id, path, recursive)
        except Exception as exc:
            return False, f"删除失败: {exc}"

        return True, result.model_dump()
