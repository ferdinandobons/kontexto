"""Multi-language parser support for Kontexto.

Supported languages:
- Python (.py, .pyi)
- JavaScript (.js, .jsx, .mjs)
- TypeScript (.ts, .tsx)
- Go (.go)
- Rust (.rs)
- Java (.java)
"""

from kontexto.parsers.base import (
    BaseParser,
    CodeEntity,
    LanguageConfig,
    DEFAULT_EXCLUDE_PATTERNS,
)
from kontexto.parsers.registry import ParserRegistry, get_registry

__all__ = [
    "BaseParser",
    "CodeEntity",
    "LanguageConfig",
    "ParserRegistry",
    "get_registry",
    "DEFAULT_EXCLUDE_PATTERNS",
]
