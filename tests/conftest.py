"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_project(temp_dir):
    """Create a sample Python project for testing."""
    # Create directory structure
    src_dir = temp_dir / "src"
    src_dir.mkdir()

    utils_dir = src_dir / "utils"
    utils_dir.mkdir()

    # Create main.py
    main_py = src_dir / "main.py"
    main_py.write_text('''"""Main module."""


def main():
    """Entry point."""
    print("Hello, World!")
    helper()


def helper():
    """Helper function."""
    return 42
''')

    # Create utils/helpers.py
    helpers_py = utils_dir / "helpers.py"
    helpers_py.write_text('''"""Utility helpers."""


class Calculator:
    """A simple calculator class."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b


def format_output(value):
    """Format a value for output."""
    return str(value)


async def async_fetch(url: str) -> str:
    """Fetch data asynchronously."""
    return f"Data from {url}"
''')

    # Create utils/__init__.py
    (utils_dir / "__init__.py").write_text('"""Utils package."""\n')

    # Create src/__init__.py
    (src_dir / "__init__.py").write_text('"""Source package."""\n')

    return temp_dir


@pytest.fixture
def indexed_project(sample_project):
    """Create and index a sample project."""
    from contexto.graph import CodeGraph
    from contexto.store import Store
    from contexto.search import SearchEngine

    contexto_dir = sample_project / ".contexto"
    contexto_dir.mkdir()
    db_path = contexto_dir / "index.db"

    # Build and save graph
    graph = CodeGraph(sample_project)
    graph.build()

    with Store(db_path) as store:
        store.save_graph(graph)

        # Build search index
        search_engine = SearchEngine(store)
        search_engine.build_index()

    return sample_project, db_path
