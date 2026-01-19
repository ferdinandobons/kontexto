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
    from kontexto.graph import CodeGraph
    from kontexto.store import Store
    from kontexto.search import SearchEngine

    kontexto_dir = sample_project / ".kontexto"
    kontexto_dir.mkdir()
    db_path = kontexto_dir / "index.db"

    # Build and save graph
    graph = CodeGraph(sample_project)
    graph.build()

    with Store(db_path) as store:
        store.save_graph(graph)

        # Build search index
        search_engine = SearchEngine(store)
        search_engine.build_index()

    return sample_project, db_path


@pytest.fixture
def project_with_inheritance(temp_dir):
    """Create a project with class inheritance for hierarchy testing."""
    src_dir = temp_dir / "src"
    src_dir.mkdir()

    # Create models with inheritance
    models_py = src_dir / "models.py"
    models_py.write_text('''"""Data models with inheritance."""


class BaseModel:
    """Base class for all models."""

    def save(self):
        """Save the model."""
        pass


class User(BaseModel):
    """User model."""

    def __init__(self, name: str):
        self.name = name


class Admin(User):
    """Admin user with extra permissions."""

    def grant_access(self):
        """Grant admin access."""
        pass


class Product(BaseModel):
    """Product model."""

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price


class Order(BaseModel):
    """Order model."""
    pass
''')

    (src_dir / "__init__.py").write_text("")

    return temp_dir


@pytest.fixture
def indexed_project_with_inheritance(project_with_inheritance):
    """Index the project with inheritance."""
    from kontexto.graph import CodeGraph
    from kontexto.store import Store
    from kontexto.search import SearchEngine

    kontexto_dir = project_with_inheritance / ".kontexto"
    kontexto_dir.mkdir()
    db_path = kontexto_dir / "index.db"

    graph = CodeGraph(project_with_inheritance)
    graph.build()

    with Store(db_path) as store:
        store.save_graph(graph)
        search_engine = SearchEngine(store)
        search_engine.build_index()

    return project_with_inheritance, db_path


@pytest.fixture
def multilang_project(temp_dir):
    """Create a multi-language project for testing."""
    # Create directory structure
    src_dir = temp_dir / "src"
    src_dir.mkdir()

    # Python file
    python_file = src_dir / "main.py"
    python_file.write_text('''"""Main Python module."""


def main():
    """Entry point."""
    print("Hello from Python!")


class PythonClass:
    """A Python class."""

    def method(self):
        """A method."""
        pass
''')

    # JavaScript file
    js_file = src_dir / "app.js"
    js_file.write_text("""/**
 * Main JavaScript module.
 */

function greet(name) {
    console.log("Hello, " + name);
}

class JsClass {
    constructor() {
        this.value = 0;
    }

    getValue() {
        return this.value;
    }
}

const arrowFunc = (x) => x * 2;
""")

    # TypeScript file
    ts_file = src_dir / "service.ts"
    ts_file.write_text("""/**
 * TypeScript service module.
 */

interface User {
    id: number;
    name: string;
}

class UserService {
    private users: User[] = [];

    addUser(user: User): void {
        this.users.push(user);
    }

    getUser(id: number): User | undefined {
        return this.users.find(u => u.id === id);
    }
}

type UserId = number;
""")

    # Go file
    go_file = src_dir / "main.go"
    go_file.write_text("""package main

import "fmt"

// User represents a user
type User struct {
    ID   int
    Name string
}

// Reader is a reader interface
type Reader interface {
    Read(p []byte) (n int, err error)
}

func main() {
    fmt.Println("Hello from Go!")
}

func (u *User) GetName() string {
    return u.Name
}
""")

    # Rust file
    rs_file = src_dir / "lib.rs"
    rs_file.write_text("""//! Rust library module.

/// A user struct
struct User {
    id: u64,
    name: String,
}

/// A color enum
enum Color {
    Red,
    Green,
    Blue,
}

/// The Drawable trait
trait Drawable {
    fn draw(&self);
}

impl User {
    fn new(id: u64, name: String) -> Self {
        User { id, name }
    }

    fn get_name(&self) -> &str {
        &self.name
    }
}
""")

    # Java file
    java_file = src_dir / "Main.java"
    java_file.write_text("""/**
 * Main Java class.
 */
public class Main {
    /**
     * Entry point.
     */
    public static void main(String[] args) {
        System.out.println("Hello from Java!");
    }

    public int add(int a, int b) {
        return a + b;
    }
}

interface Runnable {
    void run();
}

enum Status {
    ACTIVE,
    INACTIVE
}
""")

    return temp_dir


@pytest.fixture
def indexed_multilang_project(multilang_project):
    """Index the multi-language project."""
    from kontexto.graph import CodeGraph
    from kontexto.store import Store
    from kontexto.search import SearchEngine

    kontexto_dir = multilang_project / ".kontexto"
    kontexto_dir.mkdir()
    db_path = kontexto_dir / "index.db"

    graph = CodeGraph(multilang_project)
    graph.build()

    with Store(db_path) as store:
        store.save_graph(graph)
        search_engine = SearchEngine(store)
        search_engine.build_index()

    return multilang_project, db_path
