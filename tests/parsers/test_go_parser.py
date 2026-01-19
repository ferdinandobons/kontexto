"""Tests for the tree-sitter Go parser."""

from pathlib import Path

from kontexto.parsers.go_parser import GoParser


class TestGoParser:
    """Test suite for GoParser."""

    def setup_method(self) -> None:
        self.parser = GoParser()

    def test_config(self) -> None:
        """Test parser configuration."""
        assert self.parser.config.name == "go"
        assert ".go" in self.parser.config.extensions

    def test_supports_file(self, tmp_path: Path) -> None:
        """Test file support detection."""
        go_file = tmp_path / "main.go"
        go_file.touch()
        py_file = tmp_path / "main.py"
        py_file.touch()

        assert self.parser.supports_file(go_file)
        assert not self.parser.supports_file(py_file)

    def test_parse_function(self, tmp_path: Path) -> None:
        """Test parsing a function declaration."""
        code = """package main

// SayHello prints a greeting
func SayHello(name string) {
    fmt.Println("Hello, " + name)
}
"""
        file_path = tmp_path / "hello.go"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "SayHello"
        assert entities[0].type == "function"
        assert entities[0].language == "go"
        assert "SayHello prints a greeting" in (entities[0].docstring or "")

    def test_parse_function_with_return(self, tmp_path: Path) -> None:
        """Test parsing a function with return type."""
        code = """package main

func Add(a, b int) int {
    return a + b
}
"""
        file_path = tmp_path / "math.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "Add"
        assert "int" in entities[0].signature

    def test_parse_struct(self, tmp_path: Path) -> None:
        """Test parsing a struct definition."""
        code = """package main

// User represents a user in the system
type User struct {
    ID   int
    Name string
}
"""
        file_path = tmp_path / "user.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "User"
        assert entities[0].type == "struct"
        assert "type User struct" in entities[0].signature

    def test_parse_interface(self, tmp_path: Path) -> None:
        """Test parsing an interface definition."""
        code = """package main

type Reader interface {
    Read(p []byte) (n int, err error)
}
"""
        file_path = tmp_path / "reader.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "Reader"
        assert entities[0].type == "interface"

    def test_parse_method(self, tmp_path: Path) -> None:
        """Test parsing a method with receiver."""
        code = """package main

type User struct {
    Name string
}

func (u *User) GetName() string {
    return u.Name
}
"""
        file_path = tmp_path / "user.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # Should have struct + method
        assert len(entities) == 2

        struct_entity = next(e for e in entities if e.type == "struct")
        assert struct_entity.name == "User"

        method_entity = next(e for e in entities if e.type == "method")
        assert method_entity.name == "GetName"
        assert "User" in method_entity.parent_id

    def test_parse_multiple_functions(self, tmp_path: Path) -> None:
        """Test parsing multiple functions."""
        code = """package main

func First() {}
func Second() {}
func Third() {}
"""
        file_path = tmp_path / "funcs.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 3
        names = [e.name for e in entities]
        assert "First" in names
        assert "Second" in names
        assert "Third" in names

    def test_extract_calls(self, tmp_path: Path) -> None:
        """Test extraction of function calls."""
        code = """package main

func process() {
    result := helper()
    fmt.Println(result)
    save(result)
}
"""
        file_path = tmp_path / "calls.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        calls = entities[0].calls
        assert "helper" in calls
        assert "save" in calls

    def test_parse_method_on_value_receiver(self, tmp_path: Path) -> None:
        """Test parsing a method with value receiver."""
        code = """package main

type Point struct {
    X, Y int
}

func (p Point) Distance() float64 {
    return 0.0
}
"""
        file_path = tmp_path / "point.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        method = next(e for e in entities if e.type == "method")
        assert method.name == "Distance"
        assert "Point" in method.parent_id

    def test_parse_exported_vs_unexported(self, tmp_path: Path) -> None:
        """Test parsing exported and unexported functions."""
        code = """package main

func PublicFunc() {}
func privateFunc() {}
"""
        file_path = tmp_path / "funcs.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 2
        names = [e.name for e in entities]
        assert "PublicFunc" in names
        assert "privateFunc" in names

    def test_parse_multiple_return_values(self, tmp_path: Path) -> None:
        """Test parsing a function with multiple return values."""
        code = """package main

func Divide(a, b int) (int, error) {
    if b == 0 {
        return 0, fmt.Errorf("division by zero")
    }
    return a / b, nil
}
"""
        file_path = tmp_path / "math.go"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "Divide"
        assert "(int, error)" in entities[0].signature

    def test_line_count(self, tmp_path: Path) -> None:
        """Test that line count is returned correctly."""
        code = """package main

func main() {
    fmt.Println("Hello")
}
"""
        file_path = tmp_path / "main.go"
        file_path.write_text(code)

        _, line_count = self.parser.parse_file(file_path)

        assert line_count == 6
