"""离线评测：计算 Recall@K。用法：python -m app.eval.eval_runner

评测集每条形如：
    {"question": "报销标准是多少", "gold_keywords": ["800", "住宿"], "tenant_id": 1, "space_id": 1, "user_id": 1, "groups": []}
"""

import asyncio
import json
import sys
from pathlib import Path

from app.core.context import RequestContext
from app.db.mysql import SessionLocal
from app.retrieve.reranker import rerank
from app.retrieve.retriever import hybrid_recall


def ctx_of(case: dict) -> RequestContext:
    return RequestContext(
        tenant_id=case.get("tenant_id", 1),
        space_id=case.get("space_id", 1),
        user_id=case.get("user_id", 1),
        groups=case.get("groups", []),
    )


async def recall_at_k(eval_set: list[dict], k: int = 5) -> float:
    hit = 0
    for case in eval_set:
        with SessionLocal() as session:
            cands = await hybrid_recall(case["question"], ctx_of(case), session)
        top = rerank(case["question"], cands, k)
        blob = " ".join(c["text"] for c in top)
        if all(kw in blob for kw in case["gold_keywords"]):
            hit += 1
    return hit / len(eval_set) if eval_set else 0.0


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/eval_set.json")
    if not path.exists():
        print(f"评测集不存在：{path}")
        return
    eval_set = json.loads(path.read_text(encoding="utf-8"))
    score = asyncio.run(recall_at_k(eval_set, 5))
    print(f"Recall@5 = {score:.2%}（共 {len(eval_set)} 条）")


if __name__ == "__main__":
    main()
