# Contexto

A CLI tool to explore codebases efficiently. Designed for LLMs and coding agents as a smarter alternative to `ls`, `grep`, and `find`.

**All output is JSON** for easy parsing by LLMs and programmatic consumption.

## Supported Languages

| Language | Extensions | Entities Extracted |
|----------|------------|-------------------|
| Python | `.py` | functions, classes, methods |
| JavaScript | `.js`, `.jsx`, `.mjs` | functions, classes, methods, arrow functions |
| TypeScript | `.ts`, `.tsx` | functions, classes, methods, interfaces, types |
| Go | `.go` | functions, methods, structs, interfaces |
| Rust | `.rs` | functions, structs, enums, traits, impl blocks, methods |
| Java | `.java` | classes, interfaces, enums, methods, constructors |

All parsers use [tree-sitter](https://tree-sitter.github.io/) for fast, accurate AST-based parsing.

## Installation

```bash
pip install contexto
```

## Quick Start

```bash
# 1. Index your project
cd /path/to/your/project
contexto index

# 2. Explore the codebase
contexto map                          # See project structure
contexto expand src/api               # Expand a directory
contexto search "authentication"      # Search for code
contexto inspect src/api:UserController   # Inspect entity details
contexto hierarchy BaseModel          # Find all subclasses
contexto read src/api/users.py 10 50  # Read specific lines
```

## Commands

### `contexto index [path]`

Index a project and build the navigation graph. Automatically detects and parses all supported languages.

```bash
contexto index                    # Index current directory
contexto index /path/to/project   # Index specific project
contexto index -i                 # Incremental update (faster)
```

Creates a `.contexto/index.db` database with:
- File and directory structure
- Classes, methods, functions (and language-specific entities)
- Signatures and docstrings
- Call relationships
- Class inheritance (base classes)
- TF-IDF search index
- Language metadata for each entity

### `contexto map [path]`

Show a compact map of the project structure.

```bash
$ contexto map
```

```json
{
  "command": "map",
  "project": "myapp",
  "root": "/path/to/myapp",
  "stats": {"files": 20, "classes": 8, "functions": 45, "methods": 32},
  "children": [
    {"id": "src", "stats": {"files": 12, "classes": 8, "functions": 45}},
    {"id": "tests", "stats": {"files": 8, "classes": 0, "functions": 24}}
  ]
}
```

### `contexto expand <path>`

Expand a node to see its children.

```bash
$ contexto expand src/api/users.py
```

```json
{
  "command": "expand",
  "node": {
    "id": "src/api/users.py",
    "name": "users.py",
    "type": "file",
    "line_end": 95
  },
  "children": [
    {
      "id": "src/api/users.py:UserController",
      "name": "UserController",
      "type": "class",
      "line_start": 10,
      "line_end": 89,
      "signature": "class UserController",
      "docstring": "Handles user API endpoints",
      "base_classes": ["BaseController"]
    }
  ]
}
```

### `contexto inspect <entity>`

Show detailed info about an entity: signature, docstring, relationships.

```bash
$ contexto inspect src/api/users.py:UserController.get_user
```

```json
{
  "command": "inspect",
  "node": {
    "id": "src/api/users.py:UserController.get_user",
    "name": "get_user",
    "type": "method",
    "file_path": "src/api/users.py",
    "line_start": 15,
    "line_end": 25,
    "signature": "def get_user(self, user_id: int) -> User",
    "docstring": "Retrieve user by ID from database."
  },
  "calls": ["find_by_id"],
  "called_by": ["src/api/routes.py:user_routes"]
}
```

### `contexto search <query>`

Search for entities by keyword (names, docstrings, signatures).

```bash
$ contexto search "authentication"
```

```json
{
  "command": "search",
  "query": "authentication",
  "count": 3,
  "results": [
    {
      "node": {
        "id": "src/api/auth.py:require_auth",
        "name": "require_auth",
        "type": "function",
        "signature": "def require_auth(func: Callable) -> Callable"
      },
      "score": 0.8521
    }
  ]
}
```

Options:
- `--limit, -l`: Maximum number of results (default: 10)

### `contexto hierarchy <base_class>`

Find all classes that inherit from a given base class.

```bash
$ contexto hierarchy BaseModel
```

```json
{
  "command": "hierarchy",
  "base_class": "BaseModel",
  "count": 5,
  "subclasses": [
    {
      "id": "src/models/user.py:User",
      "name": "User",
      "type": "class",
      "base_classes": ["BaseModel"],
      "signature": "class User(BaseModel)"
    },
    {
      "id": "src/models/product.py:Product",
      "name": "Product",
      "type": "class",
      "base_classes": ["BaseModel"],
      "signature": "class Product(BaseModel)"
    }
  ]
}
```

### `contexto read <file> [start] [end]`

Read source code from a file. Outputs raw code (not JSON).

```bash
$ contexto read src/api/users.py 15 20
```

```python
    def get_user(self, user_id: int) -> User:
        """Retrieve user by ID from database."""
        user = self.user_service.find_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user
```

Use line ranges from `expand` or `inspect` to read specific functions.

## Use with LLMs

Contexto is designed for coding agents like Claude Code. Instead of using `ls`, `grep`, and `find`:

```bash
# Before: multiple commands, unstructured output
ls -la src/
grep -r "authenticate" src/
cat src/api/auth.py

# After: JSON output, easy to parse
contexto map
contexto search "authenticate"
contexto expand src/api/auth.py
```

### Benefits for LLMs

| Tool | Output | Structure | Relationships |
|------|--------|-----------|---------------|
| `ls` | File names only | None | None |
| `grep` | Matching lines | None | None |
| `find` | File paths | None | None |
| **contexto** | Structured JSON | Classes, functions, methods | Calls, called-by, inheritance |

### Features

- **JSON output** - All commands return structured JSON for easy parsing
- **Class hierarchy** - Track inheritance with `base_classes` field and `hierarchy` command
- **Search caching** - Repeated searches are cached for faster response
- **Incremental indexing** - Only changed files are re-indexed, with incremental search index updates

## How It Works

Contexto uses tree-sitter to parse source files and builds a navigable graph:

```
Project Root
├── Directories
│   └── Files (.py, .js, .ts, .go, .rs, .java)
│       ├── Classes/Structs/Traits (with base_classes)
│       │   └── Methods
│       ├── Functions
│       ├── Interfaces
│       └── Enums
```

The graph is stored in SQLite with:
- **TF-IDF search index** for keyword search
- **Call relationships** tracking who calls what
- **Class inheritance** tracking base classes
- **Language metadata** for each entity
- **Incremental updates** for large codebases (both graph and search index)

### Architecture

```
┌─────────────────┐
│  CLI Commands   │
└────────┬────────┘
         │
┌────────▼────────┐
│   CodeGraph     │
└────────┬────────┘
         │
┌────────▼────────┐
│ ParserRegistry  │
└────────┬────────┘
         │
    ┌────┴────┬────────┬────────┬────────┐
    ▼         ▼        ▼        ▼        ▼
┌───────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Python │ │  JS  │ │  Go  │ │ Rust │ │ Java │
│Parser │ │Parser│ │Parser│ │Parser│ │Parser│
└───┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
    │        │        │        │        │
    └────────┴────────┴────────┴────────┘
                      │
              ┌───────▼───────┐
              │  tree-sitter  │
              └───────────────┘
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/
```

## License

MIT
