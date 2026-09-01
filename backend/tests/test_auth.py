"""Tests for password hashing and JWT create/decode/revocation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

import auth  # noqa: E402


def test_password_hash_roundtrip():
    h = auth.hash_password("s3cret-pw")
    assert h != "s3cret-pw"
    assert auth.verify_password("s3cret-pw", h)
    assert not auth.verify_password("wrong", h)


def test_token_encode_decode():
    tok = auth.create_token(42, "u@x.com", "user", token_version=3)
    payload = auth.decode_token(tok)
    assert payload["sub"] == "42"
    assert payload["email"] == "u@x.com"
    assert payload["role"] == "user"
    assert payload["tv"] == 3


def test_decode_rejects_garbage():
    with pytest.raises(HTTPException):
        auth.decode_token("not.a.valid.token")


def test_get_current_user_requires_bearer():
    with pytest.raises(HTTPException):
        auth.get_current_user(None)
    with pytest.raises(HTTPException):
        auth.get_current_user("Basic abc")
