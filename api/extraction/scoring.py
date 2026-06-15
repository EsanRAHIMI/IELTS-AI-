"""Priority scoring (0-100) for vocabulary, phrases and patterns."""
from __future__ import annotations
import math

# Academic Word List signal — a representative subset used as a boost.
ACADEMIC_HINTS = {
    "analyse", "analysis", "approach", "area", "assessment", "assume", "authority", "available",
    "benefit", "concept", "consistent", "constitutional", "context", "contract", "create", "data",
    "definition", "derived", "distribution", "economic", "environment", "established", "estimate",
    "evidence", "export", "factor", "financial", "formula", "function", "identified", "income",
    "indicate", "individual", "interpretation", "involved", "issues", "labour", "legal", "legislation",
    "major", "method", "occur", "percent", "period", "policy", "principle", "procedure", "process",
    "required", "research", "response", "role", "section", "sector", "significant", "similar", "source",
    "specific", "structure", "theory", "variable", "achieve", "acquisition", "administration", "affect",
    "appropriate", "aspect", "assistance", "category", "chapter", "commission", "community", "complex",
    "consequence", "construction", "consumer", "credit", "cultural", "design", "distinction", "element",
    "equation", "evaluation", "feature", "final", "focus", "impact", "injury", "institute", "investment",
    "item", "journal", "maintenance", "normal", "obtained", "participation", "perceived", "positive",
    "potential", "previous", "primary", "purchase", "range", "region", "regulations", "relevant",
    "resident", "resources", "restricted", "security", "sought", "strategies", "survey", "text",
    "traditional", "transfer", "phenomenon", "substantial", "considerable", "facilitate", "mitigate",
    "fluctuate", "deteriorate", "comprehensive", "prominent", "inevitable", "crucial", "vital",
}

DIFFICULTY_VALUE = {"A2": 4, "B1": 8, "B2": 14, "C1": 18, "C2": 16, "": 10}

SECTION_WEIGHT = {
    "Writing Task 2": 10,
    "Writing Task 1": 9,
    "Speaking": 8,
    "Reading": 7,
    "Listening": 6,
}


def _freq_weight(freq: int) -> float:
    # log scaling, capped at 35
    return min(35.0, 12.0 * math.log1p(freq))


def score_word(*, frequency: int, difficulty: str, lemma: str, n_collocations: int,
               ielts_use_cases: list[str], source_count: int = 1) -> int:
    freq_w = _freq_weight(frequency)
    section_w = max((SECTION_WEIGHT.get(s, 0) for s in ielts_use_cases), default=4)
    academic_w = 14 if lemma.lower() in ACADEMIC_HINTS else 0
    colloc_w = min(10, n_collocations * 2.5)
    diff_w = DIFFICULTY_VALUE.get(difficulty.split("-")[0] if difficulty else "", 10)
    usefulness_w = 8 if any(s.startswith("Writing") or s == "Speaking" for s in ielts_use_cases) else 3
    coverage_w = min(6, (source_count - 1) * 2)
    total = freq_w + section_w + academic_w + colloc_w + diff_w + usefulness_w + coverage_w
    return int(max(0, min(100, round(total))))


def score_phrase(*, frequency: int, confidence: float, length: int, category: str = "") -> int:
    freq_w = _freq_weight(frequency)
    conf_w = confidence * 25  # 0..25
    len_w = 8 if length == 3 else 6 if length == 2 else 10
    cat_w = 12 if category.startswith("Writing") or category.startswith("Speaking") else 6
    total = freq_w + conf_w + len_w + cat_w + 10
    return int(max(0, min(100, round(total))))


def score_pattern(*, usefulness: int, category: str, frequency: int = 1) -> int:
    base = usefulness  # 0..100 from AI
    cat_w = 6 if category.startswith("Writing") or category.startswith("Speaking") else 2
    freq_w = min(8, frequency * 2)
    return int(max(0, min(100, round(0.8 * base + cat_w + freq_w))))
