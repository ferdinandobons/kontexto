"""Authentication API endpoints."""

from typing import Optional
from datetime import datetime, timedelta
from src.models.user import User
from src.services.auth_service import AuthService
from src.utils.security import hash_password, verify_password, generate_token


class AuthController:
    """Handles authentication endpoints."""

    TOKEN_EXPIRY_HOURS = 24

    def __init__(self, auth_service: AuthService):
        """Initialize with auth service."""
        self.auth_service = auth_service

    def login(self, email: str, password: str) -> Optional[dict]:
        """Authenticate a user and return a token.

        Args:
            email: User's email.
            password: User's password.

        Returns:
            Dict with token and user info, or None if invalid.
        """
        user = self.auth_service.find_by_email(email)
        if not user:
            return None

        if not verify_password(password, user.password_hash):
            self.auth_service.record_failed_attempt(email)
            return None

        token = generate_token(user.id, self.TOKEN_EXPIRY_HOURS)
        return {
            "token": token,
            "user": user,
            "expires_at": datetime.now() + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        }

    def logout(self, token: str) -> bool:
        """Invalidate a token.

        Args:
            token: The token to invalidate.

        Returns:
            True if invalidated.
        """
        return self.auth_service.invalidate_token(token)

    def refresh_token(self, token: str) -> Optional[str]:
        """Refresh an authentication token.

        Args:
            token: The current token.

        Returns:
            New token if valid, None otherwise.
        """
        user_id = self.auth_service.validate_token(token)
        if not user_id:
            return None
        return generate_token(user_id, self.TOKEN_EXPIRY_HOURS)

    def register(
        self,
        email: str,
        password: str,
        name: str
    ) -> Optional[User]:
        """Register a new user.

        Args:
            email: User's email.
            password: User's password.
            name: User's display name.

        Returns:
            Created user or None if email exists.
        """
        if self.auth_service.find_by_email(email):
            return None

        password_hash = hash_password(password)
        return self.auth_service.create_user(email, password_hash, name)

    def reset_password_request(self, email: str) -> bool:
        """Request a password reset.

        Args:
            email: User's email.

        Returns:
            True if request sent (always true for security).
        """
        user = self.auth_service.find_by_email(email)
        if user:
            self.auth_service.send_reset_email(user)
        return True  # Don't reveal if email exists

    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using a reset token.

        Args:
            token: Reset token from email.
            new_password: New password.

        Returns:
            True if reset successful.
        """
        user_id = self.auth_service.validate_reset_token(token)
        if not user_id:
            return False
        password_hash = hash_password(new_password)
        return self.auth_service.update_password(user_id, password_hash)


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """Validate password meets security requirements.

    Args:
        password: The password to validate.

    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("Password must contain lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain a digit")

    return len(errors) == 0, errors
