"""Saved study-card translations are reused instead of calling the translator again."""
from study.translate import normalize_language, normalize_translation, stored_translation


def test_saved_translation_is_reused_for_that_language():
    card = {
        "userId": "user-1",
        "translations": {
            "fa": {"front": "واژه", "meaning": "معنی", "examples": ["مثال"], "collocations": [], "notes": ""},
        },
    }
    saved = stored_translation(card, "fa")
    assert saved is not None
    assert saved["front"] == "واژه"
    assert stored_translation(card, "ar") is None


def test_blank_translation_is_not_treated_as_saved():
    card = {"translations": {"fa": {"front": "  ", "meaning": "", "examples": [], "collocations": [], "notes": ""}}}
    assert stored_translation(card, "fa") is None
    assert normalize_translation({}, "fa") is None


def test_unknown_settings_language_uses_persian():
    assert normalize_language("fa") == "fa"
    assert normalize_language(" FA ") == "fa"
    assert normalize_language("nope") == "fa"
    assert normalize_language(None) == "fa"
