# Contexto

A CLI tool to explore Python codebases efficiently. Designed for LLMs and coding agents as a smarter alternative to `ls`, `grep`, and `find`.

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
contexto read src/api/users.py 10 50  # Read specific lines
```

## Commands

### `contexto index [path]`

Index a Python project and build the navigation graph.

```bash
contexto index                    # Index current directory
contexto index /path/to/project   # Index specific project
contexto index -i                 # Incremental update (faster)
```

Creates a `.contexto/index.db` database with:
- File and directory structure
- Classes, methods, and functions
- Signatures and docstrings
- Call relationships
- TF-IDF search index

### `contexto map [path]`

Show a compact map of the project structure.

```bash
$ contexto map

project: myapp
root: /path/to/myapp

src/                12 files, 8 classes, 45 functions
  api/              3 files
  services/         2 files
tests/              8 files
```

### `contexto expand <path>`

Expand a node to see its children.

```bash
$ contexto expand src/api/users.py

src/api/users.py (95 lines)

class UserController [10-89]
  """Handles user API endpoints"""
  - get_user [15-25]
  - create_user [27-45]
  - update_user [47-65]

function validate_user_id [91-95]
```

### `contexto inspect <entity>`

Show detailed info about an entity: signature, docstring, relationships.

```bash
$ contexto inspect src/api/users.py:UserController.get_user

method: get_user
file: src/api/users.py [15-25]
signature: def get_user(self, user_id: int) -> User
docstring: Retrieve user by ID from database.

calls:
  - src/services/user_service.py:UserService.find_by_id

called by:
  - src/api/routes.py:user_routes
```

### `contexto search <query>`

Search for entities by keyword (names, docstrings, signatures).

```bash
$ contexto search "authentication"

search: "authentication" (3 results)

1. src/api/auth.py:require_auth [function]
   def require_auth(func: Callable) -> Callable

2. src/middleware/auth.py:AuthMiddleware [class]
   """Authentication middleware for API requests"""

3. src/services/auth_service.py:authenticate [method]
   def authenticate(self, token: str) -> User
```

Options:
- `--limit, -l`: Maximum number of results (default: 10)

### `contexto read <file> [start] [end]`

Read source code from a file with line numbers.

```bash
$ contexto read src/api/users.py 15 25

file: src/api/users.py

  15 |     def get_user(self, user_id: int) -> User:
  16 |         """Retrieve user by ID from database."""
  17 |         user = self.user_service.find_by_id(user_id)
  18 |         if not user:
  19 |             raise NotFoundError(f"User {user_id} not found")
  20 |         return user
```

## Use with LLMs

Contexto is designed for coding agents like Claude Code. Instead of using `ls`, `grep`, and `find`:

```bash
# Before: multiple commands, lots of output
ls -la src/
grep -r "authenticate" src/
cat src/api/auth.py

# After: structured, compact output
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
| **contexto** | Compact, structured | Classes, functions, methods | Calls, called-by |

## How It Works

Contexto parses Python files using AST and builds a navigable graph:

```
Project Root
├── Directories
│   └── Files (.py)
│       ├── Classes
│       │   └── Methods
│       └── Functions
```

The graph is stored in SQLite with:
- **TF-IDF search index** for keyword search
- **Call relationships** tracking who calls what
- **Incremental updates** for large codebases

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
