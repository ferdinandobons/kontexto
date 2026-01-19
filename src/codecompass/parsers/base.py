"""Base classes and types for language parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LanguageConfig:
    """Configuration for a programming language parser."""

    name: str  # "python", "javascript", etc.
    extensions: tuple[str, ...]  # (".py",), (".js", ".mjs"), etc.
    exclude_patterns: tuple[str, ...] = ()  # Language-specific excludes


@dataclass
class CodeEntity:
    """Represents a code entity (function, class, method, etc.)."""

    id: str
    name: str
    type: str  # 'function', 'class', 'method', 'constructor', 'interface', 'struct', 'trait', 'impl', 'enum', 'type'
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_id: Optional[str] = None
    calls: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    language: str = "unknown"


class BaseParser(ABC):
    """Abstract base class for all language parsers."""

    @property
    @abstractmethod
    def config(self) -> LanguageConfig:
        """Return language configuration."""
        pass

    @abstractmethod
    def parse_file(self, file_path: Path) -> tuple[list[CodeEntity], Optional[int]]:
        """Parse a file and extract all code entities.

        Args:
            file_path: Path to the source file to parse.

        Returns:
            Tuple of (list of extracted entities, total line count or None on error).
        """
        pass

    def supports_file(self, file_path: Path) -> bool:
        """Check if this parser supports the given file based on extension."""
        return file_path.suffix.lower() in self.config.extensions


# Default exclude patterns shared across all languages
DEFAULT_EXCLUDE_PATTERNS = frozenset(
    {
        # Version control
        ".git",
        ".svn",
        ".hg",
        # Python
        "__pycache__",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        "*.egg-info",
        ".eggs",
        # JavaScript/TypeScript
        "node_modules",
        ".npm",
        "bower_components",
        # Build outputs
        "dist",
        "build",
        "out",
        "_build",
        # Go
        "vendor",
        # Rust
        "target",
        # Java
        ".gradle",
        ".mvn",
        # IDE
        ".idea",
        ".vscode",
        # Other
        ".tox",
        ".nox",
        "coverage",
        ".coverage",
        "htmlcov",
    }
)
