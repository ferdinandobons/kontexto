"""Tests for the CLI commands."""

import json
from typer.testing import CliRunner

from kontexto.cli import app


runner = CliRunner()


class TestIndexCommand:
    """Tests for the index command."""

    def test_index_creates_database(self, sample_project):
        """Test that index command creates the database."""
        result = runner.invoke(app, ["index", str(sample_project)])

        assert result.exit_code == 0
        assert "Indexed successfully" in result.stdout

        # Database should exist
        db_path = sample_project / ".kontexto" / "index.db"
        assert db_path.exists()

    def test_index_shows_stats(self, sample_project):
        """Test that index shows statistics."""
        result = runner.invoke(app, ["index", str(sample_project)])

        assert result.exit_code == 0
        assert "Files:" in result.stdout
        assert "Classes:" in result.stdout
        assert "Functions:" in result.stdout

    def test_index_invalid_path(self, temp_dir):
        """Test index with invalid path."""
        result = runner.invoke(app, ["index", str(temp_dir / "nonexistent")])

        assert result.exit_code == 1
        assert "not a directory" in result.stdout

    def test_index_incremental(self, sample_project):
        """Test incremental indexing."""
        # First, do a full index
        runner.invoke(app, ["index", str(sample_project)])

        # Then do incremental
        result = runner.invoke(app, ["index", "--incremental", str(sample_project)])

        assert result.exit_code == 0
        assert "Incremental index complete" in result.stdout
        assert "Added: 0 files" in result.stdout
        assert "Updated: 0 files" in result.stdout

    def test_index_incremental_detects_changes(self, sample_project):
        """Test that incremental index detects file changes."""
        # First, do a full index
        runner.invoke(app, ["index", str(sample_project)])

        # Modify a file
        main_py = sample_project / "src" / "main.py"
        main_py.write_text(main_py.read_text() + "\n# Modified")

        # Do incremental index
        result = runner.invoke(app, ["index", "-i", str(sample_project)])

        assert result.exit_code == 0
        assert "Updated: 1 files" in result.stdout


class TestMapCommand:
    """Tests for the map command."""

    def test_map_returns_json(self, indexed_project):
        """Test that map returns valid JSON."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["map", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "map"
        assert "project" in data
        assert "stats" in data
        assert "children" in data

    def test_map_shows_structure(self, indexed_project):
        """Test that map shows project structure."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["map", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        child_ids = [c["id"] for c in data["children"]]
        assert "src" in child_ids

    def test_map_no_index(self, sample_project):
        """Test map without existing index."""
        result = runner.invoke(app, ["map", str(sample_project)])

        assert result.exit_code == 1
        assert "No index found" in result.stdout


class TestExpandCommand:
    """Tests for the expand command."""

    def test_expand_returns_json(self, indexed_project):
        """Test that expand returns valid JSON."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["expand", "src", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "expand"
        assert "node" in data
        assert "children" in data

    def test_expand_directory(self, indexed_project):
        """Test expanding a directory."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["expand", "src", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["node"]["id"] == "src"
        assert data["node"]["type"] == "dir"

    def test_expand_file(self, indexed_project):
        """Test expanding a file."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["expand", "src/main.py", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["node"]["id"] == "src/main.py"
        assert data["node"]["type"] == "file"
        # Should have children (functions)
        assert len(data["children"]) > 0

    def test_expand_nonexistent(self, indexed_project):
        """Test expanding nonexistent node."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["expand", "nonexistent", "-p", str(project_path)])

        assert result.exit_code == 1
        assert "Node not found" in result.stdout


