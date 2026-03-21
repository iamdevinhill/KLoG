"""Tests for authentication utilities."""

from datetime import datetime, timezone, timedelta

import jwt
import pytest

from app.auth import hash_password, verify_password, create_token, get_current_user
from app.config import JWT_SECRET


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "testpassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes_for_same_password(self):
        password = "testpassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # bcrypt uses random salts
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestJWT:
    def test_create_token_returns_string(self):
        token = create_token("testuser")
        assert isinstance(token, str)

    def test_token_contains_correct_subject(self):
        token = create_token("testuser")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "testuser"

    def test_token_has_expiry(self):
        token = create_token("testuser")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        assert "exp" in payload
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp > now + timedelta(days=29)


class TestGetCurrentUser:
    def test_missing_header_raises_401(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(None)
        assert exc_info.value.status_code == 401

    def test_invalid_format_raises_401(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("NotBearer token")
        assert exc_info.value.status_code == 401

    def test_valid_token_returns_username(self):
        token = create_token("alice")
        result = get_current_user(f"Bearer {token}")
        assert result == "alice"

    def test_expired_token_raises_401(self):
        from fastapi import HTTPException
        payload = {
            "sub": "alice",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(f"Bearer {token}")
        assert exc_info.value.status_code == 401

    def test_invalid_token_raises_401(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("Bearer garbage.token.here")
        assert exc_info.value.status_code == 401
