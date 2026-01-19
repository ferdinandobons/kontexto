"""Tests for the AST parser."""

from kontexto.parser import PythonParser


class TestPythonParser:
    """Test suite for PythonParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()

    def test_parse_simple_function(self, temp_dir):
        """Test parsing a simple function."""
        code = '''def hello():
    """Say hello."""
    print("Hello!")
'''
        file_path = temp_dir / "simple.py"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "hello"
        assert entities[0].type == "function"
        assert entities[0].docstring == "Say hello."
        assert line_count == 3

    def test_parse_function_with_args(self, temp_dir):
        """Test parsing function with arguments and type hints."""
        code = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
        file_path = temp_dir / "args.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.name == "add"
        assert "a: int" in entity.signature
        assert "b: int" in entity.signature
        assert "-> int" in entity.signature

    def test_parse_async_function(self, temp_dir):
        """Test parsing async function."""
        code = '''
async def fetch_data(url: str) -> str:
    """Fetch data from URL."""
    return "data"
'''
        file_path = temp_dir / "async.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.name == "fetch_data"
        assert entity.signature.startswith("async def")

    def test_parse_class(self, temp_dir):
        """Test parsing a class with methods."""
        code = '''
class Calculator:
    """A calculator class."""

    def add(self, a, b):
        """Add two numbers."""
        return a + b

    def subtract(self, a, b):
        """Subtract b from a."""
        return a - b
'''
        file_path = temp_dir / "class.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # Should have class + 2 methods
        assert len(entities) == 3

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "Calculator"
        assert class_entity.docstring == "A calculator class."

        methods = [e for e in entities if e.type == "method"]
        assert len(methods) == 2
        assert {m.name for m in methods} == {"add", "subtract"}

    def test_parse_nested_class(self, temp_dir):
        """Test parsing nested classes."""
        code = '''
class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""

        def inner_method(self):
            pass
'''
        file_path = temp_dir / "nested.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # Outer class, Inner class, inner_method
        assert len(entities) == 3

        outer = next(e for e in entities if e.name == "Outer")
        inner = next(e for e in entities if e.name == "Inner")

        assert outer.type == "class"
        assert inner.type == "class"
        assert inner.parent_id is not None

    def test_parse_function_calls(self, temp_dir):
        """Test extracting function calls from a function body."""
        code = """
def process():
    result = helper()
    print(result)
    save_data(result)
"""
        file_path = temp_dir / "calls.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        entity = entities[0]
        assert "helper" in entity.calls
        assert "print" in entity.calls
        assert "save_data" in entity.calls

    def test_parse_positional_only_args(self, temp_dir):
        """Test parsing function with positional-only arguments."""
        code = """
def func(a, b, /, c, d):
    pass
"""
        file_path = temp_dir / "posonly.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert "/" in entities[0].signature

    def test_parse_keyword_only_args(self, temp_dir):
        """Test parsing function with keyword-only arguments."""
        code = """
def func(a, *, b, c):
    pass
"""
        file_path = temp_dir / "kwonly.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        # The bare * should be in the signature
        assert "*" in entities[0].signature

    def test_parse_default_values(self, temp_dir):
        """Test parsing function with default values."""
        code = """
def func(a, b=10, c="hello"):
    pass
"""
        file_path = temp_dir / "defaults.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        sig = entities[0].signature
        assert "b=10" in sig
        assert 'c="hello"' in sig or "c='hello'" in sig

    def test_parse_syntax_error(self, temp_dir):
        """Test handling of syntax errors."""
        code = """
def broken(
    # Missing closing paren
"""
        file_path = temp_dir / "broken.py"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        assert entities == []
        assert line_count is None

    def test_parse_encoding_error(self, temp_dir):
        """Test handling of encoding errors."""
        file_path = temp_dir / "binary.py"
        # Write invalid UTF-8 bytes
        file_path.write_bytes(b"\xff\xfe invalid utf-8")

        entities, line_count = self.parser.parse_file(file_path)

        assert entities == []
        assert line_count is None

    def test_parse_class_inheritance(self, temp_dir):
        """Test parsing class with inheritance."""
        code = '''
class Child(Parent, Mixin):
    """A child class."""
    pass
'''
        file_path = temp_dir / "inheritance.py"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        entity = entities[0]
        assert "Parent" in entity.signature
        assert "Mixin" in entity.signature
