"""Human-readable upload size checks."""
from __future__ import annotations


def format_byte_size(num: int) -> str:
    n = max(0, int(num))
    if n >= 1024 * 1024:
        value = n / (1024 * 1024)
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text} MB"
    if n >= 1024:
        value = n / 1024
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text} KB"
    return f"{n} B"


def file_too_large_message(size: int, limit: int, *, at_least: bool = False) -> str:
    shown = format_byte_size(size)
    if at_least:
        shown = f"over {shown}"
    elif size > limit and shown == format_byte_size(limit):
        shown = f"{size:,} bytes"
    return f"File is too large ({shown}). The limit is {format_byte_size(limit)}."
