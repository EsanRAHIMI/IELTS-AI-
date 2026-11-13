"""Turn saved user settings into a daily-plan shape."""
from __future__ import annotations

import re

SKILL_TOKENS = {
    "Writing": "writing",
    "Speaking": "speaking",
    "Reading": "reading",
    "Listening": "listening",
}


def plan_sizes(daily_target: int) -> dict[str, int]:
    target = min(200, max(5, int(daily_target or 30)))
    return {
        "words": target,
        "phrases": max(5, round(target / 2)),
        "patterns": max(3, round(target / 3)),
    }


def focus_skill_tokens(modules: list[str] | None) -> list[str]:
    out: list[str] = []
    for module in modules or []:
        token = SKILL_TOKENS.get(str(module))
        if token and token not in out:
            out.append(token)
    return out


def focus_query(tokens: list[str]) -> dict:
    """Match IELTS section fields. Tokens come from a fixed allowlist."""
    if not tokens:
        return {}
    clauses = []
    for token in tokens:
        pattern = re.escape(token)
        clauses.append({"ieltsUseCases": {"$regex": pattern, "$options": "i"}})
        clauses.append({"section": {"$regex": pattern, "$options": "i"}})
        clauses.append({"category": {"$regex": pattern, "$options": "i"}})
    return {"$or": clauses}
