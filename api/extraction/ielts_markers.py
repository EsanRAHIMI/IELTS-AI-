"""Heuristics for IELTS section classification and known high-value expressions."""
from __future__ import annotations
import re

SECTION_KEYWORDS = {
    "Writing Task 1": [
        "graph", "chart", "table", "diagram", "figure", "percentage", "proportion", "trend",
        "increase", "decrease", "rise", "fall", "fluctuate", "peak", "plateau", "axis", "data shows",
        "illustrates", "depicts", "compared with", "respectively",
    ],
    "Writing Task 2": [
        "argue", "opinion", "agree", "disagree", "advantage", "disadvantage", "however", "moreover",
        "furthermore", "in conclusion", "to what extent", "society", "government", "should", "believe",
        "viewpoint", "arguably", "nevertheless",
    ],
    "Speaking": [
        "i think", "in my opinion", "for me", "personally", "i'd say", "you know", "to be honest",
        "i reckon", "kind of", "sort of",
    ],
    "Listening": [
        "could you", "please", "booking", "registration", "appointment", "telephone", "address",
        "form", "reference number",
    ],
    "Reading": [
        "research", "study", "evidence", "according to", "scientists", "theory", "phenomenon",
        "hypothesis", "findings",
    ],
}

# Curated set of high-value IELTS expressions to always surface if present.
KNOWN_EXPRESSIONS = [
    "a significant increase", "a sharp decline", "a gradual rise", "a steady decrease",
    "it is widely believed that", "this can be attributed to", "from my perspective",
    "the graph illustrates", "compared with", "in contrast", "to some extent",
    "on the other hand", "as a result", "due to the fact that", "in terms of",
    "play a vital role", "a wide range of", "there is no doubt that", "it is often argued that",
    "the vast majority of", "a growing number of", "to a large extent", "in addition to",
    "with regard to", "as far as i am concerned", "the data reveals", "overall the trend",
]


def classify_sentence_section(sentence: str) -> str:
    s = sentence.lower()
    best, best_score = "Reading", 0
    for section, kws in SECTION_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in s)
        if score > best_score:
            best, best_score = section, score
    return best


PATTERN_RULES = [
    (r"\b(increase|decrease|rise|fall|grow|decline|fluctuate|peak)\b", "Writing Task 1 trend description"),
    (r"\bcompared (with|to)\b|\bwhereas\b|\bwhile\b.*\bthan\b", "Writing Task 1 comparison"),
    (r"\bin my opinion\b|\bi (strongly )?believe\b|\bi (agree|disagree)\b", "Writing Task 2 opinion"),
    (r"\b(because of|due to|as a result|consequently|leads to|results in)\b", "Writing Task 2 cause/effect"),
    (r"\b(advantage|disadvantage|benefit|drawback)\b", "Writing Task 2 advantage/disadvantage"),
    (r"\b(you know|to be honest|i reckon|kind of|sort of)\b", "Speaking fluency phrases"),
    (r"\b(when i was|i remember|in my experience|i once)\b", "Speaking personal experience phrases"),
    (r"\b(could you|please|i'd like to book|reference number)\b", "Listening functional phrases"),
]


def classify_pattern_rule(sentence: str) -> str:
    s = sentence.lower()
    for rx, label in PATTERN_RULES:
        if re.search(rx, s):
            return label
    return "Reading academic structures"
