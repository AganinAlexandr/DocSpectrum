"""Shared text normalization and hash helpers for DocSpectrum tools.

All text-based entity hashes should pass through this module so pairwise
comparison artifacts and corpus-frequency artifacts stay hash-compatible.
"""

from __future__ import annotations

import hashlib
import re


TOKEN_RE = re.compile(r"[\w]+", flags=re.UNICODE)


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    value = value.strip().lower().replace("\u0451", "\u0435")
    return " ".join(value.split())


def text_tokens(value: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(value.lower()) if len(token) > 1]


def word_shingles(tokens: list[str], size: int = 5) -> list[str]:
    if len(tokens) < size:
        return []
    return [" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)]
