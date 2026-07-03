"""RemoteOperatorAgent 组件。

Agent 是远程服务器操控的核心。它将文件操作与终端执行封装为私有
usables，通过 LLM 工具调用循环完成对远程服务器的浏览、编辑、
命令执行等任务，最终以 Bot 人设语气产出汇报文本。

执行流程：
1. 构建包含 Bot 人设的系统提示词 + 任务描述。
2. 创建 LLMRequest，注入私有 usables 作为可用工具。
3. 发送请求，若返回 tool_calls 则逐个执行私有工具并将结果写回上下文。
4. 循环直至 LLM 不再调用工具（产出纯文本）或达到最大轮数。
5. 返回最终文本作为 Agent 执行结果。
"""

from __future__ import annotations

from typing import Annotated, Any

from src.app.plugin_system.api import llm_api
from src.app.plugin_system.base import BaseAgent
from src.kernel.llm import LLMPayload, ROLE, Text, ToolRegistry
from src.kernel.logger import get_logger

from .config import RemoteOperatorConfig
from .prompts import build_agent_system_prompt
from .tools import (
    CloseTerminalTool,
    CreateTerminalTool,
    DeleteFileTool,
    EditFileTool,
    ExecCommandTool,
    ListFilesTool,
    ListServersTool,
    ListTerminalsTool,
    ReadFileTool,
    WriteFileTool,
)

logger = get_logger("remote_operator")

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
        tool_registry = ToolRegistry()
        for usable_cls in self._get_all_usables():
            tool_registry.register(usable_cls)

        if not tool_registry.list_all():
            return False, "没有可用的远程操控工具，请检查 server_manager 是否已加载"

        # 工具调用循环
        max_rounds = cfg.agent.max_rounds
        final_text = ""

        try:
            from src.core.utils.llm_tool_call import run_tool_call

            response = await request.send(stream=True)

            for round_idx in range(1, max_rounds + 1):
                # 等待完整响应（消费流并收集文本与 tool_calls）
                text = await response
                final_text = text or ""

                call_list = response.call_list or []
                if not call_list:
                    # LLM 未调用工具，任务结束
                    logger.debug(
                        f"remote_operator agent 第 {round_idx} 轮无工具调用，结束"
                    )
                    break

                logger.info(
                    f"remote_operator agent 第 {round_idx} 轮收到 "
                    f"{len(call_list)} 个工具调用"
                )

                # 执行工具调用并写回结果
                await run_tool_call(
                    calls=call_list,
                    response=response,
                    usable_map=tool_registry,
                    trigger_msg=None,
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
