"""Tests for the JSON output formatter."""

import json

from kontexto.graph import GraphNode
from kontexto.output import JsonFormatter, _node_to_dict


class TestNodeToDict:
    """Tests for the _node_to_dict helper function."""

    def test_basic_node(self):
        """Test converting a basic node to dict."""
        node = GraphNode(
            id="src/main.py:foo",
            name="foo",
            type="function",
        )
        result = _node_to_dict(node)

        assert result["id"] == "src/main.py:foo"
        assert result["name"] == "foo"
        assert result["type"] == "function"
        assert result["parent_id"] is None
        assert result["file_path"] is None
        assert result["children_ids"] == []
        assert result["calls"] == []
        assert result["base_classes"] == []

    def test_full_node(self):
        """Test converting a node with all fields populated."""
        node = GraphNode(
            id="src/main.py:Calculator",
            name="Calculator",
            type="class",
            parent_id="src/main.py",
            file_path="src/main.py",
            line_start=10,
            line_end=50,
            signature="class Calculator(BaseClass)",
            docstring="A calculator class.",
            children_ids=["src/main.py:Calculator.add"],
            calls=["validate", "init"],
            base_classes=["BaseClass"],
        )
        result = _node_to_dict(node)

        assert result["id"] == "src/main.py:Calculator"
        assert result["name"] == "Calculator"
        assert result["type"] == "class"
        assert result["parent_id"] == "src/main.py"
        assert result["file_path"] == "src/main.py"
        assert result["line_start"] == 10
        assert result["line_end"] == 50
        assert result["signature"] == "class Calculator(BaseClass)"
        assert result["docstring"] == "A calculator class."
        assert result["children_ids"] == ["src/main.py:Calculator.add"]
        assert result["calls"] == ["validate", "init"]
        assert result["base_classes"] == ["BaseClass"]


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_format_map(self):
        """Test formatting project map as JSON."""
        children = [
            ("src", {"files": 10, "classes": 5, "functions": 20, "methods": 50}),
            ("tests", {"files": 3, "classes": 0, "functions": 10, "methods": 0}),
        ]

        output = JsonFormatter.format_map(
            root_name="myproject",
            root_path="/path/to/project",
            stats={"files": 13, "classes": 5, "functions": 30, "methods": 50},
            children=children,
        )

        data = json.loads(output)
        assert data["command"] == "map"
        assert data["project"] == "myproject"
        assert data["root"] == "/path/to/project"
        assert data["stats"]["files"] == 13
        assert data["stats"]["classes"] == 5
        assert len(data["children"]) == 2
        assert data["children"][0]["id"] == "src"
        assert data["children"][0]["stats"]["files"] == 10
        assert data["children"][1]["id"] == "tests"

    def test_format_map_empty_children(self):
        """Test formatting project map with no children."""
        output = JsonFormatter.format_map(
            root_name="empty",
            root_path="/path/to/empty",
            stats={"files": 0, "classes": 0, "functions": 0, "methods": 0},
            children=[],
        )

        data = json.loads(output)
        assert data["command"] == "map"
        assert data["children"] == []

    def test_format_expand_directory(self):
        """Test expanding a directory node."""
        node = GraphNode(
            id="src",
            name="src",
            type="dir",
        )

        children = [
            GraphNode(id="src/utils", name="utils", type="dir"),
            GraphNode(id="src/main.py", name="main.py", type="file", line_end=100),
        ]

        stats_map = {
            "src/utils": {"files": 5, "classes": 2, "functions": 10, "methods": 20},
            "src/main.py": {"files": 1, "classes": 1, "functions": 3, "methods": 5},
        }

        output = JsonFormatter.format_expand(node, children, stats_map)

        data = json.loads(output)
        assert data["command"] == "expand"
        assert data["node"]["id"] == "src"
        assert data["node"]["type"] == "dir"
        assert len(data["children"]) == 2
        assert data["children"][0]["id"] == "src/utils"
        assert data["children"][0]["stats"]["files"] == 5
        assert data["children"][1]["id"] == "src/main.py"

    def test_format_expand_file(self):
        """Test expanding a file node."""
        node = GraphNode(
            id="src/main.py",
            name="main.py",
            type="file",
            file_path="src/main.py",
            line_start=1,
            line_end=100,
        )

        children = [
            GraphNode(
                id="src/main.py:Calculator",
                name="Calculator",
                type="class",
                line_start=10,
                line_end=50,
                signature="class Calculator(BaseClass)",
                docstring="A calculator class.",
                base_classes=["BaseClass"],
            ),
            GraphNode(
                id="src/main.py:main",
                name="main",
                type="function",
                line_start=60,
                line_end=70,
                signature="def main()",
            ),
        ]

        output = JsonFormatter.format_expand(node, children, {})

        data = json.loads(output)
        assert data["command"] == "expand"
        assert data["node"]["line_end"] == 100
        assert len(data["children"]) == 2
        assert data["children"][0]["name"] == "Calculator"
        assert data["children"][0]["type"] == "class"
        assert data["children"][0]["base_classes"] == ["BaseClass"]
        assert data["children"][1]["name"] == "main"
        assert data["children"][1]["type"] == "function"

    def test_format_expand_class(self):
        """Test expanding a class node to show methods."""
        node = GraphNode(
            id="src/main.py:Calculator",
            name="Calculator",
            type="class",
            file_path="src/main.py",
            line_start=10,
            line_end=50,
            docstring="A calculator class.",
            base_classes=["BaseClass"],
        )

        children = [
            GraphNode(
                id="src/main.py:Calculator.add",
                name="add",
                type="method",
                line_start=15,
                line_end=20,
                signature="def add(self, a: int, b: int) -> int",
                docstring="Add two numbers.",
            ),
        ]

        output = JsonFormatter.format_expand(node, children, {})

        data = json.loads(output)
        assert data["node"]["type"] == "class"
        assert data["node"]["base_classes"] == ["BaseClass"]
        assert len(data["children"]) == 1
        assert data["children"][0]["type"] == "method"
        assert (
            data["children"][0]["signature"] == "def add(self, a: int, b: int) -> int"
        )

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

        output = JsonFormatter.format_inspect(
            node,
            calls_to=["validate", "save"],
            called_by=["main", "handler"],
        )

        data = json.loads(output)
        assert data["command"] == "inspect"
        assert data["node"]["id"] == "src/main.py:process"
        assert data["node"]["name"] == "process"
        assert data["node"]["type"] == "function"
        assert data["node"]["signature"] == "def process(data: dict) -> bool"
        assert data["calls"] == ["validate", "save"]
        assert data["called_by"] == ["main", "handler"]

    def test_format_inspect_no_calls(self):
        """Test inspecting an entity with no calls."""
        node = GraphNode(
            id="src/main.py:simple",
            name="simple",
            type="function",
        )

        output = JsonFormatter.format_inspect(node, calls_to=[], called_by=[])

        data = json.loads(output)
        assert data["calls"] == []
        assert data["called_by"] == []

    def test_format_search_results(self):
        """Test formatting search results."""
        results = [
            (
                GraphNode(
                    id="src/main.py:process",
                    name="process",
                    type="function",
                    signature="def process()",
                ),
                0.95,
            ),
            (
                GraphNode(
                    id="src/utils.py:helper",
                    name="helper",
                    type="function",
                    signature="def helper()",
                ),
                0.75,
            ),
        ]

        output = JsonFormatter.format_search_results("process", results)

        data = json.loads(output)
        assert data["command"] == "search"
        assert data["query"] == "process"
        assert data["count"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["node"]["id"] == "src/main.py:process"
        assert data["results"][0]["score"] == 0.95
        assert data["results"][1]["node"]["id"] == "src/utils.py:helper"
        assert data["results"][1]["score"] == 0.75

    def test_format_search_no_results(self):
        """Test formatting search with no results."""
        output = JsonFormatter.format_search_results("nonexistent", [])

        data = json.loads(output)
        assert data["command"] == "search"
        assert data["query"] == "nonexistent"
        assert data["count"] == 0
        assert data["results"] == []

    def test_format_search_score_rounding(self):
        """Test that search scores are rounded to 4 decimal places."""
        results = [
            (GraphNode(id="a", name="a", type="function"), 0.123456789),
        ]

        output = JsonFormatter.format_search_results("test", results)

        data = json.loads(output)
        assert data["results"][0]["score"] == 0.1235

    def test_format_hierarchy(self):
        """Test formatting class hierarchy."""
        subclasses = [
            GraphNode(
                id="src/models/user.py:User",
                name="User",
                type="class",
                signature="class User(BaseModel)",
                base_classes=["BaseModel"],
            ),
            GraphNode(
                id="src/models/product.py:Product",
                name="Product",
                type="class",
                signature="class Product(BaseModel)",
                base_classes=["BaseModel"],
            ),
        ]

        output = JsonFormatter.format_hierarchy("BaseModel", subclasses)

        data = json.loads(output)
        assert data["command"] == "hierarchy"
        assert data["base_class"] == "BaseModel"
        assert data["count"] == 2
        assert len(data["subclasses"]) == 2
        assert data["subclasses"][0]["name"] == "User"
        assert data["subclasses"][0]["base_classes"] == ["BaseModel"]
        assert data["subclasses"][1]["name"] == "Product"

    def test_format_hierarchy_no_subclasses(self):
        """Test formatting hierarchy with no subclasses found."""
        output = JsonFormatter.format_hierarchy("UnknownClass", [])

        data = json.loads(output)
        assert data["command"] == "hierarchy"
        assert data["base_class"] == "UnknownClass"
        assert data["count"] == 0
        assert data["subclasses"] == []

    def test_json_output_is_valid(self):
        """Test that all formatter methods produce valid JSON."""
        node = GraphNode(id="test", name="test", type="function")

        # All these should produce parseable JSON
        outputs = [
            JsonFormatter.format_map("p", "/p", {}, []),
            JsonFormatter.format_expand(node, [], {}),
            JsonFormatter.format_inspect(node, [], []),
            JsonFormatter.format_search_results("q", []),
            JsonFormatter.format_hierarchy("B", []),
        ]

        for output in outputs:
            # Should not raise
            json.loads(output)

    def test_special_characters_in_content(self):
        """Test handling of special characters in docstrings and content."""
        node = GraphNode(
            id="test",
            name="test",
            type="function",
            docstring='Contains "quotes" and \\ backslashes',
        )

        output = JsonFormatter.format_inspect(node, [], [])
        data = json.loads(output)
        assert data["node"]["docstring"] == 'Contains "quotes" and \\ backslashes'

    def test_unicode_content(self):
        """Test handling of unicode characters."""
        node = GraphNode(
            id="test",
            name="test",
            type="function",
            docstring="Unicode: \u00e9\u00e8\u00e0\u00f9 \u4e2d\u6587 \U0001f600",
        )

        output = JsonFormatter.format_inspect(node, [], [])
        data = json.loads(output)
        assert "\u00e9" in data["node"]["docstring"]
