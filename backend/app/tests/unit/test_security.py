"""Unit tests for security utilities."""

import uuid

import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_magic_link_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_password_and_verify_password_round_trip():
    plain = "MySecurePassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_password_when_wrong_password_then_returns_false():
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_create_access_token_when_decoded_then_contains_required_claims():
    user_id = uuid.uuid4()
    school_id = uuid.uuid4()
    token = create_access_token(user_id, school_id, "STUDENT")
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["school_id"] == str(school_id)
    assert payload["role"] == "STUDENT"
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_when_kaihle_admin_then_school_id_is_none():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, None, "KAIHLE_ADMIN")
    payload = decode_token(token)
    assert payload["school_id"] is None


def test_decode_token_when_expired_then_raises_invalid_token_error():
    user_id = uuid.uuid4()
    # Create token that expired 1 minute ago
    token = create_access_token(user_id, None, "STUDENT", expires_in=-1)
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_decode_token_when_tampered_signature_then_raises_invalid_token_error():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, uuid.uuid4(), "STUDENT")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_generate_refresh_token_returns_raw_and_hash():
    raw, hashed = generate_refresh_token()
    assert len(raw) > 32
    assert hashed == hash_token(raw)
    assert raw != hashed


def test_generate_refresh_token_each_call_produces_unique_tokens():
    raw1, _ = generate_refresh_token()
    raw2, _ = generate_refresh_token()
    assert raw1 != raw2


def test_create_magic_link_token_when_decoded_then_contains_required_claims():
    user_id = uuid.uuid4()
    token = create_magic_link_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "magic_link"
    assert "exp" in payload
    assert "iat" in payload


def test_create_magic_link_token_when_expired_then_raises_invalid_token_error():
    user_id = uuid.uuid4()
    # Create token that expired 1 minute ago
    token = create_magic_link_token(user_id, expires_in_minutes=-1)
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_hash_token_produces_consistent_hash():
    raw = "test-token-value-12345"
    hash1 = hash_token(raw)
    hash2 = hash_token(raw)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest is 64 characters


def test_hash_token_different_inputs_produce_different_hashes():
    hash1 = hash_token("token-one")
    hash2 = hash_token("token-two")
    assert hash1 != hash2
