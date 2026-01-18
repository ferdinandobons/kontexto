"""Tests for the CLI commands."""

import pytest
from typer.testing import CliRunner

from contexto.cli import app


runner = CliRunner()


class TestIndexCommand:
    """Tests for the index command."""

    def test_index_creates_database(self, sample_project):
        """Test that index command creates the database."""
        result = runner.invoke(app, ["index", str(sample_project)])

        assert result.exit_code == 0
        assert "Indexed successfully" in result.stdout

        # Database should exist
        db_path = sample_project / ".contexto" / "index.db"
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

    def test_map_shows_structure(self, indexed_project):
        """Test that map shows project structure."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["map", str(project_path)])

        assert result.exit_code == 0
        assert "project:" in result.stdout
        assert "src/" in result.stdout

    def test_map_no_index(self, sample_project):
        """Test map without existing index."""
        result = runner.invoke(app, ["map", str(sample_project)])

        assert result.exit_code == 1
        assert "No index found" in result.stdout


class TestExpandCommand:
    """Tests for the expand command."""

    def test_expand_directory(self, indexed_project):
        """Test expanding a directory."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["expand", "src", "-p", str(project_path)])

        assert result.exit_code == 0
        assert "src/" in result.stdout

    def test_expand_file(self, indexed_project):
        """Test expanding a file."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["expand", "src/main.py", "-p", str(project_path)])

        assert result.exit_code == 0
        assert "src/main.py" in result.stdout

    def test_expand_nonexistent(self, indexed_project):
        """Test expanding nonexistent node."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["expand", "nonexistent", "-p", str(project_path)])

        assert result.exit_code == 1
        assert "Node not found" in result.stdout


class TestInspectCommand:
    """Tests for the inspect command."""

    def test_inspect_class(self, indexed_project):
        """Test inspecting a class."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["inspect", "src/utils/helpers.py:Calculator", "-p", str(project_path)])

        assert result.exit_code == 0
        assert "class: Calculator" in result.stdout

    def test_inspect_nonexistent(self, indexed_project):
        """Test inspecting nonexistent entity."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["inspect", "nonexistent", "-p", str(project_path)])

        assert result.exit_code == 1
        assert "Entity not found" in result.stdout


class TestSearchCommand:
    """Tests for the search command."""

    def test_search_finds_results(self, indexed_project):
        """Test that search finds results."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["search", "Calculator", "-p", str(project_path)])

        assert result.exit_code == 0
        assert "search:" in result.stdout
        assert "Calculator" in result.stdout

    def test_search_with_limit(self, indexed_project):
        """Test search with limit option."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["search", "def", "-l", "2", "-p", str(project_path)])

        assert result.exit_code == 0

    def test_search_no_results(self, indexed_project):
        """Test search with no results."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["search", "xyznonexistent", "-p", str(project_path)])

        assert result.exit_code == 0
        assert "(0 results)" in result.stdout


class TestReadCommand:
    """Tests for the read command."""

    def test_read_file(self, indexed_project):
        """Test reading a file."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["read", "src/main.py", "-p", str(project_path)])

        assert result.exit_code == 0
        assert "file: src/main.py" in result.stdout
        assert "def main" in result.stdout

    def test_read_with_line_range(self, indexed_project):
        """Test reading file with line range."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["read", "src/main.py", "1", "5", "-p", str(project_path)])

        assert result.exit_code == 0
        assert "   1 |" in result.stdout

    def test_read_nonexistent(self, indexed_project):
        """Test reading nonexistent file."""
        project_path, _ = indexed_project

        result = runner.invoke(app, ["read", "nonexistent.py", "-p", str(project_path)])

        assert result.exit_code == 1
        assert "File not found" in result.stdout


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
        assert "src/" in result.stdout

        # Expand
        result = runner.invoke(app, ["expand", "src", "-p", str(sample_project)])
        assert result.exit_code == 0

        # Search
        result = runner.invoke(app, ["search", "Calculator", "-p", str(sample_project)])
        assert result.exit_code == 0
        assert "Calculator" in result.stdout

        # Read
        result = runner.invoke(app, ["read", "src/main.py", "-p", str(sample_project)])
        assert result.exit_code == 0
        assert "file: src/main.py" in result.stdout
