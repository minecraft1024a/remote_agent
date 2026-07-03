"""finish_task 结果自包含校验：代称检测与重写反馈构建。

用户只能看到 ``finish_task`` 提交的 ``result`` 这一段文本，Agent 的工具
调用过程、命令输出、中间思考对用户完全不可见。因此 ``result`` 必须自
包含：任何要让用户看到的内容都必须原样、完整地物理写进 ``result``。

若 Agent 在 ``result`` 中使用了「上面就是」「如上所示」「见上文」等
指代 ``result`` 之外内容的措辞，那些被指代的内容用户根本看不到，等
于没给用户。本模块负责检测此类违规代称，并构建要求 Agent 重写的反
馈文本，供主循环把违规结果「打回」给 Agent 重新提交。

本模块为纯函数模块，不依赖插件系统或 Neo-MoFox 内部模块，便于独立
单元测试。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


#: 默认代称模式列表。命中其中任一即视为 ``result`` 自包含校验失败。
#: 这些短语都是指代 ``result`` 之外（对用户不可见）内容的措辞。
DEFAULT_REFERENCE_PATTERNS: tuple[str, ...] = (
    "上面就是",
    "上面便是",
    "上方就是",
    "上方便是",
    "如上所示",
    "如上所述",
    "如上文",
    "如前所述",
    "如前所示",
    "刚才的输出",
    "刚才输出",
    "前述",
    "上文",
    "上文中",
    "上面的内容",
    "上面的输出",
    "上面的结果",
    "上面的命令",
    "上面的日志",
    "上面的信息",
    "见上文",
    "见上文所述",
    "见上",
    "见前文",
    "见前",
    "参照上文",
    "参考上文",
    "参考前文",
    "参考上面",
    "就是上面",
    "就是上文",
    "即上文",
    "即上面",
    "即前文",
    "即上面所述",
)


@dataclass(slots=True, frozen=True)
class ReferenceCheckResult:
    """代称检测结果。

    Attributes:
        has_reference: 是否检测到违规代称措辞。
        matched_patterns: 命中的代称模式列表（去重后保持首次出现顺序）。
            ``has_reference`` 为 False 时为空列表。
    """

    has_reference: bool
    matched_patterns: list[str]


def check_result_self_contained(
    result_text: str,
    patterns: Sequence[str] = DEFAULT_REFERENCE_PATTERNS,
) -> ReferenceCheckResult:
    """检测 ``finish_task`` 提交的 ``result`` 是否含违规代称措辞。

    在 ``result_text`` 中逐一匹配 ``patterns`` 中的代称短语。命中任一
    即判定为自包含校验失败。匹配采用子串包含方式，不区分大小写（对
    中文短语无影响，主要兼容可能的英文变体）。

    Args:
        result_text: Agent 通过 ``finish_task`` 提交的最终汇报文本。
        patterns: 待检测的代称模式序列；默认使用
            :data:`DEFAULT_REFERENCE_PATTERNS`。

    Returns:
        ReferenceCheckResult: 检测结果，含是否命中及命中的具体模式。

    Examples:
        >>> r = check_result_self_contained("任务完成！上面就是输出。")
        >>> r.has_reference
        True
        >>> "上面就是" in r.matched_patterns
        True
        >>> check_result_self_contained("fastfetch 输出：\\n...").has_reference
        False
    """
    if not result_text:
        return ReferenceCheckResult(has_reference=False, matched_patterns=[])

    lowered = result_text.lower()
    matched: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        if not pattern:
            continue
        key = pattern.lower()
        if key in seen:
            continue
        if key in lowered:
            matched.append(pattern)
            seen.add(key)

    return ReferenceCheckResult(
        has_reference=bool(matched),
        matched_patterns=matched,
    )


def build_rewrite_feedback(
    matched_patterns: Sequence[str],
    attempt: int,
    max_attempts: int,
) -> str:
    """构建要求 Agent 重写 ``result`` 的反馈文本。

    反馈文本会作为 ``finish_task`` 的「拒绝」结果写回 LLM 上下文，让
    Agent 意识到当前 ``result`` 违规并重新提交自包含的版本。

    Args:
        matched_patterns: 本次命中的代称模式列表。
        attempt: 当前是第几次重写（从 1 开始）。
        max_attempts: 允许的最大重写次数。

    Returns:
        反馈文本，包含违规原因、命中的具体措辞、剩余重写机会及正确做法。

    Raises:
        ValueError: ``attempt`` 小于 1 或 ``max_attempts`` 小于 0。
    """
    if attempt < 1:
        raise ValueError(f"attempt 必须 >= 1，得到 {attempt}")
    if max_attempts < 0:
        raise ValueError(f"max_attempts 必须 >= 0，得到 {max_attempts}")

    patterns_display = "、".join(f"「{p}」" for p in matched_patterns) if matched_patterns else "代称措辞"
    remaining = max(0, max_attempts - attempt)

    lines: list[str] = [
        "❌ 本次 finish_task 的 result 未通过自包含校验，已被打回重写。",
        "",
        "【违规原因】",
        f"result 中出现了指代 result 之外内容的措辞：{patterns_display}。",
        "用户只能看到 finish_task 提交的 result 这一段文本，你的工具调用过程、",
        "命令的 stdout/stderr、你的中间思考对用户完全不可见。因此任何",
        "「上面就是 / 如上所示 / 见上文」式的指代，用户根本看不到被指代的内容，",
        "等于没给用户。",
        "",
        "【正确做法】",
        "把被指代的内容（命令输出、文件内容、查询结果等）原样、完整地物理",
        "粘贴进 result 里，再附上简短说明。不要用任何指代 result 之外的措辞。",
        "",
        "【重写要求】",
        "请重新调用 finish_task，提交一份自包含的 result：",
        "1. 不得出现「上面就是」「如上所示」「见上文」等任何指代措辞；",
        "2. 用户需要看到的所有内容必须原样完整地写在 result 内；",
        "3. 输出很长时可用代码块包裹，但不得删减、截断或只写摘要。",
    ]

    if remaining > 0:
        lines.append("")
        lines.append(f"当前是第 {attempt} 次重写，剩余 {remaining} 次重写机会。")
        lines.append("若再次违规将被强制结束并附警告，请务必一次性修正。")
    else:
        lines.append("")
        lines.append(f"当前是第 {attempt} 次重写，已无剩余重写机会（max_attempts={max_attempts}）。")
        lines.append("这是最后一次机会，若仍违规将被强制结束。")

    return "\n".join(lines)
