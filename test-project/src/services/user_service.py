"""User business logic service."""

from typing import Optional
from src.models.user import User, UserCreate, UserUpdate
from src.utils.database import DatabaseConnection


class UserService:
    """Handles user business logic and data access."""

    def __init__(self, db: DatabaseConnection):
        """Initialize with database connection."""
        self.db = db

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find a user by their ID.

        Args:
            user_id: The user's unique identifier.

        Returns:
            User if found, None otherwise.
        """
        row = self.db.query_one(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
        return User.from_row(row) if row else None

    def find_by_email(self, email: str) -> Optional[User]:
        """Find a user by email."""
        row = self.db.query_one(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),)
        )
        return User.from_row(row) if row else None

    def find_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        """Get all users with pagination."""
        rows = self.db.query_all(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [User.from_row(row) for row in rows]

    def create(self, data: UserCreate) -> User:
        """Create a new user.

        Args:
            data: User creation data.

        Returns:
            The created user.

        Raises:
            ValueError: If email already exists.
        """
        if self.find_by_email(data.email):
            raise ValueError(f"Email {data.email} already exists")

        user_id = self.db.execute(
            """
            INSERT INTO users (email, name, password_hash, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (data.email.lower(), data.name, data.password_hash)
        )
        return self.find_by_id(user_id)

    def update(self, user_id: int, data: UserUpdate) -> Optional[User]:
        """Update an existing user."""
        user = self.find_by_id(user_id)
        if not user:
            return None

        updates = []
        params = []

        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if data.email is not None:
            updates.append("email = ?")
            params.append(data.email.lower())

        if not updates:
            return user

        params.append(user_id)
        self.db.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )
        return self.find_by_id(user_id)

    def delete(self, user_id: int) -> bool:
        """Delete a user by ID."""
        affected = self.db.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,)
        )
        return affected > 0

    def count(self) -> int:
        """Get total user count."""
        result = self.db.query_one("SELECT COUNT(*) as count FROM users")
        return result["count"] if result else 0


class UserCache:
    """In-memory cache for user lookups."""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[int, User] = {}
        self._max_size = max_size

    def get(self, user_id: int) -> Optional[User]:
        """Get cached user."""
        return self._cache.get(user_id)

    def set(self, user: User) -> None:
        """Cache a user."""
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        self._cache[user.id] = user

    def invalidate(self, user_id: int) -> None:
        """Remove user from cache."""
        self._cache.pop(user_id, None)

    def _evict_oldest(self) -> None:
        """Remove oldest cached entry."""
        if self._cache:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
