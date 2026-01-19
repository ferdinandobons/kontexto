"""Parser registry for multi-language support."""

from pathlib import Path
from typing import Optional

from contexto.parsers.base import BaseParser


class ParserRegistry:
    """Registry for language parsers with automatic file-to-parser matching.

    This is a singleton that lazily initializes parsers to avoid import
    overhead when not all languages are needed.
    """

    _instance: Optional["ParserRegistry"] = None
    _initialized: bool = False

    def __new__(cls) -> "ParserRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._parsers: dict[str, BaseParser] = {}
        self._extension_map: dict[str, str] = {}
        self._initialize_parsers()
        ParserRegistry._initialized = True

    def _initialize_parsers(self) -> None:
        """Initialize all available parsers."""
        # Import parsers here to avoid circular imports
        from contexto.parsers.python_parser import PythonParser
        from contexto.parsers.javascript_parser import JavaScriptParser
        from contexto.parsers.go_parser import GoParser
        from contexto.parsers.rust_parser import RustParser
        from contexto.parsers.java_parser import JavaParser

        parsers = [
            PythonParser(),
            JavaScriptParser(),
            GoParser(),
            RustParser(),
            JavaParser(),
        ]

        for parser in parsers:
            self._register_parser(parser)

    def _register_parser(self, parser: BaseParser) -> None:
        """Register a parser and map its extensions."""
        self._parsers[parser.config.name] = parser
        for ext in parser.config.extensions:
            self._extension_map[ext.lower()] = parser.config.name

    def get_parser_for_file(self, file_path: Path) -> Optional[BaseParser]:
        """Get the appropriate parser for a file based on its extension.

        Args:
            file_path: Path to the file.

        Returns:
            The parser for this file type, or None if unsupported.
        """
        ext = file_path.suffix.lower()
        lang = self._extension_map.get(ext)
        return self._parsers.get(lang) if lang else None

    def get_parser_by_name(self, name: str) -> Optional[BaseParser]:
        """Get a parser by language name.

        Args:
            name: Language name (e.g., "python", "javascript").

        Returns:
            The parser for this language, or None if not found.
        """
        return self._parsers.get(name.lower())

    def get_supported_extensions(self) -> set[str]:
        """Get all supported file extensions."""
        return set(self._extension_map.keys())

    def get_supported_languages(self) -> list[str]:
        """Get all supported language names."""
        return list(self._parsers.keys())

    def is_supported_file(self, file_path: Path) -> bool:
        """Check if a file is supported by any parser."""
        return file_path.suffix.lower() in self._extension_map


def get_registry() -> ParserRegistry:
    """Get the global parser registry singleton."""
    return ParserRegistry()
