"""Tests for the text output formatter."""

import pytest

from contexto.graph import GraphNode
from contexto.output import TextFormatter, _truncate


class TestTextFormatter:
    """Tests for TextFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = TextFormatter()

    def test_format_map(self):
        """Test formatting project map."""
        children = [
            ("src", {"files": 10, "classes": 5, "functions": 20, "methods": 50}),
            ("tests", {"files": 3, "classes": 0, "functions": 10, "methods": 0}),
        ]

        output = self.formatter.format_map(
            root_name="myproject",
            root_path="/path/to/project",
            stats={"files": 13, "classes": 5, "functions": 30, "methods": 50},
            children=children,
        )

        assert "project: myproject" in output
        assert "root: /path/to/project" in output
        assert "src/" in output
        assert "10 files" in output
        assert "5 classes" in output
        assert "tests/" in output

    def test_format_expand_directory(self):
        """Test expanding a directory node."""
        node = GraphNode(
            id="src",
            name="src",
            type="dir",
        )

        children = [
            GraphNode(id="src/utils", name="utils", type="dir"),
            GraphNode(id="src/main.py", name="main.py", type="file"),
        ]

        stats_map = {
            "src/utils": {"files": 5, "classes": 2, "functions": 10, "methods": 20},
            "src/main.py": {"files": 1, "classes": 1, "functions": 3, "methods": 5},
        }

        output = self.formatter.format_expand(node, children, stats_map)

        assert "src/" in output
        assert "utils/" in output
        assert "5 files" in output
        assert "main.py" in output

    def test_format_expand_file(self):
        """Test expanding a file node."""
        node = GraphNode(
            id="src/main.py",
            name="main.py",
            type="file",
            file_path="src/main.py",
            line_end=100,
        )

        children = [
            GraphNode(
                id="src/main.py:Calculator",
                name="Calculator",
                type="class",
                line_start=10,
                line_end=50,
                docstring="A calculator class.",
                children_ids=["src/main.py:Calculator.add"],
            ),
            GraphNode(
                id="src/main.py:main",
                name="main",
                type="function",
                line_start=60,
                line_end=70,
            ),
        ]

        output = self.formatter.format_expand(node, children, {})

        assert "src/main.py" in output
        assert "100 lines" in output
        assert "class Calculator" in output
        assert "[10-50]" in output
        assert "A calculator class." in output
        assert "function main" in output

    def test_format_expand_class(self):
        """Test expanding a class node."""
        node = GraphNode(
            id="src/main.py:Calculator",
            name="Calculator",
            type="class",
            file_path="src/main.py",
            line_start=10,
            line_end=50,
            docstring="A calculator class.",
        )

        children = [
            GraphNode(
                id="src/main.py:Calculator.add",
                name="add",
                type="method",
                line_start=15,
                line_end=20,
                signature="def add(self, a, b)",
                docstring="Add two numbers.",
            ),
        ]

        output = self.formatter.format_expand(node, children, {})

        assert "class Calculator" in output
        assert "[10-50]" in output
        assert "file: src/main.py" in output
        assert "add" in output
        assert "def add(self, a, b)" in output

    def test_format_inspect(self):
        """Test inspecting an entity."""
        node = GraphNode(
            id="src/main.py:process",
            name="process",
            type="function",
            file_path="src/main.py",
            line_start=10,
            line_end=30,
            signature="def process(data: dict) -> bool",
            docstring="Process the data.",
            calls=["validate", "save"],
        )

        output = self.formatter.format_inspect(
            node,
            calls_to=["validate", "save"],
            called_by=["main", "handler"],
        )

        assert "function: process" in output
        assert "file: src/main.py" in output
        assert "[10-30]" in output
        assert "signature: def process(data: dict) -> bool" in output
        assert "docstring: Process the data." in output
        assert "calls:" in output
        assert "- validate" in output
        assert "- save" in output
        assert "called by:" in output
        assert "- main" in output
        assert "- handler" in output

    def test_format_search_results(self):
        """Test formatting search results."""
        results = [
            (GraphNode(
                id="src/main.py:process",
                name="process",
                type="function",
                signature="def process()",
            ), 0.95),
            (GraphNode(
                id="src/utils.py:helper",
                name="helper",
                type="function",
                signature="def helper()",
            ), 0.75),
        ]

        output = self.formatter.format_search_results("process", results)

        assert 'search: "process"' in output
        assert "(2 results)" in output
        assert "1. src/main.py:process [function]" in output
        assert "def process()" in output
        assert "2. src/utils.py:helper [function]" in output

    def test_format_search_no_results(self):
        """Test formatting search with no results."""
        output = self.formatter.format_search_results("nonexistent", [])

        assert 'search: "nonexistent"' in output
        assert "(0 results)" in output

    def test_format_read(self):
        """Test formatting file read output."""
        content = "def hello():\n    print('Hello!')"

        output = self.formatter.format_read(
            file_path="src/main.py",
            content=content,
            start_line=10,
        )

        assert "file: src/main.py" in output
        assert "  10 | def hello():" in output
        assert "  11 |     print('Hello!')" in output


class TestTruncate:
    """Tests for the _truncate helper."""

    def test_no_truncation_needed(self):
        """Test text shorter than max length."""
        text = "Short text"
        result = _truncate(text, 100)
        assert result == text

    def test_truncation_single_line(self):
        """Test truncating single line text."""
        text = "This is a very long line that needs truncation"
        result = _truncate(text, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_truncation_keeps_first_line(self):
        """Test that truncation keeps first line if possible."""
        text = "Short first line\nVery long second line that goes on and on"
        result = _truncate(text, 30)
        assert result == "Short first line"

    def test_truncation_exact_length(self):
        """Test text exactly at max length."""
        text = "Exactly 10"
        result = _truncate(text, 10)
        assert result == text

    def test_truncation_empty_string(self):
        """Test truncating empty string."""
        result = _truncate("", 10)
        assert result == ""

    def test_truncation_none(self):
        """Test truncating None returns empty string."""
        result = _truncate(None, 10)
        assert result == ""
