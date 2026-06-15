"""Extract raw text from many source types: pdf, docx, txt, csv, json, url.

Parsing works directly from in-memory bytes (no local files are written).
"""
from __future__ import annotations
import io
import json
import logging
import csv as _csv

logger = logging.getLogger("ielts.ingestion")


def parse_bytes(data: bytes, kind: str | None = None) -> str:
    """Extract text from raw file bytes. Preferred entry point (no disk I/O)."""
    kind = (kind or "txt").lower().lstrip(".")
    if kind == "pdf":
        return _parse_pdf_bytes(data)
    if kind in ("docx", "doc"):
        return _parse_docx_bytes(data)
    if kind == "csv":
        return _parse_csv_bytes(data)
    if kind == "json":
        return _parse_json_bytes(data)
    return data.decode("utf-8", errors="ignore")


def _parse_pdf_bytes(data: bytes) -> str:
    import fitz  # PyMuPDF

    parts = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def _parse_docx_bytes(data: bytes) -> str:
    import docx

    d = docx.Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            parts.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _parse_csv_bytes(data: bytes) -> str:
    text = data.decode("utf-8", errors="ignore")
    try:
        import pandas as pd

        df = pd.read_csv(io.StringIO(text), on_bad_lines="skip")
        return df.to_string(index=False)
    except ImportError:
        rows = []
        for row in _csv.reader(io.StringIO(text)):
            rows.append(" ".join(cell for cell in row if cell))
        return "\n".join(rows)
    except Exception as exc:
        logger.warning("CSV parse failed (%s); falling back to raw text", exc)
        return text


def _parse_json_bytes(data: bytes) -> str:
    try:
        obj = json.loads(data.decode("utf-8", errors="ignore"))
    except Exception:
        return data.decode("utf-8", errors="ignore")
    return _flatten_json(obj)


def _flatten_json(data) -> str:
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            out.append(node)
        elif node is not None:
            out.append(str(node))

    walk(data)
    return "\n".join(out)


async def parse_url(url: str) -> tuple[str, str]:
    """Fetch a URL and return (title, text)."""
    import httpx
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "Mozilla/5.0 (IELTS-AI-Mastery; +local)"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text
    # Use lxml if installed (faster), else the stdlib html.parser.
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else url)
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return title, text
