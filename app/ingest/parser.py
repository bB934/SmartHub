"""文档解析：把常见格式统一成纯文本，交给 splitter 切片。"""

from pathlib import Path
from typing import cast

import pymupdf


def parse_pdf(path: str) -> list[tuple[int, str]]:
    """返回 [(page_no, text)]，扫描件会得到空串，必须在这里拦掉"""
    with pymupdf.open(path) as doc:
        # get_text 的桩签名是 str | list | dict，指定 "text" 时运行时必定返回 str
        out = [
            (i + 1, cast(str, doc[i].get_text("text")).strip())
            for i in range(doc.page_count)
        ]
    if not any(t for _, t in out):
        raise ValueError("扫描件无文本层，需先 OCR（MinerU / marker）")
    return out


def parse_file(path: str) -> str:
    """按扩展名解析成纯文本。不支持的类型直接报错，而不是静默入库空文档。"""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return "\n\n".join(f"# 第 {page} 页\n{text}" for page, text in parse_pdf(path))
    if ext == ".docx":
        import docx

        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    if ext in {".md", ".markdown", ".txt"}:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"暂不支持的格式：{ext}（支持 pdf/md/txt/docx）")
