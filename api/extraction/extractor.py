"""Core extraction engine: corpus -> ranked vocab, phrases, sentence patterns.

Pure-Python and dependency-light. AI enrichment happens as a later step so
this stage is fast and deterministic.
"""
from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass, field

from extraction.nlp import analyze, sentences, STOPWORDS
from extraction import scoring
from extraction.ielts_markers import (
    classify_sentence_section,
    classify_pattern_rule,
    KNOWN_EXPRESSIONS,
)

CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN", "X"}
POS_LABEL = {
    "NOUN": "noun", "VERB": "verb", "ADJ": "adjective", "ADV": "adverb",
    "PROPN": "proper noun", "X": "word",
}


def clean_text(raw: str) -> str:
    text = raw.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _difficulty_for(lemma: str, freq_in_corpus: int) -> str:
    if lemma in scoring.ACADEMIC_HINTS:
        return "B2-C1"
    if len(lemma) >= 9:
        return "C1"
    if len(lemma) >= 7:
        return "B2"
    if len(lemma) >= 5:
        return "B1"
    return "A2"


@dataclass
class ExtractionResult:
    words: list[dict] = field(default_factory=list)
    phrases: list[dict] = field(default_factory=list)
    patterns: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def extract(text: str, *, min_word_freq: int = 2, min_phrase_freq: int = 2,
            max_words: int = 400, max_phrases: int = 200, max_patterns: int = 80) -> ExtractionResult:
    text = clean_text(text)
    tokens = analyze(text)
    sents = sentences(text)

    # ---- Vocabulary -------------------------------------------------------
    lemma_freq: Counter[str] = Counter()
    lemma_pos: dict[str, Counter] = {}
    for lemma, pos, is_alpha, is_stop, lower in tokens:
        if not is_alpha or is_stop or len(lemma) < 3 or lemma in STOPWORDS:
            continue
        if pos not in CONTENT_POS:
            continue
        lemma_freq[lemma] += 1
        lemma_pos.setdefault(lemma, Counter())[pos] += 1

    # collocations: bigrams containing the lemma (for context)
    lowers = [t[4] for t in tokens]
    bigrams = list(zip(lowers, lowers[1:]))
    trigrams = list(zip(lowers, lowers[1:], lowers[2:]))

    words: list[dict] = []
    for lemma, freq in lemma_freq.most_common():
        if freq < min_word_freq:
            continue
        pos_counter = lemma_pos.get(lemma, Counter())
        top_pos = pos_counter.most_common(1)[0][0] if pos_counter else "X"
        collocs = _collocations_for(lemma, bigrams, trigrams)
        difficulty = _difficulty_for(lemma, freq)
        use_cases = _use_cases_for(lemma, sents)
        ps = scoring.score_word(
            frequency=freq, difficulty=difficulty, lemma=lemma,
            n_collocations=len(collocs), ielts_use_cases=use_cases,
        )
        examples = _examples_for(lemma, sents, limit=2)
        words.append({
            "word": lemma,
            "lemma": lemma,
            "frequency": freq,
            "priorityScore": ps,
            "difficulty": difficulty,
            "partOfSpeech": POS_LABEL.get(top_pos, "word"),
            "persianMeaning": "",
            "simpleEnglishMeaning": "",
            "ieltsUseCases": use_cases,
            "collocations": collocs,
            "examples": examples,
            "commonMistakes": [],
            "aiEnriched": False,
        })
        if len(words) >= max_words:
            break

    # ---- Phrases / collocations ------------------------------------------
    phrase_counter: Counter[str] = Counter()
    for a, b in bigrams:
        if _good_phrase_token(a) and _good_phrase_token(b):
            phrase_counter[f"{a} {b}"] += 1
    for a, b, c in trigrams:
        if _good_phrase_token(a) and _good_phrase_token(c) and b not in {".", ","}:
            phrase_counter[f"{a} {b} {c}"] += 1

    total_ngrams = max(1, len(bigrams) + len(trigrams))
    phrases: list[dict] = []
    seen_phrases: set[str] = set()

    # Always include known IELTS expressions present in the text.
    low_text = text.lower()
    for expr in KNOWN_EXPRESSIONS:
        if expr in low_text and expr not in seen_phrases:
            seen_phrases.add(expr)
            phrases.append(_make_phrase(expr, max(2, low_text.count(expr)), 0.95, sents))

    for phrase, freq in phrase_counter.most_common():
        if freq < min_phrase_freq or phrase in seen_phrases:
            continue
        confidence = min(1.0, (freq / total_ngrams) * 800 + 0.25)
        phrases.append(_make_phrase(phrase, freq, confidence, sents))
        seen_phrases.add(phrase)
        if len(phrases) >= max_phrases:
            break

    phrases.sort(key=lambda p: p["priorityScore"], reverse=True)

    # ---- Sentence patterns ------------------------------------------------
    patterns: list[dict] = []
    seen_pat: set[str] = set()
    for s in sents:
        words_in = s.split()
        if not (5 <= len(words_in) <= 32):
            continue
        norm = re.sub(r"\s+", " ", s.strip())
        key = norm.lower()[:80]
        if key in seen_pat:
            continue
        category = classify_pattern_rule(norm)
        usefulness = 70 if category.startswith("Writing") or category.startswith("Speaking") else 50
        ps = scoring.score_pattern(usefulness=usefulness, category=category)
        if ps < 45:
            continue
        seen_pat.add(key)
        patterns.append({
            "sentence": norm,
            "category": category,
            "template": norm,
            "section": classify_sentence_section(norm),
            "priorityScore": ps,
            "usefulness": usefulness,
            "notes": "",
            "aiEnriched": False,
        })
        if len(patterns) >= max_patterns:
            break
    patterns.sort(key=lambda p: p["priorityScore"], reverse=True)

    stats = {
        "tokenCount": len(tokens),
        "sentenceCount": len(sents),
        "uniqueLemmas": len(lemma_freq),
        "wordsExtracted": len(words),
        "phrasesExtracted": len(phrases),
        "patternsExtracted": len(patterns),
    }
    return ExtractionResult(words=words, phrases=phrases, patterns=patterns, stats=stats)


