from datetime import timedelta
import time
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


class TestSecurityUtils:
    def test_password_hashing_and_verification(self):
        password = "SecureOfficerPassword2026!"
        hashed = hash_password(password)

        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_jwt_create_and_decode(self):
        token = create_access_token(
            subject="officer-id-123",
            extra_claims={"badge": "LM-DEL-042", "role": "officer"},
        )
        assert isinstance(token, str)

        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "officer-id-123"
        assert payload["badge"] == "LM-DEL-042"
        assert payload["role"] == "officer"
        assert "exp" in payload
        assert "iat" in payload

    def test_jwt_expired_token(self):
        # Create an already-expired token
        token = create_access_token(
            subject="officer-id-expired",
            expires_delta=timedelta(seconds=-10),
        )
        payload = decode_access_token(token)
        assert payload is None

    def test_jwt_invalid_token(self):
        payload = decode_access_token("not.a.valid.jwt.token")
        assert payload is None
