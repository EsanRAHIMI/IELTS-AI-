"""Object storage for an uploaded coursebook."""
import pytest

from config import Settings, settings
from storage import s3_service
from storage.s3_service import StorageUnavailable, build_user_source_key, upload_file_bytes


PDF_NAME = "Oxford Word Skills Elementary 2nd Edition [www.languagecentre.ir].pdf"


def test_s3_client_does_not_use_the_60s_chunked_default():
    cfg = s3_service._client_config()
    assert cfg.read_timeout == 300
    assert cfg.connect_timeout == 10
    assert cfg.request_checksum_calculation == "when_required"
    assert cfg.response_checksum_validation == "when_required"


def test_coursebook_pdf_is_uploaded_in_parts(monkeypatch):
    captured = {}

    class FakeClient:
        def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None, Config=None):
            captured["body"] = fileobj.read()
            captured["bucket"] = bucket
            captured["key"] = key
            captured["content_type"] = (ExtraArgs or {})["ContentType"]
            captured["threshold"] = Config.multipart_threshold
            captured["chunk"] = Config.multipart_chunksize

    monkeypatch.setattr(s3_service, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(settings, "aws_access_key_id", "key")
    monkeypatch.setattr(settings, "aws_secret_access_key", "secret")
    monkeypatch.setattr(settings, "aws_s3_bucket", "coursebooks")

    key = build_user_source_key("user", "source", PDF_NAME)
    data = b"%PDF-1.7" + (b"x" * (9 * 1024 * 1024))
    meta = upload_file_bytes(key, data, "application/pdf")

    assert meta["storage"] == "s3"
    assert meta["bucket"] == "coursebooks"
    assert meta["sizeBytes"] == len(data)
    assert captured["body"] == data
    assert captured["content_type"] == "application/pdf"
    assert captured["threshold"] == 8 * 1024 * 1024
    assert captured["chunk"] == 8 * 1024 * 1024
    assert captured["key"].endswith(
        "Oxford_Word_Skills_Elementary_2nd_Edition_www.languagecentre.ir.pdf"
    )
    assert "[" not in captured["key"] and "]" not in captured["key"]


def test_production_without_aws_does_not_keep_the_file_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")
    monkeypatch.setattr(settings, "aws_s3_bucket", "")
    monkeypatch.setattr(Settings, "allow_local_storage", property(lambda self: False))

    with pytest.raises(StorageUnavailable):
        upload_file_bytes("users/u/sources/s/original/note.txt", b"hello", "text/plain")

    assert list(tmp_path.rglob("*")) == []
