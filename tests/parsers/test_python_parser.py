"""Tests for the tree-sitter Python parser."""

from pathlib import Path

from kontexto.parsers.python_parser import PythonParser


class TestPythonParser:
    """Test suite for PythonParser."""

    def setup_method(self) -> None:
        self.parser = PythonParser()

    def test_config(self) -> None:
        """Test parser configuration."""
        assert self.parser.config.name == "python"
        assert ".py" in self.parser.config.extensions
        assert ".pyi" in self.parser.config.extensions

    def test_supports_file(self, tmp_path: Path) -> None:
        """Test file support detection."""
        py_file = tmp_path / "test.py"
        py_file.touch()
        js_file = tmp_path / "test.js"
        js_file.touch()

        assert self.parser.supports_file(py_file)
        assert not self.parser.supports_file(js_file)

    def test_parse_simple_function(self, tmp_path: Path) -> None:
        """Test parsing a simple function."""
        code = '''def hello():
    """Say hello."""
    print("Hello!")
'''
        file_path = tmp_path / "simple.py"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "hello"
        assert entities[0].type == "function"
        assert entities[0].docstring == "Say hello."
        assert entities[0].language == "python"
        assert line_count == 4

    def test_parse_function_with_args(self, tmp_path: Path) -> None:
        """Test parsing a function with arguments."""
        code = '''def greet(name: str, greeting: str = "Hello") -> str:
    """Greet someone."""
    return f"{greeting}, {name}!"
'''
        file_path = tmp_path / "greet.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "greet"
        assert "name: str" in entities[0].signature
        assert "greeting: str" in entities[0].signature

    def test_parse_async_function(self, tmp_path: Path) -> None:
        """Test parsing an async function."""
        code = '''async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    return {}
'''
        file_path = tmp_path / "async.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "fetch_data"
        assert "async def" in entities[0].signature

    def test_parse_class(self, tmp_path: Path) -> None:
        """Test parsing a class."""
        code = '''class Calculator:
    """A calculator class."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract two numbers."""
        return a - b
'''
        file_path = tmp_path / "calc.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 3  # class + 2 methods

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "Calculator"
        assert class_entity.docstring == "A calculator class."

        methods = [e for e in entities if e.type == "method"]
        assert len(methods) == 2
        assert {m.name for m in methods} == {"add", "subtract"}

    def test_parse_class_with_inheritance(self, tmp_path: Path) -> None:
        """Test parsing a class with inheritance."""
        code = '''class Child(Parent, Mixin):
    """A child class."""
    pass
'''
        file_path = tmp_path / "child.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "Child"
        assert "Parent" in entities[0].base_classes
        assert "Mixin" in entities[0].base_classes

    def test_parse_nested_class(self, tmp_path: Path) -> None:
        """Test parsing nested classes."""
        code = '''class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""

        def inner_method(self):
            pass
'''
        file_path = tmp_path / "nested.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 3  # Outer + Inner + inner_method

        outer = next(e for e in entities if e.name == "Outer")
        inner = next(e for e in entities if e.name == "Inner")
        method = next(e for e in entities if e.name == "inner_method")

        assert outer.type == "class"
        assert inner.type == "class"
        assert inner.parent_id is not None
        assert method.parent_id is not None

    def test_extract_calls(self, tmp_path: Path) -> None:
        """Test extraction of function calls."""
        code = """def process():
    result = helper()
    print(result)
    return save(result)
"""
        file_path = tmp_path / "calls.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        calls = entities[0].calls
        assert "helper" in calls
        assert "print" in calls
        assert "save" in calls

    def test_parse_syntax_error(self, tmp_path: Path) -> None:
        """Test handling of syntax errors."""
        code = """def broken(
    # Missing closing parenthesis
"""
        file_path = tmp_path / "broken.py"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        # Should return empty or partial results, not crash
        assert isinstance(entities, list)

    def test_parse_encoding_error(self, tmp_path: Path) -> None:
        """Test handling of encoding errors."""
        file_path = tmp_path / "binary.py"
        file_path.write_bytes(b"\x80\x81\x82")

        entities, line_count = self.parser.parse_file(file_path)

        assert entities == []
        assert line_count is None

    def test_entity_ids(self, tmp_path: Path) -> None:
        """Test that entity IDs are correctly formatted."""
        code = """class MyClass:
    def my_method(self):
        pass
"""
        file_path = tmp_path / "ids.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        class_entity = next(e for e in entities if e.type == "class")
        method_entity = next(e for e in entities if e.type == "method")

        assert "MyClass" in class_entity.id
        assert "my_method" in method_entity.id
        assert method_entity.parent_id is not None
