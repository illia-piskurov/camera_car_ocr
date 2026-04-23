from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


def _normalize_key(raw_key: str) -> bytes:
    key = raw_key.strip()
    if not key:
        raise ValueError("Missing encryption key")

    try:
        return base64.urlsafe_b64decode(key.encode("utf-8"))
    except Exception:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=4)
def _fernet(raw_key: str) -> Fernet:
    return Fernet(_normalize_key(raw_key))


def encrypt_text(value: str, raw_key: str) -> str:
    if not value:
        return ""
    token = _fernet(raw_key).encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(value: str, raw_key: str) -> str:
    if not value:
        return ""
    try:
        decoded = _fernet(raw_key).decrypt(value.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted value") from exc
    return decoded.decode("utf-8")
