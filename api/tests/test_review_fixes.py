"""Regression tests for the security and correctness review."""
from __future__ import annotations

import asyncio

import pytest

from http_util import clamp_limit, content_disposition, read_bool, search_regex
from jobs.merge_stats import apply_source_stats
from quotas import MemoryWindowLimiter, quota_block, take_ai_slot
from security_policy import is_local_context, jwt_startup_error
from study.plan import focus_query, focus_skill_tokens, plan_sizes
from study.sm2 import review
from url_guard import (
    UrlRejected,
    choose_connect_ip,
    fetch_public_bytes,
    ip_is_blocked,
    pinned_transport,
    validate_url_syntax,
)


BLOCKED = [
    "127.0.0.1",
    "10.1.2.3",
    "192.168.0.5",
    "172.16.0.1",
    "169.254.169.254",
    "0.0.0.0",
    "100.64.0.1",
    "100.100.100.200",
    "224.0.0.1",
    "::1",
    "fe80::1",
    "fd00:ec2::254",
    "::ffff:127.0.0.1",
    "::ffff:169.254.169.254",
]
PUBLIC = ["8.8.8.8", "1.1.1.1", "93.184.216.34"]


@pytest.mark.parametrize("ip", BLOCKED)
def test_private_and_metadata_addresses_are_blocked(ip):
    assert ip_is_blocked(ip)


@pytest.mark.parametrize("ip", PUBLIC)
def test_public_addresses_are_allowed(ip):
    assert not ip_is_blocked(ip)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/latest/meta-data",
        "http://169.254.169.254/",
        "http://2130706433/",
        "http://localhost/admin",
        "http://metadata.google.internal/",
        "http://user:pass@example.com/",
        "file:///etc/passwd",
        "http://example.com:22/",
        "http://10.0.0.8/",
        "https://app.internal/secret",
    ],
)
def test_url_syntax_rejects_unsafe_targets(url):
    with pytest.raises(UrlRejected):
        validate_url_syntax(url)


def test_public_https_url_is_accepted():
    assert validate_url_syntax("https://example.com/ielts") == "example.com"


def test_mixed_dns_answers_are_rejected():
    with pytest.raises(UrlRejected):
        choose_connect_ip("example.com", resolver=lambda _host: ["8.8.8.8", "127.0.0.1"])


def test_public_dns_answer_is_used():
    assert choose_connect_ip("example.com", resolver=lambda _host: ["93.184.216.34"]) == "93.184.216.34"


def test_pinned_transport_dials_through_the_guard():
    transport = asyncio.run(pinned_transport())
    backend = transport._pool._network_backend
    assert backend.__class__.__name__ == "_Backend"


def test_redirect_to_metadata_is_not_fetched():
    seen = []

    async def opener(url):
        seen.append(url)
        return 302, {"location": "http://169.254.169.254/latest/meta-data"}, b""

    with pytest.raises(UrlRejected):
        asyncio.run(fetch_public_bytes("https://example.com/start", opener=opener, max_bytes=1000))
    assert seen == ["https://example.com/start"]


def test_response_body_is_capped():
    async def opener(_url):
        return 200, {}, b"x" * 50

    with pytest.raises(UrlRejected) as caught:
        asyncio.run(fetch_public_bytes("https://example.com/big", opener=opener, max_bytes=20))
    assert caught.value.code == "size"


def test_reprocess_replaces_frequency_instead_of_adding():
    first = apply_source_stats(None, "source-a", 4)
    assert first["frequency"] == 4
    again = apply_source_stats(
        {"frequency": 4, "sourceIds": ["source-a"], "sourceFrequency": {"source-a": 4}},
        "source-a",
        4,
    )
    assert again["frequency"] == 4
    changed = apply_source_stats(again, "source-a", 6)
    assert changed["frequency"] == 6
    both = apply_source_stats(changed, "source-b", 2)
    assert both["frequency"] == 8
    assert both["sourceIds"] == ["source-a", "source-b"]