class TestInspectCommand:
    """Tests for the inspect command."""

    def test_inspect_returns_json(self, indexed_project):
        """Test that inspect returns valid JSON."""
        project_path, _ = indexed_project

        result = runner.invoke(
            app, ["inspect", "src/utils/helpers.py:Calculator", "-p", str(project_path)]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "inspect"
        assert "node" in data
        assert "calls" in data
        assert "called_by" in data

    def test_inspect_class(self, indexed_project):
        """Test inspecting a class."""
        project_path, _ = indexed_project

        result = runner.invoke(
            app, ["inspect", "src/utils/helpers.py:Calculator", "-p", str(project_path)]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["node"]["name"] == "Calculator"
        assert data["node"]["type"] == "class"

    def test_inspect_function(self, indexed_project):
        """Test inspecting a function."""
        project_path, _ = indexed_project

        result = runner.invoke(
            app, ["inspect", "src/main.py:main", "-p", str(project_path)]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["node"]["name"] == "main"
        assert data["node"]["type"] == "function"

    def test_inspect_nonexistent(self, indexed_project):
        """Test inspecting nonexistent entity."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["inspect", "nonexistent", "-p", str(project_path)])

        assert result.exit_code == 1
        assert "Entity not found" in result.stdout


class TestSearchCommand:
    """Tests for the search command."""

    def test_search_returns_json(self, indexed_project):
        """Test that search returns valid JSON."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["search", "Calculator", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "search"
        assert data["query"] == "Calculator"
        assert "count" in data
        assert "results" in data

    def test_search_finds_results(self, indexed_project):
        """Test that search finds results."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["search", "Calculator", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["count"] > 0
        names = [r["node"]["name"] for r in data["results"]]
        assert "Calculator" in names

    def test_search_with_limit(self, indexed_project):
        """Test search with limit option."""
        project_path, _ = indexed_project

        result = runner.invoke(
            app, ["search", "def", "-l", "2", "-p", str(project_path)]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["results"]) <= 2

    def test_search_no_results(self, indexed_project):
        """Test search with no results."""
        project_path, _ = indexed_project

        result = runner.invoke(
            app, ["search", "xyznonexistent", "-p", str(project_path)]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["count"] == 0
        assert data["results"] == []


class TestReadCommand:
    """Tests for the read command."""

    def test_read_returns_raw_content(self, indexed_project):
        """Test that read returns raw file content."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["read", "src/main.py", "-p", str(project_path)])

        assert result.exit_code == 0
        # Output should be raw code, not JSON
        assert "def main" in result.stdout

    def test_read_file(self, indexed_project):
        """Test reading a file."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["read", "src/main.py", "-p", str(project_path)])

        assert result.exit_code == 0
        # Should contain the main function
        assert "def main" in result.stdout

    def test_read_with_line_range(self, indexed_project):
        """Test reading file with line range."""
        project_path, _ = indexed_project

        result = runner.invoke(
            app, ["read", "src/main.py", "1", "5", "-p", str(project_path)]
        )

        assert result.exit_code == 0
        # Raw content should have 5 lines
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 5

    def test_read_nonexistent(self, indexed_project):
        """Test reading nonexistent file."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["read", "nonexistent.py", "-p", str(project_path)])

        assert result.exit_code == 1
        assert "File not found" in result.stdout


class TestHierarchyCommand:
    """Tests for the hierarchy command."""

    def test_hierarchy_returns_json(self, indexed_project_with_inheritance):
        """Test that hierarchy returns valid JSON."""
        project_path, _ = indexed_project_with_inheritance

        result = runner.invoke(app, ["hierarchy", "BaseModel", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "hierarchy"
        assert data["base_class"] == "BaseModel"
        assert "count" in data
        assert "subclasses" in data

    def test_hierarchy_finds_subclasses(self, indexed_project_with_inheritance):
        """Test that hierarchy finds all subclasses."""
        project_path, _ = indexed_project_with_inheritance

        result = runner.invoke(app, ["hierarchy", "BaseModel", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        names = {s["name"] for s in data["subclasses"]}
        assert "User" in names
        assert "Product" in names
        assert "Order" in names

    def test_hierarchy_nested_inheritance(self, indexed_project_with_inheritance):
        """Test hierarchy with nested inheritance."""
        project_path, _ = indexed_project_with_inheritance

        result = runner.invoke(app, ["hierarchy", "User", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Admin inherits from User
        names = {s["name"] for s in data["subclasses"]}
        assert "Admin" in names

    def test_hierarchy_no_subclasses(self, indexed_project_with_inheritance):
        """Test hierarchy when no subclasses exist."""
        project_path, _ = indexed_project_with_inheritance

        result = runner.invoke(
            app, ["hierarchy", "NonexistentBase", "-p", str(project_path)]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["count"] == 0
        assert data["subclasses"] == []

    def test_hierarchy_shows_base_classes(self, indexed_project_with_inheritance):
        """Test that hierarchy results include base_classes field."""
        project_path, _ = indexed_project_with_inheritance

        result = runner.invoke(app, ["hierarchy", "BaseModel", "-p", str(project_path)])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for subclass in data["subclasses"]:
            assert "base_classes" in subclass
            assert "BaseModel" in subclass["base_classes"]


class TestCLIIntegration:
    """Integration tests for CLI workflow."""

    def test_full_workflow(self, sample_project):
        """Test a full CLI workflow: index -> map -> expand -> search -> read."""
        # Index
        result = runner.invoke(app, ["index", str(sample_project)])
        assert result.exit_code == 0

        # Map
        result = runner.invoke(app, ["map", str(sample_project)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "map"

        # Expand
        result = runner.invoke(app, ["expand", "src", "-p", str(sample_project)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "expand"

        # Search
        result = runner.invoke(app, ["search", "Calculator", "-p", str(sample_project)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["command"] == "search"
        assert "Calculator" in [r["node"]["name"] for r in data["results"]]

        # Read (returns raw content, not JSON)
        result = runner.invoke(app, ["read", "src/main.py", "-p", str(sample_project)])
        assert result.exit_code == 0
        assert "def main" in result.stdout

    def test_workflow_with_hierarchy(self, project_with_inheritance):
        """Test workflow including hierarchy command."""
        # Index
        result = runner.invoke(app, ["index", str(project_with_inheritance)])
        assert result.exit_code == 0

        # Hierarchy
        result = runner.invoke(
            app, ["hierarchy", "BaseModel", "-p", str(project_with_inheritance)]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["count"] >= 3  # User, Product, Order


class TestCLIEdgeCases:
    """Test edge cases and error handling."""

    def test_read_invalid_line_range(self, indexed_project):
        """Test read with invalid line range (start > end)."""
        project_path, _ = indexed_project

        result = runner.invoke(
            app, ["read", "src/main.py", "10", "5", "-p", str(project_path)]
        )

        assert result.exit_code == 1
        assert "Invalid line range" in result.stdout

    def test_help_command(self):
        """Test that help command works."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "kontexto" in result.stdout.lower()

    def test_command_help(self):
        """Test that individual command help works."""
        commands = ["index", "map", "expand", "inspect", "search", "read", "hierarchy"]
        for cmd in commands:
            result = runner.invoke(app, [cmd, "--help"])
            assert result.exit_code == 0
