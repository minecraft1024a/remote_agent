"""任务完成工具。

提供显性的任务结束入口。Agent 在完成所有远程操控步骤后，调用
``finish_task`` 提交要返回给主大模型（用户）的汇报文本，主循环检测
到该调用即提取参数作为最终结果，不再继续工具调用循环。
"""

from __future__ import annotations

from typing import Annotated

from src.app.plugin_system.base import BaseTool


class FinishTaskTool(BaseTool):
    """显性提交任务最终结果。"""

    name: str = "finish_task"
    description: str = (
        "任务完成后调用此工具提交最终汇报文本，调用即表示任务结束。"
        "传入的 result 将作为本次远程操控的结果返回给用户。"
        "完成所有操作步骤后，务必调用此工具结束任务，不要只是输出纯文本。"
    )

    async def execute(
        self,
        result: Annotated[str, "要返回给用户的最终汇报文本,必须自包含：任何要让用户看到的命令输出、文件内容、查询结果，"],
    ) -> tuple[bool, str | dict]:
        """提交任务结果。

        正常情况下 Agent 主循环会在执行前拦截 ``finish_task`` 调用并
        直接提取参数，此方法仅作为兜底入口，确保即使被实际执行也能
        正常返回。

        Args:
            result: 最终汇报文本。

        Returns:
            tuple[bool, str | dict]: (是否成功, 包含结果的结构)。
        """
        return True, {"finished": True, "result": result}
