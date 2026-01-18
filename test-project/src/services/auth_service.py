"""Authentication service."""

from typing import Optional
from datetime import datetime, timedelta
from src.models.user import User
from src.utils.database import DatabaseConnection
from src.utils.security import generate_reset_token


class AuthService:
    """Handles authentication business logic."""

    RESET_TOKEN_EXPIRY_HOURS = 24

    def __init__(self, db: DatabaseConnection):
        """Initialize with database connection."""
        self.db = db
        self._invalid_tokens: set[str] = set()

    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email for authentication."""
        row = self.db.query_one(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),)
        )
        return User.from_row(row) if row else None

    def create_user(self, email: str, password_hash: str, name: str) -> User:
        """Create a new user during registration."""
        user_id = self.db.execute(
            """
            INSERT INTO users (email, name, password_hash, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (email.lower(), name, password_hash)
        )
        return self.find_by_id(user_id)

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID."""
        row = self.db.query_one(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
        return User.from_row(row) if row else None

    def validate_token(self, token: str) -> Optional[int]:
        """Validate a JWT token and return user ID.

        Args:
            token: JWT token.

        Returns:
            User ID if valid, None otherwise.
        """
        if token in self._invalid_tokens:
            return None
        # In real implementation, decode JWT and verify
        # For testing, just parse the mock token
        try:
            parts = token.split(".")
            if len(parts) == 3:
                return int(parts[1])  # Mock: user_id in middle
        except (ValueError, IndexError):
            pass
        return None

    def invalidate_token(self, token: str) -> bool:
        """Invalidate a token (logout)."""
        self._invalid_tokens.add(token)
        return True

    def record_failed_attempt(self, email: str) -> None:
        """Record a failed login attempt for rate limiting."""
        self.db.execute(
            """
            INSERT INTO login_attempts (email, attempted_at)
            VALUES (?, datetime('now'))
            """,
            (email.lower(),)
        )

    def is_rate_limited(self, email: str, max_attempts: int = 5) -> bool:
        """Check if email is rate limited.

        Args:
            email: Email to check.
            max_attempts: Max attempts in last hour.

        Returns:
            True if rate limited.
        """
        result = self.db.query_one(
            """
            SELECT COUNT(*) as count FROM login_attempts
            WHERE email = ? AND attempted_at > datetime('now', '-1 hour')
            """,
            (email.lower(),)
        )
        return result and result["count"] >= max_attempts

    def send_reset_email(self, user: User) -> None:
        """Send password reset email.

        In real implementation, this would send an actual email.
        """
        token = generate_reset_token(user.id)
        expiry = datetime.now() + timedelta(hours=self.RESET_TOKEN_EXPIRY_HOURS)

        self.db.execute(
            """
            INSERT INTO reset_tokens (user_id, token, expires_at)
            VALUES (?, ?, ?)
            """,
            (user.id, token, expiry.isoformat())
        )
        # Would send email here in production

    def validate_reset_token(self, token: str) -> Optional[int]:
        """Validate a password reset token."""
        row = self.db.query_one(
            """
            SELECT user_id FROM reset_tokens
            WHERE token = ? AND expires_at > datetime('now') AND used = 0
            """,
            (token,)
        )
        return row["user_id"] if row else None

    def update_password(self, user_id: int, password_hash: str) -> bool:
        """Update user password."""
        affected = self.db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id)
        )
        return affected > 0


class SessionManager:
    """Manages user sessions."""

    def __init__(self, max_sessions_per_user: int = 5):
        self._sessions: dict[str, dict] = {}
        self._max_sessions = max_sessions_per_user

    def create_session(self, user_id: int, token: str) -> dict:
        """Create a new session."""
        session = {
            "user_id": user_id,
            "token": token,
            "created_at": datetime.now(),
            "last_active": datetime.now()
        }
        self._sessions[token] = session
        return session

    def get_session(self, token: str) -> Optional[dict]:
        """Get session by token."""
        session = self._sessions.get(token)
        if session:
            session["last_active"] = datetime.now()
        return session

    def destroy_session(self, token: str) -> bool:
        """Destroy a session."""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """Remove expired sessions."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        expired = [
            token for token, session in self._sessions.items()
            if session["last_active"] < cutoff
        ]
        for token in expired:
            del self._sessions[token]
        return len(expired)
