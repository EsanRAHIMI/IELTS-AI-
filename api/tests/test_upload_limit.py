from config import Settings
from sources.limits import file_too_large_message, format_byte_size


def test_default_upload_limit_fits_a_coursebook_pdf():
    assert Settings.model_fields["max_upload_bytes"].default == 200 * 1024 * 1024


def test_format_byte_size_uses_mb_for_study_files():
    assert format_byte_size(200 * 1024 * 1024) == "200 MB"
    assert format_byte_size(25 * 1024 * 1024) == "25 MB"
    assert format_byte_size(int(48.2 * 1024 * 1024)) == "48.2 MB"


def test_too_large_message_names_the_file_size_and_the_limit():
    message = file_too_large_message(220 * 1024 * 1024, 200 * 1024 * 1024)
    assert message == "File is too large (220 MB). The limit is 200 MB."


def test_too_large_message_uses_bytes_when_rounding_would_hide_the_size():
    limit = 200 * 1024 * 1024
    message = file_too_large_message(limit + 10, limit)
    assert "209,715,210 bytes" in message
    assert "The limit is 200 MB." in message


def test_too_large_message_can_mark_a_partial_count():
    message = file_too_large_message(1024 * 1024 * 1024, 200 * 1024 * 1024, at_least=True)
    assert message.startswith("File is too large (over ")
    assert "The limit is 200 MB." in message
