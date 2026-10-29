def rrf_fuse(roads: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion：按排名融合，不需要归一化分数"""
    acc, ref = {}, {}
    for road in roads:
        for rank, item in enumerate(road):
            cid = item.get("chunk_id")
            if not cid: continue
            acc[cid] = acc.get(cid, 0.0) + 1.0 / (k + rank + 1)
            ref.setdefault(cid, item)
    order = sorted(acc, key=lambda c: acc[c], reverse=True)
    return [ref[c] | {"rrf": acc[c]} for c in order]