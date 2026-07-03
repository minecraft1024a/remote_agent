"""RemoteOperatorAgent 组件。

Agent 是远程服务器操控的核心。它将文件操作与终端执行封装为私有
usables，通过 LLM 工具调用循环完成对远程服务器的浏览、编辑、
命令执行等任务，最终以 Bot 人设语气产出汇报文本。

执行流程：
1. 构建包含 Bot 人设的系统提示词 + 任务描述。
2. 创建 LLMRequest，注入私有 usables 作为可用工具。
3. 发送请求，若返回 tool_calls 则逐个执行私有工具并将结果写回上下文。
4. 循环直至 LLM 调用 ``finish_task`` 工具显性提交结果，或达到最大轮数。
5. 返回 ``finish_task`` 提交的汇报文本作为 Agent 执行结果。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Any, cast

from src.app.plugin_system.api import llm_api, stream_api
from src.app.plugin_system.base import BaseAgent
from src.kernel.llm import LLMPayload, ROLE, Text, ToolRegistry
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from src.core.models.message import Message

from .config import RemoteOperatorConfig
from .prompts import build_agent_system_prompt
from .tools import (
    CloseTerminalTool,
    CreateTerminalTool,
    DeleteFileTool,
    EditFileTool,
    ExecCommandTool,
    FinishTaskTool,
    ListFilesTool,
    ListServersTool,
    ListTerminalsTool,
    ReadFileTool,
    WriteFileTool,
)

logger = get_logger("remote_operator")

#: ``finish_task`` 工具名，用于主循环检测显性结束调用
_FINISH_TASK_TOOL_NAME: str = "finish_task"

#: ``finish_task`` 工具参数名，即返回给主大模型的结果字段
_FINISH_TASK_RESULT_ARG: str = "result"

#: Agent 私有工具类列表（不进入全局注册表）
_AGENT_USABLES: list[type] = [
    ListServersTool,
    ListFilesTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    DeleteFileTool,
    CreateTerminalTool,
    ExecCommandTool,
    ListTerminalsTool,
    CloseTerminalTool,
    FinishTaskTool,
]


class RemoteOperatorAgent(BaseAgent):
    """远程服务器操控 Agent。

    通过编排私有工具（文件操作 + 终端执行）完成对远程服务器的
    操控任务。人设提示词从 core.toml 的 [personality] 节读取，
    确保产出回复符合 Bot 角色设定。
    """

    agent_name: str = "remote_operator_agent"
    agent_description: str = (
        "远程服务器操控子代理。可对已配置的远程服务器执行文件浏览、"
        "读写、编辑、删除，以及创建终端、执行命令等操作。"
        "适用于需要在服务器上查看文件、部署项目、排查问题等场景。"
    )

    associated_types: list[str] = ["text"]
    #: 私有工具集，仅对本 Agent 可见
    usables: list[type] = _AGENT_USABLES

    def _cfg(self) -> RemoteOperatorConfig:
        """获取插件配置实例。

        Returns:
            当前生效的配置实例。

        Raises:
            RuntimeError: 配置未正确加载。
        """
        cfg = self.plugin.config
        if not isinstance(cfg, RemoteOperatorConfig):
            raise RuntimeError("remote_operator plugin config 未正确加载")
        return cfg

    async def _get_trigger_message(self) -> "Message | None":
        """根据当前 stream_id 获取触发消息。

        通过 stream_api 从流中取最近一条消息作为工具执行的触发消息。
        run_tool_call 在 trigger_msg 为 None 时会跳过所有工具的实际执行，
        因此必须提供有效的触发消息，工具才能被实例化并执行。

        Returns:
            Message | None: 流中最近的一条消息；流不存在或无消息时返回 None。
        """
        if not self.stream_id:
            return None
        try:
            messages = await stream_api.get_stream_messages(
                stream_id=self.stream_id,
                limit=1,
                offset=0,
            )
        except Exception as exc:
            logger.warning(
                f"remote_operator agent 获取触发消息失败: {exc}",
                exc_info=True,
            )
            return None
        if not messages:
            return None
        return messages[-1]

    @staticmethod
    def _extract_finish_result(calls: Sequence[Any]) -> str | None:
        """从工具调用列表中提取 ``finish_task`` 的 ``result`` 参数。

        遍历本轮 LLM 返回的工具调用，若存在 ``finish_task`` 调用，则
        提取其 ``result`` 参数作为最终汇报文本返回，表示任务应结束。
        主循环据此显性结束，不再执行其他工具或进入下一轮。

        Args:
            calls: 本轮 LLM 响应中的工具调用列表。

        Returns:
            ``finish_task`` 提交的汇报文本；未发现该调用时返回 None。
        """
        for call in calls:
            if getattr(call, "name", "") != _FINISH_TASK_TOOL_NAME:
                continue
            args = call.args if isinstance(call.args, dict) else {}
            result = args.get(_FINISH_TASK_RESULT_ARG, "")
            return str(result) if result else ""
        return None

    async def execute(
        self,
        task_description: Annotated[str, "要执行的远程操控任务的自然语言描述"],
    ) -> tuple[Annotated[bool, "是否成功"], Annotated[str | dict, "返回结果"]]:
        """执行远程操控 Agent 任务。

        构建 LLM 请求并通过工具调用循环完成任务，最终返回符合 Bot
        人设语气的汇报文本。

        Args:
            task_description: 任务描述，如「查看 srv-a 上 /var/log/syslog 的最后 50 行」。

        Returns:
            tuple[bool, str | dict]: (是否成功, 汇报文本或错误信息)。
        """
        cfg = self._cfg()
        logger.info(f"remote_operator agent 执行任务: {task_description}")
        try:
            model_set = llm_api.get_model_set_by_task(cfg.agent.model_task)
        except Exception as exc:
            logger.error(f"获取模型任务 '{cfg.agent.model_task}' 失败: {exc}")
            return False, f"模型配置不可用: {exc}"

        # 构建系统提示词（含人设）
        system_prompt = build_agent_system_prompt(task_description)

        # 创建 LLM 请求
        request = llm_api.create_llm_request(
            model_set=model_set,
            request_name=cfg.agent.request_name,
        )
        request.add_payload(LLMPayload(ROLE.SYSTEM, Text(system_prompt)))
        request.add_payload(LLMPayload(ROLE.USER, Text(task_description)))

        # 注入 Agent 私有工具
        usable_classes = self._get_all_usables()
        tool_registry = ToolRegistry()
        for usable_cls in usable_classes:
            tool_registry.register(usable_cls)

        if not tool_registry.list_all():
            logger.error("没有可用的远程操控工具，请检查 server_manager 是否已加载")
            return False, "没有可用的远程操控工具，请检查 server_manager 是否已加载"

        # ToolRegistry 仅用于执行期按名反查组件类，不会自动让 LLM 看见工具。
        # 必须把工具类作为 ROLE.TOOL payload 注入请求上下文，模型才能感知并调用。
        request.add_payload(LLMPayload(ROLE.TOOL, cast(list[Any], usable_classes)))

        # 工具调用循环
        max_rounds = cfg.agent.max_rounds
        final_text = ""

        try:
            from src.core.utils.llm_tool_call import run_tool_call

            response = await request.send(stream=False)

            for round_idx in range(1, max_rounds + 1):
                # 等待完整响应（消费流并收集文本与 tool_calls）
                text = await response
                logger.info(f"remote_operator agent 第 {round_idx} 轮 LLM 响应文本: {text}")
                final_text = text or ""

                call_list = response.call_list or []
                if not call_list:
                    # LLM 未调用工具，任务结束
                    logger.debug(
                        f"remote_operator agent 第 {round_idx} 轮无工具调用，结束"
                    )
                    break

                # 优先检测显性结束调用 finish_task
                finish_result = self._extract_finish_result(call_list)
                if finish_result is not None:
                    logger.info(
                        f"remote_operator agent 第 {round_idx} 轮收到 "
                        f"finish_task，显性结束任务"
                    )
                    final_text = finish_result
                    break

                logger.debug(
                    f"remote_operator agent 第 {round_idx} 轮收到 "
                    f"{len(call_list)} 个工具调用"
                )

                # 执行工具调用并写回结果
                await run_tool_call(
                    calls=call_list,
                    response=response,
                    usable_map=tool_registry,
                    trigger_msg=await self._get_trigger_message(),
                    plugin=self.plugin,
                    stream_id=self.stream_id,
                    logger_name="remote_operator",
                    display_name="remote_operator_agent",
                )

                # 准备下一轮请求：response 的 payloads 已包含工具结果
                request.payloads = response.payloads
                response = await request.send(stream=True)
            else:
                # 达到最大轮数仍未结束
                final_text = final_text or "操作未能在限定轮数内完成"
                logger.warning(
                    f"remote_operator agent 达到最大轮数 {max_rounds}，强制结束"
                )

        except Exception as exc:
            logger.error(f"remote_operator agent 执行异常: {exc}")
            return False, f"执行过程中出错: {exc}"

        if not final_text.strip():
            return False, "未能获取有效的操作结果汇报"

        return True, final_text
