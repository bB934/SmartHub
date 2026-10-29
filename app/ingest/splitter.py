import re
import uuid


def split_markdown(md: str, size=500, overlap=100):
    blocks, heading, buf = [], "", ""
    for line in md.splitlines():
        if re.match(r"^#{1,6}\s", line):
            if buf.strip(): blocks.append((heading, buf.strip()))
            heading, buf = line.lstrip("#").strip(), ""
        else:
            buf += line + "\n"
    if buf.strip(): blocks.append((heading, buf.strip()))

    chunks = []
    for h, body in blocks:
        if len(body) <= size:
            chunks.append({"heading": h, "text": body}); continue
        step = size - overlap
        for i in range(0, len(body), step):          # 递归细分，保留 overlap
            chunks.append({"heading": h, "text": body[i:i + size]})
    for c in chunks: c["chunk_id"] = uuid.uuid4().hex
    return chunks