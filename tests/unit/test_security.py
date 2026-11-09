"""Unit tests: app.utilities.security and app.config helpers (no DB, no HTTP)."""

from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest

from app.config import get_settings, mask_database_uri, mask_secret
from app.utilities import security


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        assert security.encrypt_password("secret") != "secret"

    def test_hash_is_salted(self):
        assert security.encrypt_password("secret") != security.encrypt_password("secret")

    def test_verify_accepts_correct_password(self):
        hashed = security.encrypt_password("secret")
        assert security.verify_password("secret", hashed) is True

    def test_verify_rejects_wrong_password(self):
        hashed = security.encrypt_password("secret")
        assert security.verify_password("not-secret", hashed) is False


class TestAccessToken:
    def _decode(self, token):
        settings = get_settings()
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])

    def test_token_contains_claims_and_expiry(self):
        token = security.create_access_token({"sub": "7", "role": "admin"})
        payload = self._decode(token)
        assert payload["sub"] == "7"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_expired_token_is_rejected_on_decode(self):
        token = security.create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-5))
        with pytest.raises(jwt.ExpiredSignatureError):
            self._decode(token)

    def test_input_dict_is_not_mutated(self):
        data = {"sub": "1"}
        security.create_access_token(data)
        assert data == {"sub": "1"}


class TestCookieFlags:
    def test_development_cookie_is_lax_and_not_secure(self, monkeypatch):
        monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(env="development"))
        flags = security.access_token_cookie_kwargs()
        assert flags == {"httponly": True, "samesite": "lax", "secure": False}

    @pytest.mark.parametrize("env", ["production", "prod", "PRODUCTION"])
    def test_production_cookie_is_secure(self, monkeypatch, env):
        monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(env=env))
        flags = security.access_token_cookie_kwargs()
        assert flags["secure"] is True
        assert flags["samesite"] == "none"
        assert flags["httponly"] is True


class TestConfigMasking:
    def test_mask_secret_keeps_tail(self):
        assert mask_secret("abcdefgh") == "****efgh"

    def test_mask_secret_short_value_fully_masked(self):
        assert mask_secret("abc") == "***"

    def test_mask_secret_unset(self):
        assert mask_secret(None) == "(unset)"
        assert mask_secret("") == "(unset)"

    def test_mask_database_uri_hides_password(self):
        masked = mask_database_uri("postgresql://user:hunter2@host:5432/db")
        assert "hunter2" not in masked
        assert masked == "postgresql://user:****@host:5432/db"

    def test_mask_database_uri_without_credentials_unchanged(self):
        assert mask_database_uri("sqlite:///database.db") == "sqlite:///database.db"
