"""Fernet-based encryption for provider API keys.

Uses ``ENCRYPTION_KEY`` env var (url-safe base64, 32 bytes).
Falls back to a deterministic dev key when unset — NOT for production.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet  # noqa: PLW0603
    if _fernet is not None:
        return _fernet

    raw = os.getenv("ENCRYPTION_KEY", "").strip()
    if raw:
        # Derive a valid 32-byte key from whatever the user provides
        key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    else:
        logger.warning("ENCRYPTION_KEY not set — using dev-only default (NOT FOR PRODUCTION)")
        key = base64.urlsafe_b64encode(hashlib.sha256(b"dev-key-options-scanner").digest())

    _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> bytes:
    """Encrypt a plaintext string and return ciphertext bytes."""
    return _get_fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    """Decrypt ciphertext bytes back to a plaintext string."""
    if isinstance(ciphertext, str):
        ciphertext = ciphertext.encode()
    return _get_fernet().decrypt(ciphertext).decode()


def mask_key(key: str | None) -> str:
    """Return masked version showing only last 4 characters."""
    if not key:
        return ""
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


def reset() -> None:
    """Reset singleton for testing."""
    global _fernet  # noqa: PLW0603
    _fernet = None
