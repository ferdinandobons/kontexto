"""Security utilities."""

import hashlib
import hmac
import secrets
from base64 import b64encode, b64decode
from typing import Optional


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash a password securely.

    Args:
        password: Plain text password.
        salt: Optional salt (generated if not provided).

    Returns:
        Hashed password with salt prefix.
    """
    if salt is None:
        salt = secrets.token_hex(16)

    # Use PBKDF2 with SHA256
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        iterations=100000
    )
    return f"{salt}${b64encode(dk).decode()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash.

    Args:
        password: Plain text password to verify.
        hashed: Previously hashed password.

    Returns:
        True if password matches.
    """
    try:
        salt, hash_part = hashed.split("$", 1)
        expected = hash_password(password, salt)
        return hmac.compare_digest(expected, hashed)
    except (ValueError, AttributeError):
        return False


def generate_token(user_id: int, expiry_hours: int = 24) -> str:
    """Generate an authentication token.

    Args:
        user_id: User ID to encode.
        expiry_hours: Token validity in hours.

    Returns:
        JWT-like token string.
    """
    # Simplified token format for testing
    # In production, use proper JWT with signing
    random_part = secrets.token_hex(16)
    return f"token.{user_id}.{random_part}"


def validate_token(token: str) -> Optional[int]:
    """Validate a token and extract user ID.

    Args:
        token: Token to validate.

    Returns:
        User ID if valid, None otherwise.
    """
    try:
        parts = token.split(".")
        if len(parts) == 3 and parts[0] == "token":
            return int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


def generate_reset_token(user_id: int) -> str:
    """Generate a password reset token.

    Args:
        user_id: User requesting reset.

    Returns:
        Secure reset token.
    """
    random_part = secrets.token_urlsafe(32)
    return f"reset_{user_id}_{random_part}"


def generate_api_key() -> str:
    """Generate a secure API key.

    Returns:
        Random API key string.
    """
    return f"sk_{secrets.token_urlsafe(32)}"


class Encryptor:
    """Simple encryption utility using XOR cipher.

    Note: For demo purposes only. Use proper encryption
    (AES via cryptography library) in production.
    """

    def __init__(self, key: str):
        """Initialize with encryption key."""
        self.key = key.encode()

    def encrypt(self, data: str) -> str:
        """Encrypt data.

        Args:
            data: Plain text to encrypt.

        Returns:
            Base64 encoded encrypted data.
        """
        encrypted = bytes(
            b ^ self.key[i % len(self.key)]
            for i, b in enumerate(data.encode())
        )
        return b64encode(encrypted).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt data.

        Args:
            encrypted: Base64 encoded encrypted data.

        Returns:
            Decrypted plain text.
        """
        data = b64decode(encrypted.encode())
        decrypted = bytes(
            b ^ self.key[i % len(self.key)]
            for i, b in enumerate(data)
        )
        return decrypted.decode()


def sanitize_input(value: str, max_length: int = 1000) -> str:
    """Sanitize user input.

    Args:
        value: Input string.
        max_length: Maximum allowed length.

    Returns:
        Sanitized string.
    """
    # Remove null bytes
    value = value.replace("\x00", "")

    # Truncate if too long
    if len(value) > max_length:
        value = value[:max_length]

    # Remove potentially dangerous characters for SQL
    # (Note: use parameterized queries instead!)
    dangerous = ["--", ";--", "/*", "*/", "@@"]
    for pattern in dangerous:
        value = value.replace(pattern, "")

    return value.strip()
