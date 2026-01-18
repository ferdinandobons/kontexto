"""User data models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Represents a user in the system."""

    id: int
    email: str
    name: str
    password_hash: str
    created_at: datetime
    is_active: bool = True
    is_admin: bool = False

    @classmethod
    def from_row(cls, row: dict) -> "User":
        """Create User from database row."""
        return cls(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            password_hash=row["password_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
            is_active=row.get("is_active", True),
            is_admin=row.get("is_admin", False),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary (without sensitive data)."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "is_admin": self.is_admin,
        }

    def is_authenticated(self) -> bool:
        """Check if user is authenticated and active."""
        return self.is_active


@dataclass
class UserCreate:
    """Data for creating a new user."""

    email: str
    name: str
    password_hash: str

    def validate(self) -> list[str]:
        """Validate creation data."""
        errors = []
        if not self.email or "@" not in self.email:
            errors.append("Invalid email")
        if not self.name or len(self.name) < 2:
            errors.append("Name must be at least 2 characters")
        return errors


@dataclass
class UserUpdate:
    """Data for updating a user."""

    name: Optional[str] = None
    email: Optional[str] = None


class UserRole:
    """User role constants."""

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

    @classmethod
    def all_roles(cls) -> list[str]:
        """Get all available roles."""
        return [cls.ADMIN, cls.USER, cls.GUEST]

    @classmethod
    def is_valid(cls, role: str) -> bool:
        """Check if role is valid."""
        return role in cls.all_roles()
