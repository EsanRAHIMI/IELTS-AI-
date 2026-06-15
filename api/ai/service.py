"""High-level AI service: provider selection + IELTS-specific helpers.

Every method degrades gracefully: if no provider is configured (or a call
fails), it returns a sensible fallback so the rest of the pipeline keeps
working without AI enrichment.
"""
from __future__ import annotations
import json
import logging

from config import settings
from ai.base import AIProvider
from ai.providers import OpenAIProvider, AnthropicProvider, OllamaProvider

logger = logging.getLogger("ielts.ai")

_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str | None = None) -> AIProvider | None:
    name = (name or settings.ai_provider or "openai").lower()
    cls = _PROVIDERS.get(name)
    if not cls:
        return None
    provider = cls()
    return provider if provider.configured else None


def ai_available() -> bool:
    return get_provider() is not None


def _parse_json(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw.strip("`")
        raw = raw.replace("json\n", "", 1).strip()
    try:
        return json.loads(raw)
    except Exception:
        # try to locate the first {...}
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
    return None


SYSTEM = (
    "You are an expert IELTS coach and lexicographer. You explain English vocabulary, "
    "collocations and sentence patterns precisely for an Iranian (Persian-speaking) "
    "learner aiming for IELTS band 7.5+. Be accurate and concise."
)


async def explain_word(word: str, pos: str = "", context: str = "") -> dict:
    """Return enrichment dict for a word. Falls back to empty fields if no AI."""
    fallback = {
        "persianMeaning": "",
        "simpleEnglishMeaning": "",
        "difficulty": "B2",
        "ieltsUseCases": [],
        "collocations": [],
        "examples": [],
        "commonMistakes": [],
        "notes": "",
    }
    provider = get_provider()
    if not provider:
        return fallback
    prompt = (
        f"Explain the English word '{word}' (part of speech: {pos or 'unknown'}) for IELTS.\n"
        f"{('Context sentence: ' + context) if context else ''}\n"
        "Return JSON with keys: persianMeaning (Persian/Farsi translation), "
        "simpleEnglishMeaning (one short sentence), difficulty (one of A2,B1,B2,C1,C2), "
        "ieltsUseCases (array from: Writing Task 1, Writing Task 2, Reading, Listening, Speaking), "
        "collocations (array of 3-5 natural collocations), examples (array of 2 IELTS-style sentences), "
        "commonMistakes (array of 1-2 short tips), notes (one short study note)."
    )
    try:
        raw = await provider.complete(prompt, system=SYSTEM, json_mode=True)
        data = _parse_json(raw) or {}
        return {**fallback, **{k: data[k] for k in fallback if k in data}}
    except Exception as exc:
        logger.warning("explain_word failed: %s", exc)
        return fallback


async def explain_phrase(phrase: str, context: str = "") -> dict:
    fallback = {"persianMeaning": "", "simpleEnglishMeaning": "", "examples": [], "notes": "", "register": "academic"}
    provider = get_provider()
    if not provider:
        return fallback
    prompt = (
        f"Explain the IELTS phrase/collocation '{phrase}'.\n"
        f"{('Context: ' + context) if context else ''}\n"
        "Return JSON with keys: persianMeaning, simpleEnglishMeaning, "
        "examples (array of 2 sentences), register (academic|neutral|spoken), notes (when to use it)."
    )
    try:
        raw = await provider.complete(prompt, system=SYSTEM, json_mode=True)
        data = _parse_json(raw) or {}
        return {**fallback, **{k: data[k] for k in fallback if k in data}}
    except Exception as exc:
        logger.warning("explain_phrase failed: %s", exc)
        return fallback


async def classify_pattern(sentence: str) -> dict:
    fallback = {"category": "Reading academic structures", "template": sentence, "notes": "", "usefulness": 60}
    provider = get_provider()
    if not provider:
        return fallback
    prompt = (
        f"Classify this English sentence into an IELTS sentence-pattern category and turn it into a reusable template.\n"
        f"Sentence: {sentence}\n"
        "Categories: Writing Task 1 trend description, Writing Task 1 comparison, Writing Task 2 opinion, "
        "Writing Task 2 cause/effect, Writing Task 2 advantage/disadvantage, Speaking fluency phrases, "
        "Speaking personal experience phrases, Reading academic structures, Listening functional phrases.\n"
        "Return JSON: category (one of the above), template (sentence with [placeholders]), "
        "notes (how to reuse), usefulness (0-100 integer for Writing/Speaking)."
    )
    try:
        raw = await provider.complete(prompt, system=SYSTEM, json_mode=True)
        data = _parse_json(raw) or {}
        return {**fallback, **{k: data[k] for k in fallback if k in data}}
    except Exception as exc:
        logger.warning("classify_pattern failed: %s", exc)
        return fallback


async def generate_study_note(term: str, kind: str = "word") -> str:
    provider = get_provider()
    if not provider:
        return ""
    try:
        return await provider.complete(
            f"Write a single concise IELTS study tip (max 2 sentences) for the {kind} '{term}'.",
            system=SYSTEM,
        )
    except Exception:
        return ""
