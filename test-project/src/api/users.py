"""User API endpoints."""

from typing import Optional
from src.models.user import User, UserCreate, UserUpdate
from src.services.user_service import UserService
from src.middleware.auth import require_auth


class UserController:
    """Handles all user-related API endpoints.

    This controller provides CRUD operations for users and integrates
    with the authentication middleware for protected routes.
    """

    def __init__(self, user_service: UserService):
        """Initialize the controller with a user service.

        Args:
            user_service: The service handling user business logic.
        """
        self.user_service = user_service

    def get_user(self, user_id: int) -> Optional[User]:
        """Retrieve a user by their ID.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            The User object if found, None otherwise.

        Raises:
            ValueError: If user_id is negative.
        """
        if user_id < 0:
            raise ValueError("User ID must be positive")
        return self.user_service.find_by_id(user_id)

    def get_all_users(self, limit: int = 100, offset: int = 0) -> list[User]:
        """Retrieve all users with pagination.

        Args:
            limit: Maximum number of users to return.
            offset: Number of users to skip.

        Returns:
            List of User objects.
        """
        return self.user_service.find_all(limit=limit, offset=offset)

    @require_auth
    def create_user(self, data: UserCreate) -> User:
        """Create a new user.

        Args:
            data: The user creation data.

        Returns:
            The newly created User object.

        Raises:
            ValidationError: If the data is invalid.
        """
        self._validate_email(data.email)
        return self.user_service.create(data)

    @require_auth
    def update_user(self, user_id: int, data: UserUpdate) -> Optional[User]:
        """Update an existing user.

        Args:
            user_id: The ID of the user to update.
            data: The update data.

        Returns:
            The updated User object if found.
        """
        return self.user_service.update(user_id, data)

    @require_auth
    def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID.

        Args:
            user_id: The ID of the user to delete.

        Returns:
            True if deleted, False if not found.
        """
        return self.user_service.delete(user_id)

    def _validate_email(self, email: str) -> None:
        """Validate email format."""
        if "@" not in email:
            raise ValueError("Invalid email format")


def validate_user_id(user_id: int) -> bool:
    """Validate that a user ID is valid.

    Args:
        user_id: The ID to validate.

    Returns:
        True if valid.
    """
    return isinstance(user_id, int) and user_id > 0
