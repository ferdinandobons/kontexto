"""Tests for the tree-sitter Java parser."""

from pathlib import Path

from kontexto.parsers.java_parser import JavaParser


class TestJavaParser:
    """Test suite for JavaParser."""

    def setup_method(self) -> None:
        self.parser = JavaParser()

    def test_config(self) -> None:
        """Test parser configuration."""
        assert self.parser.config.name == "java"
        assert ".java" in self.parser.config.extensions

    def test_supports_file(self, tmp_path: Path) -> None:
        """Test file support detection."""
        java_file = tmp_path / "Main.java"
        java_file.touch()
        py_file = tmp_path / "main.py"
        py_file.touch()

        assert self.parser.supports_file(java_file)
        assert not self.parser.supports_file(py_file)

    def test_parse_class(self, tmp_path: Path) -> None:
        """Test parsing a class declaration."""
        code = """/**
 * Represents a user in the system.
 */
public class User {
    private String name;
}
"""
        file_path = tmp_path / "User.java"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "User"
        assert entities[0].type == "class"
        assert entities[0].language == "java"
        assert "public" in entities[0].signature
        assert "user in the system" in (entities[0].docstring or "").lower()

    def test_parse_class_with_methods(self, tmp_path: Path) -> None:
        """Test parsing a class with methods."""
        code = """public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int subtract(int a, int b) {
        return a - b;
    }
}
"""
        file_path = tmp_path / "Calculator.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # class + 2 methods
        assert len(entities) == 3

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "Calculator"

        methods = [e for e in entities if e.type == "method"]
        assert len(methods) == 2
        method_names = [m.name for m in methods]
        assert "add" in method_names
        assert "subtract" in method_names

    def test_parse_class_with_extends(self, tmp_path: Path) -> None:
        """Test parsing a class that extends another."""
        code = """public class AdminUser extends User {
    private String role;
}
"""
        file_path = tmp_path / "AdminUser.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "AdminUser"
        assert "User" in class_entity.base_classes
        assert "extends User" in class_entity.signature

    def test_parse_class_with_implements(self, tmp_path: Path) -> None:
        """Test parsing a class that implements interfaces."""
        code = """public class UserService implements IService, Runnable {
    public void run() {}
}
"""
        file_path = tmp_path / "UserService.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "UserService"
        assert "implements" in class_entity.signature

    def test_parse_interface(self, tmp_path: Path) -> None:
        """Test parsing an interface."""
        code = """public interface Drawable {
    void draw();
    double getArea();
}
"""
        file_path = tmp_path / "Drawable.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        interface_entity = next(e for e in entities if e.type == "interface")
        assert interface_entity.name == "Drawable"

    def test_parse_enum(self, tmp_path: Path) -> None:
        """Test parsing an enum."""
        code = """public enum Color {
    RED,
    GREEN,
    BLUE
}
"""
        file_path = tmp_path / "Color.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        enum_entity = next(e for e in entities if e.type == "enum")
        assert enum_entity.name == "Color"
        assert "enum Color" in enum_entity.signature

    def test_parse_constructor(self, tmp_path: Path) -> None:
        """Test parsing a constructor."""
        code = """public class Person {
    private String name;

    public Person(String name) {
        this.name = name;
    }
}
"""
        file_path = tmp_path / "Person.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # class + constructor
        assert len(entities) == 2

        constructor = next(
            e for e in entities if e.name == "Person" and e.type == "constructor"
        )
        assert constructor is not None
        assert "Person" in constructor.signature

    def test_parse_static_method(self, tmp_path: Path) -> None:
        """Test parsing a static method."""
        code = """public class Utils {
    public static int max(int a, int b) {
        return a > b ? a : b;
    }
}
"""
        file_path = tmp_path / "Utils.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        method = next(e for e in entities if e.type == "method")
        assert method.name == "max"
        assert "static" in method.signature

    def test_extract_calls(self, tmp_path: Path) -> None:
        """Test extraction of method calls."""
        code = """public class Processor {
    public void process() {
        String result = helper();
        System.out.println(result);
        save(result);
    }
}
"""
        file_path = tmp_path / "Processor.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        method = next(e for e in entities if e.type == "method")
        assert "helper" in method.calls
        assert "save" in method.calls

    def test_parse_nested_class(self, tmp_path: Path) -> None:
        """Test parsing a nested class."""
        code = """public class Outer {
    public class Inner {
        public void innerMethod() {}
    }
}
"""
        file_path = tmp_path / "Outer.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # Outer + Inner + innerMethod
        assert len(entities) == 3

        outer = next(e for e in entities if e.name == "Outer")
        inner = next(e for e in entities if e.name == "Inner")
        assert outer.type == "class"
        assert inner.type == "class"
        assert inner.parent_id is not None

    def test_parse_abstract_class(self, tmp_path: Path) -> None:
        """Test parsing an abstract class."""
        code = """public abstract class Shape {
    public abstract double area();
}
"""
        file_path = tmp_path / "Shape.java"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "Shape"
        assert "abstract" in class_entity.signature

    def test_line_count(self, tmp_path: Path) -> None:
        """Test that line count is returned correctly."""
        code = """public class Main {
    public static void main(String[] args) {
        System.out.println("Hello");
    }
}
"""
        file_path = tmp_path / "Main.java"
        file_path.write_text(code)

        _, line_count = self.parser.parse_file(file_path)

        assert line_count == 6
