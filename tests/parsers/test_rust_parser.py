"""Tests for the tree-sitter Rust parser."""

from pathlib import Path

from kontexto.parsers.rust_parser import RustParser


class TestRustParser:
    """Test suite for RustParser."""

    def setup_method(self) -> None:
        self.parser = RustParser()

    def test_config(self) -> None:
        """Test parser configuration."""
        assert self.parser.config.name == "rust"
        assert ".rs" in self.parser.config.extensions

    def test_supports_file(self, tmp_path: Path) -> None:
        """Test file support detection."""
        rs_file = tmp_path / "lib.rs"
        rs_file.touch()
        py_file = tmp_path / "lib.py"
        py_file.touch()

        assert self.parser.supports_file(rs_file)
        assert not self.parser.supports_file(py_file)

    def test_parse_function(self, tmp_path: Path) -> None:
        """Test parsing a function."""
        code = """/// Say hello to someone
fn hello(name: &str) {
    println!("Hello, {}!", name);
}
"""
        file_path = tmp_path / "hello.rs"
        file_path.write_text(code)

        entities, line_count = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "hello"
        assert entities[0].type == "function"
        assert entities[0].language == "rust"
        assert "Say hello" in (entities[0].docstring or "")

    def test_parse_pub_function(self, tmp_path: Path) -> None:
        """Test parsing a public function."""
        code = """pub fn public_func() -> i32 {
    42
}
"""
        file_path = tmp_path / "lib.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "public_func"
        assert "pub" in entities[0].signature

    def test_parse_async_function(self, tmp_path: Path) -> None:
        """Test parsing an async function."""
        code = """async fn fetch_data(url: &str) -> Result<String, Error> {
    Ok(String::new())
}
"""
        file_path = tmp_path / "async.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "fetch_data"
        assert "async" in entities[0].signature

    def test_parse_struct(self, tmp_path: Path) -> None:
        """Test parsing a struct."""
        code = """/// Represents a user
struct User {
    id: u64,
    name: String,
}
"""
        file_path = tmp_path / "user.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "User"
        assert entities[0].type == "struct"
        assert "struct User" in entities[0].signature

    def test_parse_enum(self, tmp_path: Path) -> None:
        """Test parsing an enum."""
        code = """enum Color {
    Red,
    Green,
    Blue,
}
"""
        file_path = tmp_path / "color.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "Color"
        assert entities[0].type == "enum"

    def test_parse_trait(self, tmp_path: Path) -> None:
        """Test parsing a trait."""
        code = """trait Drawable {
    fn draw(&self);
    fn area(&self) -> f64;
}
"""
        file_path = tmp_path / "drawable.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # trait + 2 methods
        assert len(entities) >= 1
        trait_entity = next(e for e in entities if e.type == "trait")
        assert trait_entity.name == "Drawable"

    def test_parse_impl_block(self, tmp_path: Path) -> None:
        """Test parsing an impl block."""
        code = """struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn new(x: f64, y: f64) -> Self {
        Point { x, y }
    }

    fn distance(&self) -> f64 {
        (self.x * self.x + self.y * self.y).sqrt()
    }
}
"""
        file_path = tmp_path / "point.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        # struct + impl + methods
        struct_entity = next(e for e in entities if e.type == "struct")
        assert struct_entity.name == "Point"

        impl_entity = next(e for e in entities if e.type == "impl")
        assert impl_entity.name == "Point"

        methods = [e for e in entities if e.type == "method"]
        assert len(methods) == 2
        method_names = [m.name for m in methods]
        assert "new" in method_names
        assert "distance" in method_names

    def test_parse_impl_trait_for_type(self, tmp_path: Path) -> None:
        """Test parsing impl Trait for Type."""
        code = """struct Circle {
    radius: f64,
}

impl Drawable for Circle {
    fn draw(&self) {
        println!("Drawing circle");
    }
}
"""
        file_path = tmp_path / "circle.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        impl_entity = next(e for e in entities if e.type == "impl")
        assert "Drawable" in impl_entity.base_classes
        assert "impl Drawable for Circle" in impl_entity.signature

    def test_extract_calls(self, tmp_path: Path) -> None:
        """Test extraction of function calls."""
        code = """fn process() {
    let result = helper();
    println!("{}", result);
    save(result);
}
"""
        file_path = tmp_path / "calls.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        calls = entities[0].calls
        assert "helper" in calls
        assert "save" in calls

    def test_parse_generic_function(self, tmp_path: Path) -> None:
        """Test parsing a generic function."""
        code = """fn swap<T>(a: &mut T, b: &mut T) {
    std::mem::swap(a, b);
}
"""
        file_path = tmp_path / "generic.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "swap"

    def test_parse_unsafe_function(self, tmp_path: Path) -> None:
        """Test parsing an unsafe function."""
        code = """unsafe fn dangerous() {
    // Unsafe operations
}
"""
        file_path = tmp_path / "unsafe.rs"
        file_path.write_text(code)

        entities, _ = self.parser.parse_file(file_path)

        assert len(entities) == 1
        assert entities[0].name == "dangerous"
        assert "unsafe" in entities[0].signature

    def test_line_count(self, tmp_path: Path) -> None:
        """Test that line count is returned correctly."""
        code = """fn main() {
    println!("Hello");
}
"""
        file_path = tmp_path / "main.rs"
        file_path.write_text(code)

        _, line_count = self.parser.parse_file(file_path)

        assert line_count == 4
