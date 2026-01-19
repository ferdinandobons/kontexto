"""Multi-language parser support for Contexto.

Supported languages:
- Python (.py, .pyi)
- JavaScript (.js, .jsx, .mjs)
- TypeScript (.ts, .tsx)
- Go (.go)
- Rust (.rs)
- Java (.java)
"""

from contexto.parsers.base import (
    BaseParser,
    CodeEntity,
    LanguageConfig,
    DEFAULT_EXCLUDE_PATTERNS,
)
from contexto.parsers.registry import ParserRegistry, get_registry

__all__ = [
    "BaseParser",
    "CodeEntity",
    "LanguageConfig",
    "ParserRegistry",
    "get_registry",
    "DEFAULT_EXCLUDE_PATTERNS",
]
