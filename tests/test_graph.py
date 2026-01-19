"""Tests for the code graph."""

from kontexto.graph import CodeGraph, GraphNode


class TestGraphNode:
    """Tests for GraphNode dataclass."""

    def test_create_node(self):
        """Test creating a basic node."""
        node = GraphNode(
            id="src/main.py",
            name="main.py",
            type="file",
        )

        assert node.id == "src/main.py"
        assert node.name == "main.py"
        assert node.type == "file"
        assert node.parent_id is None
        assert node.children_ids == []
        assert node.calls == []

    def test_node_with_all_fields(self):
        """Test creating a node with all fields."""
        node = GraphNode(
            id="src/main.py:process",
            name="process",
            type="function",
            parent_id="src/main.py",
            file_path="src/main.py",
            line_start=10,
            line_end=20,
            signature="def process(data: dict) -> None",
            docstring="Process the data.",
            calls=["validate", "save"],
        )

        assert node.signature == "def process(data: dict) -> None"
        assert node.docstring == "Process the data."
        assert "validate" in node.calls


class TestCodeGraph:
    """Tests for CodeGraph."""

    def test_build_graph(self, sample_project):
        """Test building a graph from a sample project."""
        graph = CodeGraph(sample_project)
        graph.build()

        # Should have root node
        root = graph.get_root()
        assert root.id == "."
        assert root.type == "dir"

        # Should have src directory
        assert "src" in graph.nodes

        # Should have Python files
        file_nodes = [n for n in graph.nodes.values() if n.type == "file"]
        assert len(file_nodes) >= 2  # main.py and helpers.py

    def test_graph_hierarchy(self, sample_project):
        """Test that graph hierarchy is correct."""
        graph = CodeGraph(sample_project)
        graph.build()

        # Check parent-child relationships
        src_node = graph.nodes["src"]
        assert src_node.parent_id == "."
        assert "." in [
            graph.nodes[c].parent_id
            for c in graph.nodes
            if graph.nodes[c].parent_id == "."
        ]

    def test_get_children(self, sample_project):
        """Test getting children of a node."""
        graph = CodeGraph(sample_project)
        graph.build()

        root_children = graph.get_children(".")
        assert len(root_children) > 0

        # src should be a child of root
        child_names = [c.name for c in root_children]
        assert "src" in child_names

    def test_get_stats(self, sample_project):
        """Test getting statistics for a node."""
        graph = CodeGraph(sample_project)
        graph.build()

        stats = graph.get_stats(".")

        assert stats["files"] > 0
        assert stats["classes"] >= 1  # Calculator
        assert stats["functions"] >= 2  # main, helper, format_output, async_fetch
        assert stats["methods"] >= 2  # add, subtract

    def test_exclude_patterns(self, sample_project):
        """Test that exclude patterns work."""
        # Create a __pycache__ directory
        pycache = sample_project / "src" / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-311.pyc").write_bytes(b"fake bytecode")

        graph = CodeGraph(sample_project)
        graph.build()

        # __pycache__ should not be in the graph
        assert "__pycache__" not in [n.name for n in graph.nodes.values()]

    def test_add_single_file(self, sample_project):
        """Test adding a single file to existing graph."""
        graph = CodeGraph(sample_project)
        graph.build()

        initial_file_count = len([n for n in graph.nodes.values() if n.type == "file"])

        # Create a new file
        new_file = sample_project / "src" / "new_module.py"
        new_file.write_text("def new_func(): pass")

        # Add it to the graph
        graph.add_single_file(new_file, "src/new_module.py", "src")

        new_file_count = len([n for n in graph.nodes.values() if n.type == "file"])
        assert new_file_count == initial_file_count + 1

    def test_add_single_file_updates_existing(self, sample_project):
        """Test that adding an existing file updates it."""
        graph = CodeGraph(sample_project)
        graph.build()

        # Update main.py with new content
        main_py = sample_project / "src" / "main.py"
        main_py.write_text("""
def func1(): pass
def func2(): pass
def func3(): pass
""")

        graph.add_single_file(main_py, "src/main.py", "src")

        # Should have new function count
        main_functions = [
            n
            for n in graph.nodes.values()
            if n.file_path == "src/main.py" and n.type == "function"
        ]
        assert len(main_functions) == 3