# Helpers --------------------------------------------------------------------
def _good_phrase_token(tok: str) -> bool:
    return tok.isalpha() and len(tok) > 2 and tok not in STOPWORDS


def _collocations_for(lemma: str, bigrams, trigrams, limit: int = 5) -> list[str]:
    c: Counter[str] = Counter()
    for a, b in bigrams:
        if lemma in (a, b) and _good_phrase_token(a) and _good_phrase_token(b):
            c[f"{a} {b}"] += 1
    for a, b, cc in trigrams:
        if lemma in (a, b, cc):
            c[f"{a} {b} {cc}"] += 1
    return [p for p, _ in c.most_common(limit)]


def _use_cases_for(lemma: str, sents: list[str]) -> list[str]:
    found: set[str] = set()
    for s in sents:
        if re.search(rf"\b{re.escape(lemma)}", s.lower()):
            found.add(classify_sentence_section(s))
        if len(found) >= 3:
            break
    return sorted(found) or ["Reading"]


def _examples_for(term: str, sents: list[str], limit: int = 2) -> list[str]:
    out = []
    for s in sents:
        if re.search(rf"\b{re.escape(term)}", s.lower()) and 4 <= len(s.split()) <= 30:
            out.append(s.strip())
        if len(out) >= limit:
            break
    return out


def _make_phrase(phrase: str, freq: int, confidence: float, sents: list[str]) -> dict:
    length = len(phrase.split())
    category = classify_sentence_section(phrase)
    ps = scoring.score_phrase(frequency=freq, confidence=confidence, length=length, category=category)
    return {
        "phrase": phrase,
        "frequency": freq,
        "confidence": round(confidence, 3),
        "length": length,
        "section": category,
        "priorityScore": ps,
        "persianMeaning": "",
        "simpleEnglishMeaning": "",
        "examples": _examples_for(phrase, sents, limit=1),
        "notes": "",
        "aiEnriched": False,
    }
