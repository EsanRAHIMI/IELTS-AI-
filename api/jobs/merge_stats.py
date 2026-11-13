"""Replace one source's contribution instead of adding it on every reprocess.

``sourceFrequency`` stores the count last contributed by each source.
Reprocessing the same source overwrites that bucket. A legacy document that
has only a total is replaced when it belongs to this source alone, and is
left stable (not summed again) once a map exists.
"""
from __future__ import annotations

LEGACY_KEY = "__legacy__"


def apply_source_stats(existing: dict | None, source_id: str, contribution: int) -> dict:
    contribution = max(0, int(contribution))
    if not existing:
        return {
            "frequency": contribution,
            "sourceFrequency": {source_id: contribution},
            "sourceIds": [source_id],
        }

    ids = [str(s) for s in (existing.get("sourceIds") or [])]
    stored = existing.get("sourceFrequency") or {}
    sf = {str(k): int(v) for k, v in stored.items() if str(k) != source_id}
    already = source_id in ids

    if not stored:
        others = [s for s in ids if s != source_id]
        legacy_total = int(existing.get("frequency") or 0)
        if others:
            # Other sources own an unknown share of the old total. Park it once
            # so a later reprocess replaces only this source's bucket.
            sf[LEGACY_KEY] = legacy_total
        elif already:
            sf = {}

    sf[source_id] = contribution
    new_ids: list[str] = []
    for sid in ids + [source_id]:
        if sid not in new_ids:
            new_ids.append(sid)
    frequency = sum(int(v) for v in sf.values())
    return {"frequency": frequency, "sourceFrequency": sf, "sourceIds": new_ids}
