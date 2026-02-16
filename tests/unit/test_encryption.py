"""Unit tests for the Fernet encryption module."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.providers.encryption import decrypt, encrypt, mask_key, reset


class TestEncryption:
    """Tests for encrypt / decrypt round-trip."""

    def setup_method(self) -> None:
        reset()  # clear cached _fernet between tests

    def teardown_method(self) -> None:
        reset()

    def test_encrypt_decrypt_roundtrip(self) -> None:
        plaintext = "my-secret-api-key-12345"
        ciphertext = encrypt(plaintext)
        assert isinstance(ciphertext, bytes)
        assert decrypt(ciphertext) == plaintext

    def test_encrypt_produces_different_ciphertext(self) -> None:
        """Fernet uses random IV so same plaintext → different ciphertext."""
        a = encrypt("hello")
        b = encrypt("hello")
        assert a != b  # probabilistic but practically always true

    def test_decrypt_wrong_key_raises(self) -> None:
        ciphertext = encrypt("secret")
        reset()
        # Change the env var to get a different Fernet key
        with patch.dict(os.environ, {"ENCRYPTION_KEY": "c2VjcmV0LWtleS10aGF0LWlzLWxvbmdlci10aGFuLTMy"}):
            with pytest.raises(Exception):
                decrypt(ciphertext)


class TestMaskKey:
    def test_mask_short_key(self) -> None:
        assert mask_key("abc") == "****"

    def test_mask_long_key(self) -> None:
        assert mask_key("sk-1234567890") == "****7890"

    def test_mask_exactly_four(self) -> None:
        assert mask_key("abcd") == "****"
