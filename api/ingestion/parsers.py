"""Extract raw text from many source types: pdf, docx, txt, csv, json, url."""
from __future__ import annotations
import json
import logging
import os

logger = logging.getLogger("ielts.ingestion")


def parse_file(path: str, kind: str | None = None) -> str:
    kind = (kind or os.path.splitext(path)[1].lstrip(".")).lower()
    if kind == "pdf":
        return _parse_pdf(path)
    if kind in ("docx", "doc"):
        return _parse_docx(path)
    if kind == "csv":
        return _parse_csv(path)
    if kind == "json":
        return _parse_json(path)
    # txt and anything else: read as text
    return _parse_txt(path)


def _parse_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _parse_pdf(path: str) -> str:
    import fitz  # PyMuPDF

    parts = []
    with fitz.open(path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def _parse_docx(path: str) -> str:
    import docx

    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            parts.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _parse_csv(path: str) -> str:
    # Prefer pandas if available; otherwise use the stdlib csv module.
    try:
        import pandas as pd

        df = pd.read_csv(path, on_bad_lines="skip")
        return df.to_string(index=False)
    except ImportError:
        import csv

        rows = []
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            for row in csv.reader(f):
                rows.append(" ".join(cell for cell in row if cell))
        return "\n".join(rows)
    except Exception as exc:
        logger.warning("CSV parse failed (%s); falling back to raw read", exc)
        return _parse_txt(path)


def _parse_json(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    return _flatten_json(data)


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
