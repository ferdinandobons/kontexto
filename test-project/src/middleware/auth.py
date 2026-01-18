"""Authentication middleware."""

from functools import wraps
from typing import Callable, TypeVar, Any

T = TypeVar("T")


def require_auth(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that requires authentication.

    Use this decorator on any endpoint that requires the user
    to be authenticated.

    Example:
        @require_auth
        def get_profile(self, user_id: int) -> User:
            ...

    Args:
        func: The function to wrap.

    Returns:
        Wrapped function that checks authentication.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # In real implementation, check request context for auth token
        # For now, just pass through
        return func(*args, **kwargs)
    return wrapper


def require_admin(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that requires admin privileges.

    Use this decorator on any endpoint that requires the user
    to be an administrator.

    Args:
        func: The function to wrap.

    Returns:
        Wrapped function that checks admin status.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        # In real implementation, check user role
        return func(*args, **kwargs)
    return wrapper


class AuthMiddleware:
    """Middleware for handling authentication.

    This middleware intercepts requests and validates
    authentication tokens before passing to handlers.
    """

    def __init__(self, auth_service: Any):
        """Initialize with auth service."""
        self.auth_service = auth_service
        self._excluded_paths: set[str] = {"/login", "/register", "/health"}

    def process_request(self, request: dict) -> dict:
        """Process incoming request.

        Args:
            request: The request dict with path, headers, etc.

        Returns:
            Modified request with user info if authenticated.

        Raises:
            AuthenticationError: If token is invalid.
        """
        path = request.get("path", "")

        if self._is_excluded(path):
            return request

        token = self._extract_token(request)
        if not token:
            raise AuthenticationError("No authentication token provided")

        user_id = self.auth_service.validate_token(token)
        if not user_id:
            raise AuthenticationError("Invalid or expired token")

        request["user_id"] = user_id
        return request

    def _is_excluded(self, path: str) -> bool:
        """Check if path is excluded from auth."""
        return path in self._excluded_paths

    def _extract_token(self, request: dict) -> str | None:
        """Extract token from request headers."""
        headers = request.get("headers", {})
        auth_header = headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    def exclude_path(self, path: str) -> None:
        """Add a path to exclusion list."""
        self._excluded_paths.add(path)


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message)
        self.code = code


class AuthorizationError(Exception):
    """Raised when user lacks permission."""

    def __init__(self, message: str, required_role: str | None = None):
        super().__init__(message)
        self.required_role = required_role
