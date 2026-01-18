"""Application settings."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DatabaseSettings:
    """Database configuration."""

    path: Path
    pool_size: int = 10
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        """Load settings from environment."""
        return cls(
            path=Path(os.getenv("DB_PATH", "app.db")),
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            timeout=int(os.getenv("DB_TIMEOUT", "30")),
        )


@dataclass
class AuthSettings:
    """Authentication configuration."""

    secret_key: str
    token_expiry_hours: int = 24
    reset_token_expiry_hours: int = 24
    max_login_attempts: int = 5

    @classmethod
    def from_env(cls) -> "AuthSettings":
        """Load settings from environment."""
        secret = os.getenv("SECRET_KEY")
        if not secret:
            raise ValueError("SECRET_KEY environment variable required")
        return cls(
            secret_key=secret,
            token_expiry_hours=int(os.getenv("TOKEN_EXPIRY_HOURS", "24")),
            reset_token_expiry_hours=int(os.getenv("RESET_TOKEN_EXPIRY_HOURS", "24")),
            max_login_attempts=int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
        )


@dataclass
class AppSettings:
    """Main application settings."""

    debug: bool = False
    log_level: str = "INFO"
    database: Optional[DatabaseSettings] = None
    auth: Optional[AuthSettings] = None

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Load all settings from environment."""
        return cls(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database=DatabaseSettings.from_env(),
        )


class Settings:
    """Singleton settings manager."""

    _instance: Optional["Settings"] = None
    _settings: Optional[AppSettings] = None

    def __new__(cls) -> "Settings":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> AppSettings:
        """Load and cache settings."""
        if self._settings is None:
            self._settings = AppSettings.from_env()
        return self._settings

    def reload(self) -> AppSettings:
        """Force reload settings."""
        self._settings = None
        return self.load()

    @property
    def debug(self) -> bool:
        """Get debug mode."""
        return self.load().debug

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self.load().log_level


def get_settings() -> AppSettings:
    """Get application settings.

    Returns:
        Loaded AppSettings instance.
    """
    return Settings().load()
