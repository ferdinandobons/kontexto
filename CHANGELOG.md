# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Incremental indexing with `--incremental` / `-i` flag - only re-indexes changed files
- `called_by` reverse lookup in `inspect()` tool - shows which entities call the inspected entity
- Support for nested classes in AST parsing
- Full function signature parsing including:
  - Positional-only arguments (`/` separator)
  - Keyword-only arguments (`*` separator)
  - Default values for all argument types
  - `async def` prefix for async functions

### Fixed
- Resource leak: Store now implements context manager protocol for safe cleanup
- Path traversal vulnerability in `read()` tool - prevents accessing files outside project
- Potential division by zero in search score normalization
- File nodes now correctly show total line count in `line_end`
- SQLite transaction safety in `save_graph()` with explicit BEGIN/COMMIT/ROLLBACK
- MCP server now properly closes database connection on shutdown

### Changed
- File hashing switched from MD5 to SHA256 for better collision resistance
- Parser now logs warnings for syntax/encoding errors instead of silently ignoring

### Known Limitations
- Python files only (no other language support yet)

## [0.1.0] - 2025-01-18

### Added
- Initial release of Contexto
- `contexto index [path]` command to build codebase graph from Python files
- `contexto serve [path]` command to start MCP server for LLM integration
- MCP tools for codebase navigation:
  - `map()` - Returns compact project structure map
  - `expand(path)` - Expands nodes to show children (directories, files, classes, methods)
  - `inspect(path)` - Shows detailed entity info (signature, docstring, calls)
  - `read(path, start_line?, end_line?)` - Reads source code with line numbers
  - `search(query, limit?)` - TF-IDF based search across names, docstrings, signatures
- CLI debug commands: `map`, `expand`, `search`
- AST-based Python parser for extracting code structure
- SQLite persistence layer with performance indexes
- TF-IDF search engine with camelCase/snake_case identifier splitting
- XML output format optimized for LLM consumption
