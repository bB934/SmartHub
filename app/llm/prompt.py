"""提示词模板：强制引用标注 + 拒答，避免模型拿训练知识编造答案。"""

SYSTEM_PROMPT = (
    "你是企业知识库助手。只依据【参考资料】回答，句末用 [1][2] 标注出处编号；"
    "资料中没有答案时回答“知识库中没有相关内容”，不要编造。"
)


def build_prompt(question: str, chunks: list[dict]) -> str:
    lines = ["【参考资料】"]
    for i, chunk in enumerate(chunks, 1):
        heading = chunk.get("heading") or "无标题"
        lines.append(f"[{i}] {heading}\n{chunk['text'].strip()}")
    lines.append(f"【问题】{question}")
    return "\n\n".join(lines)
