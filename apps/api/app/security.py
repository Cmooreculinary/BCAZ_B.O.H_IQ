from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings


class TokenError(ValueError):
    pass


def hash_password(password: str, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("Password must not be empty.")
    actual_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), actual_salt, 310_000)
    return f"pbkdf2_sha256$310000${actual_salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (TypeError, ValueError):
        return False


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: str, organization_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": user_id,
        "organization_id": organization_id,
        "exp": int(expires.timestamp()),
    }
    body = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _encode(
        hmac.new(settings.auth_secret.encode(), body.encode(), hashlib.sha256).digest()
    )
    return f"{body}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
        expected = _encode(
            hmac.new(settings.auth_secret.encode(), body.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise TokenError("Invalid token signature.")
        payload = json.loads(_decode(body))
        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise TokenError("Token has expired.")
        if not payload.get("sub") or not payload.get("organization_id"):
            raise TokenError("Token is incomplete.")
        return payload
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, TokenError):
            raise
        raise TokenError("Invalid access token.") from exc

