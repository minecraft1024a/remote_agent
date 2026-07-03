"""Agent 系统提示词构建器。

从 Core 配置的 personality 节读取 Bot 人设，拼接出远程操控子代理的
系统提示词。人设内容来自 config/core.toml 的 [personality] 节，
确保 Agent 在执行远程操作时仍以 Bot 的角色身份与语气产出最终回复。
"""

from __future__ import annotations

from src.core.config import get_core_config


def build_agent_system_prompt(task_description: str) -> str:
    """构建 Agent 子代理的系统提示词。

    提示词由两部分组成：
    1. Bot 人设：从 core.toml 的 [personality] 节读取，包含昵称、
       核心性格、人格侧面、身份、表达风格等，确保 Agent 产出的
       最终回复符合 Bot 角色设定。
    2. 远程操控任务指令：说明 Agent 可用的工具范围、操作约束与
       输出要求。

    Args:
        task_description: 本次远程操控任务的自然语言描述。

    Returns:
        拼接后的完整系统提示词。
    """
    task_block = _build_task_block(task_description)
    return f"\n\n{task_block}"


def _build_task_block(task_description: str) -> str:
    """构建远程操控任务指令块。

    Args:
        task_description: 任务描述文本。

    Returns:
        任务指令文本。
    """
    return (
        "【当前任务】\n"
        f"{task_description}\n\n"
        "【你的角色】\n"
        "你是远程服务器操控子代理。你可以调用以下类别的私有工具来完成任务：\n"
        "- 服务器管理：列出可用服务器、查询服务器信息\n"
        "- 文件操作：列目录、读文件、写文件、diff 编辑文件、删除文件\n"
        "- 终端操作：创建终端、执行命令、列出终端、关闭终端\n"
        "- 任务结束：finish_task —— 提交最终结果并结束任务\n\n"
        "【操作约束】\n"
        "1. 操作前先用 list_servers 确认目标 server_id 是否存在。\n"
        "2. 终端会话有上下文保留能力，相关联的命令应复用同一 terminal_id。\n"
        "3. 创建终端时务必填写有意义的 remark，便于管理多个终端。\n"
        "4. 命令执行后根据 exit_code 与 stderr 判断是否成功，失败时分析原因并重试或调整。\n"
        "5. 完成所有操作步骤后，必须调用 finish_task 工具提交最终汇报文本，"
        "传入的 result 即为返回给用户的最终结果。这是结束任务的唯一显性方式。\n"
        "6. 涉及删除、写入等破坏性操作前，先确认路径正确，避免误删。\n"
        "7. 工具调用结果中的 stdout/stderr 可能较长，重点关注末尾的退出码与错误行。\n\n"
        "【输出要求】\n"
        "1. 用户只能看到你调用 finish_task 时传入的 result 这一段文本。"
        "你的工具调用过程、命令的 stdout/stderr、你的中间思考，对用户完全不可见。"
        "因此 result 必须自包含：任何要让用户看到的命令输出、文件内容、查询结果，"
        "都必须原样、完整地物理写进 result 里，而不是说一句「上面就是」「如前所示」了事。\n"
        "2. 严禁使用「上面就是」「如上所示」「如前所述」「刚才的输出」「见上文」"
        "等任何指代 result 之外内容的措辞——那些内容用户根本看不到。"
        "错误示例：『任务完成！上面就是 fastfetch 的完整输出。』"
        "正确做法：把 fastfetch 的完整输出原样粘贴进 result，再附上简短说明。\n"
        "3. 如果用户要求「完整命令」「原样输出」「给我命令」等，你必须在 result 中"
        "把对应的命令文本原样完整写出（含完整路径、参数、管道等），不做改写、不加分页、不折叠。\n"
        "4. 若一条命令的输出很长，仍应完整保留，可用代码块包裹以便阅读，但不得删减、截断或只写摘要。\n"
        "5. 一句话总结：result 不是对已发生操作的点评，而是用户能看到的全部。"
        "缺了任何一段用户需要的内容，就等于没给用户。"
    )
