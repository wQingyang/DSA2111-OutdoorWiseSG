from datetime import datetime, timezone
from uuid import uuid4

from .models import AccountCredentials, AccountRecord, UserPublic
from .repository import AccountRepository
from .security import hash_password, normalize_username, public_user, verify_password


class AccountService:
    def __init__(self, repository: AccountRepository): self.repository = repository

    def availability(self, username):
        normalized = normalize_username(username)
        return self.repository.find_user(normalized) is None

    def register(self, credentials: AccountCredentials) -> AccountRecord:
        normalized = normalize_username(credentials.username)
        now = datetime.now(timezone.utc)
        return self.repository.create_user(AccountRecord(user_id=str(uuid4()), username=credentials.username.strip(),
            normalized_username=normalized, password_hash=hash_password(credentials.password), created_at=now, updated_at=now))

    def authenticate(self, credentials: AccountCredentials) -> AccountRecord | None:
        try: normalized = normalize_username(credentials.username)
        except ValueError: return None
        user = self.repository.find_user(normalized)
        return user if user and verify_password(credentials.password, user.password_hash) else None

    @staticmethod
    def public(user): return public_user(user)
