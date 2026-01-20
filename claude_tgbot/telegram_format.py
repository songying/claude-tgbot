"""Utilities for encoding and line wrapping normalization for Telegram messages."""

from __future__ import annotations

import textwrap
from typing import Iterable, List


def normalize_newlines(text: str) -> str:
    """Normalize CRLF/CR newlines to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_line_wrapping(text: str, max_line_length: int = 120) -> str:
    """Wrap long lines to avoid oversized Telegram payloads."""
    if max_line_length <= 0:
        return text

    wrapped_lines = []
    for line in text.split("\n"):
        if len(line) <= max_line_length:
            wrapped_lines.append(line)
            continue
        wrapped_lines.append(
            textwrap.fill(
                line,
                width=max_line_length,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )
        )
    return "\n".join(wrapped_lines)


def sanitize_utf8(text: str) -> str:
    """Ensure the string can be safely encoded in UTF-8."""
    return text.encode("utf-8", "replace").decode("utf-8", "replace")


def normalize_for_telegram(
    text: str,
    max_line_length: int = 120,
) -> str:
    """Normalize text for Telegram by fixing newlines, wrapping, and encoding."""
    normalized = normalize_newlines(text)
    normalized = normalize_line_wrapping(normalized, max_line_length=max_line_length)
    return sanitize_utf8(normalized)


def split_for_telegram(
    text: str,
    max_chars: int = 4000,
    max_bytes: int = 4096,
    max_line_length: int = 120,
) -> List[str]:
    """Split text into Telegram-safe chunks with encoding normalization."""
    normalized = normalize_for_telegram(text, max_line_length=max_line_length)
    return list(_chunk_text(normalized, max_chars=max_chars, max_bytes=max_bytes))


def _chunk_text(text: str, max_chars: int, max_bytes: int) -> Iterable[str]:
    if max_chars <= 0 or max_bytes <= 0:
        raise ValueError("max_chars and max_bytes must be positive")

    current: List[str] = []
    current_bytes = 0

    def flush() -> str:
        nonlocal current, current_bytes
        chunk = "".join(current)
        current = []
        current_bytes = 0
        return chunk

    for segment in text.splitlines(keepends=True):
        segment_bytes = len(segment.encode("utf-8"))
        if len(segment) <= max_chars and segment_bytes <= max_bytes:
            if (
                len(current) + len(segment) > max_chars
                or current_bytes + segment_bytes > max_bytes
            ):
                yield flush()
            current.append(segment)
            current_bytes += segment_bytes
            continue

        for char in segment:
            char_bytes = len(char.encode("utf-8"))
            if len(current) + 1 > max_chars or current_bytes + char_bytes > max_bytes:
                yield flush()
            current.append(char)
            current_bytes += char_bytes

    if current:
        yield flush()
