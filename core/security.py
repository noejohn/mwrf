import base64
import hashlib
import hmac
import json
import os
import time

from django.conf import settings


class JWTError(Exception):
    pass


def _b64url_encode(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")


def _b64url_decode(raw_text):
    padding = "=" * (-len(raw_text) % 4)
    return base64.urlsafe_b64decode((raw_text + padding).encode("ascii"))


def _compact_signature(raw_password, salt):
    payload = f"{salt}:{raw_password}".encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    digest = hmac.new(secret, payload, hashlib.sha256).digest()
    return _b64url_encode(digest[:18])


def is_password_hashed(value):
    value_text = str(value or "").strip()
    if not value_text:
        return False
    parts = value_text.split("$")
    if len(parts) != 3:
        return False
    version, salt, signature = parts
    return version == "v1" and len(salt) >= 6 and len(signature) >= 20


def hash_password(raw_password):
    salt = _b64url_encode(os.urandom(6))
    signature = _compact_signature(str(raw_password or ""), salt)
    return f"v1${salt}${signature}"


def set_user_password(user, raw_password, save=True):
    user.userpassword = hash_password(raw_password)
    if save:
        user.save(update_fields=["userpassword"])
    return user.userpassword


def verify_user_password(user, raw_password):
    stored = str(getattr(user, "userpassword", "") or "")
    raw = str(raw_password or "")
    if not stored or not raw:
        return False

    if is_password_hashed(stored):
        try:
            version, salt, signature = stored.split("$")
        except ValueError:
            return False
        if version != "v1":
            return False
        expected_signature = _compact_signature(raw, salt)
        return hmac.compare_digest(signature, expected_signature)

    if stored == raw:
        # Upgrade legacy plain-text password to hashed on first successful login/check.
        set_user_password(user, raw, save=True)
        return True
    return False


def create_jwt_token(payload, expires_in_seconds=8 * 60 * 60):
    now = int(time.time())
    full_payload = {
        **payload,
        "iat": now,
        "exp": now + int(expires_in_seconds),
        "iss": "mwrf",
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(full_payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_jwt_token(token):
    token_value = str(token or "").strip()
    parts = token_value.split(".")
    if len(parts) != 3:
        raise JWTError("Invalid token format.")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise JWTError("Invalid token signature.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise JWTError("Invalid token payload.") from exc

    now = int(time.time())
    exp = int(payload.get("exp", 0))
    if exp and now >= exp:
        raise JWTError("Token expired.")
    return payload
