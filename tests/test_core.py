"""测试 core 模块：加密、密码哈希、Session"""

import time

import pytest

from app.core.security import CryptoService, hash_password, verify_password
from app.core.session import SessionManager


# ---- CryptoService (Fernet SMTP 密码加密) ----


class TestCryptoService:
    def test_encrypt_decrypt_roundtrip(self):
        crypto = CryptoService("my-secret-key")
        plaintext = "smtp-password-123"
        encrypted = crypto.encrypt(plaintext)
        assert encrypted != plaintext
        assert crypto.decrypt(encrypted) == plaintext

    def test_different_keys_cannot_decrypt(self):
        crypto1 = CryptoService("key-1")
        crypto2 = CryptoService("key-2")
        encrypted = crypto1.encrypt("password")
        with pytest.raises(Exception):
            crypto2.decrypt(encrypted)

    def test_same_key_always_works(self):
        crypto1 = CryptoService("same-key")
        crypto2 = CryptoService("same-key")
        encrypted = crypto1.encrypt("test")
        assert crypto2.decrypt(encrypted) == "test"

    def test_encrypt_empty_string(self):
        crypto = CryptoService("key")
        encrypted = crypto.encrypt("")
        assert crypto.decrypt(encrypted) == ""

    def test_encrypt_unicode(self):
        crypto = CryptoService("key")
        plaintext = "密码测试123"
        encrypted = crypto.encrypt(plaintext)
        assert crypto.decrypt(encrypted) == plaintext

    def test_each_encryption_produces_different_ciphertext(self):
        crypto = CryptoService("key")
        e1 = crypto.encrypt("same")
        e2 = crypto.encrypt("same")
        # Fernet 包含时间戳和随机 IV，所以每次加密结果不同
        assert e1 != e2


# ---- Password Hashing (bcrypt) ----


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("admin123")
        assert verify_password("admin123", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # 不同的 salt

    def test_hash_format(self):
        hashed = hash_password("test")
        assert hashed.startswith("$2b$")  # bcrypt 格式


# ---- SessionManager ----


class TestSessionManager:
    def test_create_and_load_session(self):
        sm = SessionManager("secret", max_age=3600)
        token = sm.create_session({"admin_id": "abc-123", "role": "admin"})
        data = sm.load_session(token)
        assert data["admin_id"] == "abc-123"
        assert data["role"] == "admin"

    def test_invalid_token_returns_none(self):
        sm = SessionManager("secret")
        assert sm.load_session("invalid-token") is None

    def test_different_secret_returns_none(self):
        sm1 = SessionManager("secret-1")
        sm2 = SessionManager("secret-2")
        token = sm1.create_session({"id": "1"})
        assert sm2.load_session(token) is None

    def test_tampered_token_returns_none(self):
        sm = SessionManager("secret")
        token = sm.create_session({"id": "1"})
        tampered = token[:-5] + "XXXXX"
        assert sm.load_session(tampered) is None

    def test_cookie_name_default(self):
        sm = SessionManager("secret")
        assert sm.cookie_name == "mp_session"

    def test_expired_session_returns_none(self):
        sm = SessionManager("secret", max_age=1)
        token = sm.create_session({"id": "1"})
        time.sleep(2.5)  # itsdangerous 用整数秒比较(>)，需要 age > max_age
        assert sm.load_session(token) is None
