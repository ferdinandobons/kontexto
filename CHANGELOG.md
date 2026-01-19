# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-19

### Added

- **Multi-language support** via tree-sitter:
  - Python (`.py`)
  - JavaScript/TypeScript (`.js`, `.jsx`, `.mjs`, `.ts`, `.tsx`)
  - Go (`.go`)
  - Rust (`.rs`)
  - Java (`.java`)

- **CLI commands** for codebase exploration:
  - `kontexto index` - Index a project with incremental update support (`-i`)
  - `kontexto map` - Show project structure with statistics
  - `kontexto expand` - Expand nodes to see children
  - `kontexto inspect` - Detailed entity inspection with call relationships
  - `kontexto search` - TF-IDF based keyword search
  - `kontexto hierarchy` - Find all subclasses of a base class
  - `kontexto read` - Read source code with optional line ranges

- **JSON output** for all commands (except `read`) for easy LLM parsing

- **AST parsing** with tree-sitter to extract:
  - Functions, classes, and methods
  - Signatures with full argument support (positional-only, keyword-only, defaults)
  - Docstrings
  - Function calls
  - Class inheritance (base classes)

- **SQLite storage** with:
  - WAL mode for concurrent access
  - Optimized indexes for fast queries
  - File hash tracking for incremental updates

- **TF-IDF search engine** with:
  - Tokenization with camelCase/snake_case splitting
  - Stop word filtering
  - Result caching
  - Incremental index updates

- **Performance optimizations**:
  - Batch database inserts
  - Pre-compiled regex patterns
  - Memory-mapped I/O
  - Search result caching

[0.1.0]: https://github.com/ferdinandobons/kontexto/releases/tag/v0.1.0
