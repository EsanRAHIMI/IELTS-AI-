"""Saved card translations.

A translation is stored on the user's own learning card, under the language
they chose in Settings. A later open of that card reads the saved text and
does not call the translator again.
"""
from __future__ import annotations

LANGUAGES = {
    "fa": "Persian",
    "ar": "Arabic",
    "tr": "Turkish",
    "ur": "Urdu",
    "hi": "Hindi",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ru": "Russian",
    "en": "English",
}
DEFAULT_LANGUAGE = "fa"


def normalize_language(value: str | None) -> str:
    code = (value or "").strip().lower()
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def _lines(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text[:500])
        if len(out) == 6:
            break
    return out


def normalize_translation(raw: dict | None, language: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    data = {
        "language": language,
        "front": str(raw.get("front") or "").strip()[:500],
        "meaning": str(raw.get("meaning") or "").strip()[:2000],
        "examples": _lines(raw.get("examples")),
        "collocations": _lines(raw.get("collocations")),
        "notes": str(raw.get("notes") or "").strip()[:2000],
    }
    pieces = [data["front"], data["meaning"], data["notes"], *data["examples"], *data["collocations"]]
    if not any(piece.strip() for piece in pieces):
        return None
    return data


def stored_translation(card: dict | None, language: str) -> dict | None:
    """Return the saved translation for this language, or None if it must be created."""
    saved = ((card or {}).get("translations") or {}).get(language)
    return normalize_translation(saved if isinstance(saved, dict) else None, language)


def card_source_text(card: dict) -> dict:
    back = card.get("back") or {}
    return {
        "front": str(card.get("front") or ""),
        "meaning": str(back.get("simpleEnglishMeaning") or back.get("persianMeaning") or ""),
        "examples": _lines(back.get("examples")),
        "collocations": _lines(back.get("collocations")),
        "notes": str(back.get("notes") or ""),
    }
