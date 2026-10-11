import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Request, Response

from .models import AccountRecord, SessionRecord, UserPublic
from .repository import AccountRepository

SESSION_COOKIE = "outdoorwise_session"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


def normalize_username(username: str) -> str:
    value = username.strip().lower()
    if not USERNAME_RE.fullmatch(value):
        raise ValueError("Username must be 3–32 letters, numbers, underscores, or hyphens")
    return value


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$16384$8$1$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = stored.split("$")
        if algorithm != "scrypt": return False
        salt = base64.urlsafe_b64decode(salt_text); expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def public_user(user: AccountRecord) -> UserPublic:
    return UserPublic(user_id=user.user_id, username=user.username, created_at=user.created_at)


def current_user_from_request(request: Request, repository: AccountRepository) -> UserPublic:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(401, "Authentication required")
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    user = repository.get_session_user(token_hash)
    if user is None:
        raise HTTPException(401, "Authentication required")
    return public_user(user)


def set_session_cookie(response: Response, repository: AccountRepository, user_id: str):
    raw = secrets.token_urlsafe(32); now = datetime.now(timezone.utc); expires = now + timedelta(days=7)
    repository.create_session(SessionRecord(token_hash=hashlib.sha256(raw.encode()).hexdigest(), user_id=user_id,
        created_at=now, expires_at=expires))
    response.set_cookie(SESSION_COOKIE, raw, httponly=True, samesite="lax",
        secure=os.getenv("OUTDOORWISE_SECURE_COOKIES", "0") == "1", max_age=7 * 86400)


def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE)
