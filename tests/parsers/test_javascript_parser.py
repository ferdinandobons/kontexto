"""Tests for the tree-sitter JavaScript/TypeScript parser."""

from pathlib import Path

from kontexto.parsers.javascript_parser import JavaScriptParser


class TestJavaScriptParser:
    """Test suite for JavaScriptParser."""

    def setup_method(self) -> None:
        self.parser = JavaScriptParser()

    def test_config(self) -> None:
        """Test parser configuration."""
        assert self.parser.config.name == "javascript"
        assert ".js" in self.parser.config.extensions
        assert ".ts" in self.parser.config.extensions
        assert ".tsx" in self.parser.config.extensions

    def test_supports_file(self, tmp_path: Path) -> None:
        """Test file support detection."""
        js_file = tmp_path / "test.js"
        js_file.touch()
        ts_file = tmp_path / "test.ts"
        ts_file.touch()
        py_file = tmp_path / "test.py"
        py_file.touch()

        assert self.parser.supports_file(js_file)
        assert self.parser.supports_file(ts_file)
        assert not self.parser.supports_file(py_file)

    def test_parse_function_declaration(self, tmp_path: Path) -> None:
        """Test parsing a function declaration."""
        code = """/**
 * Say hello
 */
function hello() {
    console.log("Hello!");
}
"""
        file_path = tmp_path / "hello.js"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "hello"
        assert entities[0].type == "function"
        assert entities[0].language == "javascript"

    def test_parse_arrow_function(self, tmp_path: Path) -> None:
        """Test parsing an arrow function."""
        code = """const greet = (name) => {
    return `Hello, ${name}!`;
};
"""
        file_path = tmp_path / "arrow.js"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "greet"
        assert entities[0].type == "function"
        assert "=>" in entities[0].signature

    def test_parse_class(self, tmp_path: Path) -> None:
        """Test parsing a JavaScript class."""
        code = """class Calculator {
    add(a, b) {
        return a + b;
    }

    subtract(a, b) {
        return a - b;
    }
}
"""
        file_path = tmp_path / "calc.js"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 3  # class + 2 methods

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "Calculator"

        methods = [e for e in entities if e.type == "method"]
        assert len(methods) == 2

    def test_parse_class_with_extends(self, tmp_path: Path) -> None:
        """Test parsing a class with inheritance."""
        code = """class Child extends Parent {
    constructor() {
        super();
    }
}
"""
        file_path = tmp_path / "child.js"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "Child"
        assert "Parent" in class_entity.base_classes

    def test_parse_typescript_interface(self, tmp_path: Path) -> None:
        """Test parsing a TypeScript interface."""
        code = """interface User {
    id: number;
    name: string;
}
"""
        file_path = tmp_path / "user.ts"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "User"
        assert entities[0].type == "interface"
        assert entities[0].language == "typescript"

    def test_parse_typescript_interface_extends(self, tmp_path: Path) -> None:
        """Test parsing a TypeScript interface with extends."""
        code = """interface Admin extends User {
    permissions: string[];
}
"""
        file_path = tmp_path / "admin.ts"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        interface = next(e for e in entities if e.type == "interface")
        assert interface.name == "Admin"

    def test_parse_typescript_class_implements(self, tmp_path: Path) -> None:
        """Test parsing a TypeScript class with implements."""
        code = """class UserManager implements IManager {
    getUser(id: number): User {
        return { id, name: "test" };
    }
}
"""
        file_path = tmp_path / "manager.ts"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        class_entity = next(e for e in entities if e.type == "class")
        assert class_entity.name == "UserManager"

    def test_parse_async_function(self, tmp_path: Path) -> None:
        """Test parsing an async function."""
        code = """async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}
"""
        file_path = tmp_path / "async.js"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "fetchData"
        assert "async" in entities[0].signature

    def test_extract_calls(self, tmp_path: Path) -> None:
        """Test extraction of function calls."""
        code = """function process() {
    const result = helper();
    console.log(result);
    return save(result);
}
"""
        file_path = tmp_path / "calls.js"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        calls = entities[0].calls
        assert "helper" in calls
        assert "log" in calls
        assert "save" in calls

    def test_parse_export_default(self, tmp_path: Path) -> None:
        """Test parsing an exported function."""
        code = """export default function main() {
    return "main";
}
"""
        file_path = tmp_path / "main.js"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "main"

    def test_parse_generator_function(self, tmp_path: Path) -> None:
        """Test parsing a generator function."""
        code = """function* generateNumbers() {
    yield 1;
    yield 2;
    yield 3;
}
"""
        file_path = tmp_path / "generator.js"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "generateNumbers"
