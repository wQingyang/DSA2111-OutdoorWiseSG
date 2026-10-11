import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import AccountRecord, SessionRecord


class AccountRepository:
    def __init__(self, data_root: Path):
        self.path = Path(data_root) / "runtime" / "accounts.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    normalized_username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id);
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _user(row):
        return AccountRecord(user_id=row["user_id"], username=row["username"],
            normalized_username=row["normalized_username"], password_hash=row["password_hash"],
            created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]))

    def find_user(self, normalized_username):
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE normalized_username=?", (normalized_username,)).fetchone()
        return self._user(row) if row else None

    def get_user(self, user_id):
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return self._user(row) if row else None

    def create_user(self, user):
        with self._lock, self._connect() as db:
            try:
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (user.user_id, user.username,
                    user.normalized_username, user.password_hash, user.created_at.isoformat(), user.updated_at.isoformat()))
                db.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("Username already exists") from exc
        return user

    def create_session(self, session: SessionRecord):
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (session.token_hash, session.user_id,
                session.created_at.isoformat(), session.expires_at.isoformat()))
            db.commit()

    def get_session_user(self, token_hash, now=None):
        now = now or datetime.now(timezone.utc)
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
            if row and datetime.fromisoformat(row["expires_at"]) <= now:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,)); db.commit(); row = None
        return self.get_user(row["user_id"]) if row else None

    def delete_session(self, token_hash):
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,)); db.commit()
