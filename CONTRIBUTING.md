# Contributing to Kontexto

Thank you for your interest in contributing to Kontexto! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check the existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title** describing the issue
- **Steps to reproduce** the behavior
- **Expected behavior** vs. actual behavior
- **Environment details** (OS, Python version, Kontexto version)
- **Error messages** or logs if applicable

### Suggesting Features

Feature suggestions are welcome! Please:

1. Check if the feature has already been suggested
2. Open an issue with the `enhancement` label
3. Describe the feature and its use case
4. Explain why it would be valuable

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Install development dependencies**: `pip install -e ".[dev]"`
3. **Make your changes** following the coding standards below
4. **Add tests** for new functionality
5. **Run the test suite**: `pytest`
6. **Run linting**: `ruff check src tests`
7. **Run type checking**: `mypy src`
8. **Update documentation** if needed
9. **Submit your PR** with a clear description

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/kontexto.git
cd kontexto

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src tests

# Run type checking
mypy src
```

## Coding Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use [type hints](https://docs.python.org/3/library/typing.html)
- Maximum line length: 100 characters
- Use descriptive variable names

### Docstrings

Use Google-style docstrings:

```python
def function_name(arg1: str, arg2: int) -> bool:
    """Short description of function.

    Longer description if needed.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When something is wrong.
    """
```

### Commit Messages

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep the first line under 72 characters
- Reference issues when relevant

Examples:
- `Add search functionality for class methods`
- `Fix edge case in AST parsing for async functions`
- `Update README with MCP configuration examples`

### Testing

- Write tests for all new functionality
- Maintain test coverage above 80%
- Use descriptive test names: `test_search_returns_empty_list_for_no_matches`

## Project Structure

```
kontexto/
├── src/kontexto/       # Main package
│   ├── __init__.py
│   ├── cli.py          # CLI commands
│   ├── parser.py       # AST parsing
│   ├── graph.py        # Graph construction
│   ├── store.py        # SQLite storage
│   ├── search.py       # Search engine
│   ├── mcp_server.py   # MCP server
│   └── output.py       # XML formatters
├── tests/              # Test suite
├── pyproject.toml      # Project configuration
└── README.md           # Documentation
```

## Questions?

If you have questions, feel free to:

- Open a [Discussion](https://github.com/YOUR_USERNAME/kontexto/discussions)
- Ask in an issue with the `question` label

Thank you for contributing!
