"""Seed a high-quality starter IELTS dataset into MongoDB.

Inserts 200+ academic words, 100+ phrases/collocations and 50+ sentence
patterns (with Persian meanings, English explanations and examples) for a
target user, then auto-builds flashcards for the highest-priority items.

Usage:
    cd api && source .venv/bin/activate
    cd ..
    python scripts/seed_ielts_data.py --email you@example.com [--password secret] [--reset]

If the user does not exist it is created (default password: changeme123).
Run this AFTER configuring api/.env with MONGODB_URI.
"""
from __future__ import annotations
import argparse
import asyncio
import os
import sys

# Make the api/ package importable and load api/.env.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT, "api")
sys.path.insert(0, API_DIR)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(API_DIR, ".env"))

DATA_DIR = os.path.join(ROOT, "scripts", "data")
SECTION_MAP = {
    "W1": "Writing Task 1", "W2": "Writing Task 2",
    "R": "Reading", "L": "Listening", "S": "Speaking",
}


def _read_rows(path: str, n_fields: int) -> list[list[str]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < n_fields:
                parts += [""] * (n_fields - len(parts))
            rows.append([p.strip() for p in parts[:n_fields]])
    return rows


def _expand_sections(codes: str) -> list[str]:
    out = []
    for c in codes.split(","):
        c = c.strip()
        if c in SECTION_MAP:
            out.append(SECTION_MAP[c])
        elif c:
            out.append(c)
    return out or ["Reading"]


def load_words() -> list[dict]:
    from extraction import scoring
    from utils.serialization import now
    rows = _read_rows(os.path.join(DATA_DIR, "words.txt"), 8)
    docs = []
    for word, pos, persian, english, difficulty, sections, collocs, example in rows:
        use_cases = _expand_sections(sections)
        collocations = [c.strip() for c in collocs.split(",") if c.strip()]
        ps = scoring.score_word(
            frequency=8, difficulty=difficulty, lemma=word.lower(),
            n_collocations=len(collocations), ielts_use_cases=use_cases, source_count=1,
        )
        docs.append({
            "word": word, "lemma": word.lower(), "frequency": 8, "priorityScore": ps,
            "difficulty": difficulty, "partOfSpeech": pos, "persianMeaning": persian,
            "simpleEnglishMeaning": english, "ieltsUseCases": use_cases,
            "collocations": collocations, "examples": [example] if example else [],
            "commonMistakes": [], "notes": "", "aiEnriched": True, "seed": True,
            "status": "new", "important": False, "hidden": False,
            "createdAt": now(), "updatedAt": now(),
        })
    return docs


def load_phrases() -> list[dict]:
    from extraction import scoring
    from utils.serialization import now
    rows = _read_rows(os.path.join(DATA_DIR, "phrases.txt"), 5)
    docs = []
    for phrase, persian, english, section, example in rows:
        length = len(phrase.split())
        ps = scoring.score_phrase(frequency=6, confidence=0.95, length=length, category=section)
        docs.append({
            "phrase": phrase, "frequency": 6, "confidence": 0.95, "length": length,
            "section": section, "priorityScore": ps, "persianMeaning": persian,
            "simpleEnglishMeaning": english, "examples": [example] if example else [],
            "notes": "", "aiEnriched": True, "seed": True,
            "status": "new", "important": False, "hidden": False,
            "createdAt": now(), "updatedAt": now(),
        })
    return docs


def load_patterns() -> list[dict]:
    from extraction import scoring
    from utils.serialization import now
    rows = _read_rows(os.path.join(DATA_DIR, "patterns.txt"), 5)
    docs = []
    for template, category, section, notes, example in rows:
        usefulness = 80 if category.startswith(("Writing", "Speaking")) else 60
        ps = scoring.score_pattern(usefulness=usefulness, category=category)
        docs.append({
            "sentence": example or template, "template": template, "category": category,
            "section": section, "priorityScore": ps, "usefulness": usefulness,
            "notes": notes, "aiEnriched": True, "seed": True,
            "status": "new", "important": False, "hidden": False,
            "createdAt": now(), "updatedAt": now(),
        })
    return docs


async def get_or_create_user(email: str, password: str) -> str:
    import database as db
    from auth.security import hash_password
    from utils.serialization import now
    email = email.lower()
    user = await db.users().find_one({"email": email})
    if user:
        return str(user["_id"])
    res = await db.users().insert_one({
        "email": email, "name": email.split("@")[0],
        "passwordHash": hash_password(password),
        "settings": {"aiProvider": "openai", "dailyTarget": 30, "targetBand": 7.5,
                     "examDate": None, "focusModules": ["Academic", "Writing", "Speaking"]},
        "createdAt": now(), "updatedAt": now(),
    })
    print(f"  Created user {email} (password: {password})")
    return str(res.inserted_id)


async def seed(email: str, password: str, reset: bool) -> None:
    import database as db
    from utils.serialization import now, oid

    if not await db.ping():
        print("ERROR: cannot connect to MongoDB. Check MONGODB_URI in api/.env")
        sys.exit(1)
    await db.init_indexes()
    uid = await get_or_create_user(email, password)

    if reset:
        for c in (db.vocab(), db.phrases(), db.patterns()):
            await c.delete_many({"userId": uid, "seed": True})
        await db.cards().delete_many({"userId": uid})
        print("  Reset existing seed data")

    words = load_words()
    phrases = load_phrases()
    patterns = load_patterns()

    async def upsert(col, docs, key):
        added = 0
        for d in docs:
            if await col.find_one({"userId": uid, key: d[key]}):
                continue
            await col.insert_one({**d, "userId": uid, "sourceIds": []})
            added += 1
        return added

    nw = await upsert(db.vocab(), words, "lemma")
    np = await upsert(db.phrases(), phrases, "phrase")
    na = await upsert(db.patterns(), patterns, "sentence")
    print(f"  Inserted {nw} words, {np} phrases, {na} patterns")

    # Auto-build flashcards for the top items so Study Mode works immediately.
    async def build_cards(col, ctype, front_key, limit):
        made = 0
        cur = col.find({"userId": uid}).sort("priorityScore", -1).limit(limit)
        async for item in cur:
            if await db.cards().find_one({"userId": uid, "type": ctype, "refId": str(item["_id"])}):
                continue
            if ctype == "word":
                front = item["word"]
                back = {"persianMeaning": item.get("persianMeaning", ""),
                        "simpleEnglishMeaning": item.get("simpleEnglishMeaning", ""),
                        "examples": item.get("examples", []),
                        "collocations": item.get("collocations", []),
                        "notes": item.get("notes", "")}
            elif ctype == "phrase":
                front = item["phrase"]
                back = {"persianMeaning": item.get("persianMeaning", ""),
                        "simpleEnglishMeaning": item.get("simpleEnglishMeaning", ""),
                        "examples": item.get("examples", []), "collocations": [],
                        "notes": item.get("notes", "")}
            else:
                front = item.get("template", item.get("sentence", ""))
                back = {"persianMeaning": "", "simpleEnglishMeaning": item.get("category", ""),
                        "examples": [item.get("sentence", "")], "collocations": [],
                        "notes": item.get("notes", "")}
            await db.cards().insert_one({
                "userId": uid, "type": ctype, "refId": str(item["_id"]), "front": front,
                "back": back, "status": "new", "easeFactor": 2.5, "interval": 0,
                "repetitions": 0, "nextReviewAt": now(), "lastReviewedAt": None,
                "createdAt": now(), "updatedAt": now(),
            })
            await col.update_one({"_id": item["_id"]}, {"$set": {"status": "learning"}})
            made += 1
        return made

    c1 = await build_cards(db.vocab(), "word", "word", 40)
    c2 = await build_cards(db.phrases(), "phrase", "phrase", 20)
    c3 = await build_cards(db.patterns(), "sentence_pattern", "template", 10)
    print(f"  Built {c1 + c2 + c3} starter flashcards")
    print("Done. Log in with the email above to see your seeded data.")


def main():
    parser = argparse.ArgumentParser(description="Seed IELTS starter data")
    parser.add_argument("--email", required=True, help="target user email")
    parser.add_argument("--password", default="changeme123", help="password if user is created")
    parser.add_argument("--reset", action="store_true", help="remove existing seed data first")
    args = parser.parse_args()
    asyncio.run(seed(args.email, args.password, args.reset))


if __name__ == "__main__":
    main()