def test_legacy_single_source_reprocess_does_not_double():
    legacy = {"frequency": 10, "sourceIds": ["source-a"]}
    updated = apply_source_stats(legacy, "source-a", 3)
    assert updated["frequency"] == 3


def test_query_flags_accept_camel_case():
    params = {"keepExtractedData": "false", "resetExtractedData": "true"}
    assert read_bool(params, ("keepExtractedData", "keep_extracted_data"), True) is False
    assert read_bool(params, ("resetExtractedData", "reset_extracted_data"), False) is True
    assert read_bool({}, ("keepExtractedData", "keep_extracted_data"), True) is True


def test_limit_zero_is_not_unlimited():
    assert clamp_limit(0, default=50, maximum=100) == 50
    assert clamp_limit(500, default=50, maximum=100) == 100


def test_search_is_escaped():
    pattern = search_regex("(a+)+")
    assert pattern["$regex"] == r"\(a\+\)\+"


def test_content_disposition_strips_quotes():
    header = content_disposition('report";\r\nfoo.pdf')
    assert '"' not in header.split("filename=", 1)[1].strip('"')
    assert "\n" not in header
    assert "\r" not in header


def test_jwt_secret_is_refused_outside_local_dev():
    assert jwt_startup_error(secret="dev-insecure-secret-change-me", algorithm="HS256", local=True) is None
    assert jwt_startup_error(secret="dev-insecure-secret-change-me", algorithm="HS256", local=False)
    assert jwt_startup_error(secret="x" * 40, algorithm="none", local=True)
    assert jwt_startup_error(secret="x" * 40, algorithm="HS256", local=False) is None
    assert is_local_context(app_env="production", api_prefix="", cors_origins=["http://localhost:3000"]) is False
    assert is_local_context(app_env="development", api_prefix="/api", cors_origins=["http://localhost:3000"]) is False
    assert is_local_context(app_env="development", api_prefix="", cors_origins=["https://example.com"]) is False
    assert is_local_context(app_env="development", api_prefix="", cors_origins=["http://localhost:3000"]) is True


def test_invalid_grade_is_rejected():
    with pytest.raises(ValueError):
        review({"easeFactor": 2.5, "repetitions": 0, "interval": 0}, "banana")


def test_daily_plan_uses_saved_target_and_focus():
    assert plan_sizes(30) == {"words": 30, "phrases": 15, "patterns": 10}
    assert plan_sizes(10)["words"] == 10
    tokens = focus_skill_tokens(["Academic", "Writing", "not-a-skill"])
    assert tokens == ["writing"]
    query = focus_query(tokens)
    assert query["$or"][0]["ieltsUseCases"]["$regex"] == "writing"


def test_quota_and_rate_limit():
    assert quota_block(
        sources=200, max_sources=200, used_bytes=0, extra_bytes=1,
        max_bytes=100, active_jobs=0, max_jobs=3,
    )
    assert take_ai_slot(40, 40) is False
    assert take_ai_slot(3, 40) is True


def test_memory_rate_limiter_blocks_after_the_cap():
    limiter = MemoryWindowLimiter()

    async def run():
        assert await limiter.allow("register:1", 2, 3600)
        assert await limiter.allow("register:1", 2, 3600)
        assert await limiter.allow("register:1", 2, 3600) is False

    asyncio.run(run())


def test_upload_metadata_has_no_public_url(tmp_path, monkeypatch):
    from config import settings
    from storage.s3_service import public_url, upload_file_bytes

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")
    monkeypatch.setattr(settings, "aws_s3_bucket", "")
    meta = upload_file_bytes("users/u/sources/s/original/note.txt", b"hello", "text/plain")
    assert public_url("users/u/sources/s/original/note.txt") == ""
    assert "url" not in meta
    assert meta["storage"] == "local"


def test_page_cap_is_never_unlimited():
    from config import Settings

    assert Settings(ocr_max_pages=0, max_pdf_pages=80).effective_page_cap() == 80
    assert Settings(ocr_max_pages=10, max_pdf_pages=80).effective_page_cap() == 10
    assert Settings(ocr_max_pages=500, max_pdf_pages=80).effective_page_cap() == 80
