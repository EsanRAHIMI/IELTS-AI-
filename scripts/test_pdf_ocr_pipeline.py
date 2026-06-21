"""Standalone verification for the OCR PDF ingestion pipeline.

Builds a synthetic PDF: page 1 has embedded text, page 2 is an image-only
(scanned) page rendered from text so it must go through OCR. Then exercises the
real parser, chunker, extractor and quality heuristics from the api package.

Run from the api/ dir (so imports resolve):
    cd api && python ../scripts/test_pdf_ocr_pipeline.py
"""
import os
import sys

# allow running from repo root or scripts/: ensure api/ is importable
HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(os.path.dirname(HERE), "api")
if API not in sys.path:
    sys.path.insert(0, API)

import types  # noqa: E402

import fitz  # noqa: E402

from ingestion.parsers import parse_pdf_document, ocr_available  # noqa: E402
from extraction.extractor import clean_text, extract  # noqa: E402


def _stub_heavy_modules():
    """Stub DB/storage/AI modules so we can import the pure helpers in
    jobs.processor without a Mongo driver / boto3 / AI SDKs present."""
    for name in ("database", "storage", "storage.s3_service", "ai", "ai.service"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    # storage / ai need to look like packages with attributes
    sys.modules["storage"].s3_service = sys.modules["storage.s3_service"]
    sys.modules["ai"].service = sys.modules["ai.service"]


LOREM_TEXT = (
    "The graph illustrates a significant increase in urban population after 2010. "
    "It is widely believed that this can be attributed to economic development. "
    "From my perspective, the trend demonstrates substantial growth compared with "
    "previous decades. In contrast, rural figures declined to some extent. "
) * 6

SCANNED_TEXT = (
    "Academic vocabulary is essential for the IELTS examination. Candidates must "
    "demonstrate a wide range of collocations and sophisticated sentence patterns. "
    "Consequently, the writing task requires careful planning and coherent argument. "
) * 6


def build_test_pdf() -> bytes:
    doc = fitz.open()
    # Page 1: embedded selectable text
    p1 = doc.new_page()
    p1.insert_textbox(fitz.Rect(40, 40, 550, 800), LOREM_TEXT, fontsize=11)
    # Page 2: render text to an image, then place ONLY the image (no text layer)
    tmp = fitz.open()
    tp = tmp.new_page()
    tp.insert_textbox(fitz.Rect(40, 40, 550, 800), SCANNED_TEXT, fontsize=16)
    pix = tp.get_pixmap(matrix=fitz.Matrix(3, 3))
    img_bytes = pix.tobytes("png")
    p2 = doc.new_page()
    p2.insert_image(fitz.Rect(0, 0, p2.rect.width, p2.rect.height), stream=img_bytes)
    out = doc.tobytes()
    doc.close(); tmp.close()
    return out


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""))
    return cond


def main():
    print("OCR available:", ocr_available())
    pdf = build_test_pdf()
    print(f"Built synthetic PDF: {len(pdf)} bytes\n")

    print("== Parser ==")
    doc = parse_pdf_document(pdf, ocr_enabled=True, dpi=200, min_chars=80, language="eng")
    print(f"  pageCount={doc.pageCount} extracted={doc.extractedPages} "
          f"ocr={doc.ocrPages} empty={doc.emptyPages} method={doc.extractionMethod}")
    for p in doc.pages:
        print(f"    page {p.pageNumber}: method={p.method} chars={p.charCount}")

    ok = True
    ok &= check("2 pages detected", doc.pageCount == 2, str(doc.pageCount))
    ok &= check("page 1 used embedded text", doc.pages[0].method == "pdf_text")
    ok &= check("page 2 used OCR", doc.pages[1].method == "ocr", doc.pages[1].method)
    ok &= check("extractionMethod is mixed", doc.extractionMethod == "mixed", doc.extractionMethod)
    ok &= check("OCR text is non-trivial", len(doc.pages[1].text.strip()) > 80,
                f"{len(doc.pages[1].text.strip())} chars")

    print("\n== Chunker + Extractor (full cleaned text) ==")
    cleaned = clean_text(doc.text)
    # mirror processor chunking
    _stub_heavy_modules()
    from jobs.processor import _build_chunks  # noqa: E402
    chunks = _build_chunks(cleaned)
    result = extract(cleaned)
    print(f"  rawChars={len(doc.text)} cleanedChars={len(cleaned)} chunks={len(chunks)}")
    print(f"  words={len(result.words)} phrases={len(result.phrases)} patterns={len(result.patterns)}")
    ok &= check("cleaned text non-empty", len(cleaned) > 200)
    ok &= check("at least 1 chunk", len(chunks) >= 1)
    ok &= check("words extracted", len(result.words) > 5)
    ok &= check("phrases extracted", len(result.phrases) > 3)

    print("\n== Quality heuristics ==")
    from jobs.processor import _quality_status  # noqa: E402
    # simulate the bad old result: 400 pages, tiny text
    status, warns = _quality_status(400, 20_318, 2, 0, None)
    print(f"  big-pdf-low-text -> {status}; warnings={len(warns)}")
    ok &= check("low-text 400p flagged warning", status == "warning")
    status2, _ = _quality_status(2, len(cleaned), len(chunks), len(result.patterns), doc)
    print(f"  this-doc -> {status2}")
    ok &= check("healthy small doc not failed", status2 in ("ok", "warning"))

    print("\n== Graceful degradation (OCR disabled) ==")
    doc2 = parse_pdf_document(pdf, ocr_enabled=False, min_chars=80)
    print(f"  method={doc2.extractionMethod} empty={doc2.emptyPages} warnings={doc2.warnings}")
    ok &= check("scanned page marked empty when OCR off", doc2.pages[1].method == "empty")
    ok &= check("warning present on page 2", bool(doc2.pages[1].warning))

    print("\nRESULT:", "ALL PASS" if ok else "SOME FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
