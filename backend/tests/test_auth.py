"""tests/test_auth.py — password hashing and JWT token round-trip."""

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hashing_round_trip():
    hashed = hash_password("mySecurePass123")
    assert hashed != "mySecurePass123"
    assert verify_password("mySecurePass123", hashed)
    assert not verify_password("wrongPassword", hashed)


def test_jwt_token_round_trip():
    token = create_access_token({"sub": "user-123"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"


def test_invalid_jwt_returns_none():
    assert decode_access_token("not.a.real.token") is None
