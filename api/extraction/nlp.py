"""spaCy loading with a graceful regex fallback.

If the spaCy model isn't installed the pipeline still works using a lightweight
tokenizer/lemmatizer so the app never hard-fails on a fresh machine.
"""
from __future__ import annotations
import logging
import re

logger = logging.getLogger("ielts.nlp")

_nlp = None
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")

# Minimal POS guess + lemma fallback suffix rules
_SUFFIX_LEMMA = [
    ("ies", "y"), ("sses", "ss"), ("ied", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", ""),
]


def load_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm", disable=["ner"])
        except OSError:
            logger.warning("spaCy model en_core_web_sm not found; using blank pipeline")
            _nlp = spacy.blank("en")
            if "sentencizer" not in _nlp.pipe_names:
                _nlp.add_pipe("sentencizer")
    except Exception as exc:  # spaCy not installed at all
        logger.warning("spaCy unavailable (%s); using regex fallback", exc)
        _nlp = False  # sentinel: fallback mode
    return _nlp


def _fallback_lemma(token: str) -> str:
    t = token.lower()
    for suf, repl in _SUFFIX_LEMMA:
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)] + repl
    return t


def analyze(text: str):
    """Return list of (lemma, pos, is_alpha, is_stop, lower_text)."""
    nlp = load_nlp()
    if nlp is False or nlp is None:
        toks = []
        for m in _TOKEN_RE.finditer(text):
            w = m.group(0)
            toks.append((_fallback_lemma(w), "X", True, w.lower() in STOPWORDS, w.lower()))
        return toks
    doc = nlp(text)
    out = []
    for t in doc:
        if not t.is_alpha:
            continue
        lemma = (t.lemma_ or t.text).lower()
        pos = t.pos_ if t.pos_ else "X"
        out.append((lemma, pos, t.is_alpha, t.is_stop or t.lower_ in STOPWORDS, t.lower_))
    return out


def sentences(text: str) -> list[str]:
    nlp = load_nlp()
    if nlp is False or nlp is None:
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in parts if len(s.strip()) > 3]
    doc = nlp(text)
    try:
        return [s.text.strip() for s in doc.sents if len(s.text.strip()) > 3]
    except ValueError:
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in parts if len(s.strip()) > 3]


# A compact, IELTS-aware stopword list (extends NLTK/spaCy defaults).
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "while", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after", "above",
    "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does",
    "did", "doing", "would", "could", "ought", "i", "me", "my", "myself", "we", "our", "ours",
    "you", "your", "yours", "he", "him", "his", "she", "her", "it", "its", "they", "them",
    "their", "what", "which", "who", "whom", "this", "that", "these", "those", "am", "as",
    "until", "because", "as", "of", "also", "may", "might", "must", "shall", "let", "us", "one",
}
