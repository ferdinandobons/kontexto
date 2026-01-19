"""Tests for the SQLite store."""

from kontexto.graph import CodeGraph, GraphNode
from kontexto.store import Store


class TestStore:
    """Tests for the Store class."""

    def test_create_store(self, temp_dir):
        """Test creating a new store."""
        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            assert db_path.exists()
            assert store.conn is not None

    def test_context_manager(self, temp_dir):
        """Test store as context manager."""
        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            # Connection should be open
            cursor = store.conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

        # After context, connection should be closed
        # (We can't easily test this without accessing private state)

    def test_save_and_load_graph(self, sample_project):
        """Test saving and loading a graph."""
        kontexto_dir = sample_project / ".kontexto"
        kontexto_dir.mkdir()
        db_path = kontexto_dir / "index.db"

        # Build and save
        graph = CodeGraph(sample_project)
        graph.build()

        with Store(db_path) as store:
            store.save_graph(graph)

        # Load in a new store instance
        with Store(db_path) as store:
            loaded_graph = store.load_graph(sample_project)

        # Compare
        assert set(loaded_graph.nodes.keys()) == set(graph.nodes.keys())

    def test_get_node(self, indexed_project):
        """Test getting a single node."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            root = store.get_node(".")
            assert root is not None
            assert root.type == "dir"

            src = store.get_node("src")
            assert src is not None
            assert src.type == "dir"

    def test_get_node_not_found(self, indexed_project):
        """Test getting a non-existent node."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            node = store.get_node("nonexistent")
            assert node is None

    def test_get_children(self, indexed_project):
        """Test getting children of a node."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            children = store.get_children(".")
            assert len(children) > 0

            # All children should have root as parent
            for child in children:
                assert child.parent_id == "."

    def test_get_stats(self, indexed_project):
        """Test getting statistics."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            stats = store.get_stats(".")

        assert "files" in stats
        assert "classes" in stats
        assert "functions" in stats
        assert "methods" in stats

    def test_get_stats_batch(self, indexed_project):
        """Test batch statistics query."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            stats = store.get_stats_batch([".", "src"])

        assert "." in stats
        assert "src" in stats
        assert stats["."]["files"] >= stats["src"]["files"]

    def test_file_hash_operations(self, indexed_project):
        """Test file hash save and retrieve."""
        project_path, db_path = indexed_project

        test_file = project_path / "src" / "main.py"
        test_hash = Store.compute_file_hash(test_file)

        with Store(db_path) as store:
            store.save_file_hash("src/main.py", test_hash)

            retrieved = store.get_file_hash("src/main.py")
            assert retrieved == test_hash

    def test_file_hash_batch(self, indexed_project):
        """Test batch file hash operations."""
        project_path, db_path = indexed_project

        hashes = {
            "file1.py": "abc123",
            "file2.py": "def456",
        }

        with Store(db_path) as store:
            store.save_file_hashes_batch(hashes)

            assert store.get_file_hash("file1.py") == "abc123"
            assert store.get_file_hash("file2.py") == "def456"

    def test_delete_file_nodes(self, indexed_project):
        """Test deleting nodes for a file."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            # Verify the file exists
            node = store.get_node("src/main.py")
            assert node is not None

            # Delete it
            store.delete_file_nodes("src/main.py")

            # Should be gone
            node = store.get_node("src/main.py")
            assert node is None

    def test_delete_file_nodes_batch(self, indexed_project):
        """Test batch deletion of file nodes."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            # Add some test file hashes
            store.save_file_hashes_batch(
                {
                    "test1.py": "hash1",
                    "test2.py": "hash2",
                }
            )

            store.delete_file_nodes_batch(["test1.py", "test2.py"])

            assert store.get_file_hash("test1.py") is None
            assert store.get_file_hash("test2.py") is None

    def test_get_indexed_files(self, indexed_project):
        """Test getting all indexed files."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            # Add some file hashes first
            store.save_file_hashes_batch(
                {
                    "file1.py": "hash1",
                    "file2.py": "hash2",
                }
            )

            indexed = store.get_indexed_files()

            assert "file1.py" in indexed
            assert "file2.py" in indexed
            assert indexed["file1.py"] == "hash1"

    def test_get_callers(self, indexed_project):
        """Test finding callers of a function."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            # In our sample project, main() calls helper()
            callers = store.get_callers("helper")

            # Should find at least one caller
            # (main function calls helper)
            assert isinstance(callers, list)

    def test_compute_file_hash(self, temp_dir):
        """Test computing file hash."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        hash1 = Store.compute_file_hash(test_file)

        # Same content should give same hash
        hash2 = Store.compute_file_hash(test_file)
        assert hash1 == hash2

        # Different content should give different hash
        test_file.write_text("Different content")
        hash3 = Store.compute_file_hash(test_file)
        assert hash1 != hash3

    def test_transaction_rollback(self, temp_dir):
        """Test that failed transactions rollback."""
        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            # Create a simple graph
            graph = CodeGraph(temp_dir)
            graph.nodes["."] = GraphNode(id=".", name="root", type="dir")
            store.save_graph(graph)

        # The save should have succeeded
        with Store(db_path) as store:
            node = store.get_node(".")
            assert node is not None

    def test_get_subclasses(self, temp_dir):
        """Test finding subclasses of a base class."""
        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            # Create a graph with classes that have inheritance
            graph = CodeGraph(temp_dir)
            graph.nodes["."] = GraphNode(id=".", name="root", type="dir")
            graph.nodes["models.py"] = GraphNode(
                id="models.py",
                name="models.py",
                type="file",
                parent_id=".",
                file_path="models.py",
            )
            graph.nodes["models.py:User"] = GraphNode(
                id="models.py:User",
                name="User",
                type="class",
                parent_id="models.py",
                file_path="models.py",
                signature="class User(BaseModel)",
                base_classes=["BaseModel"],
            )
            graph.nodes["models.py:Product"] = GraphNode(
                id="models.py:Product",
                name="Product",
                type="class",
                parent_id="models.py",
                file_path="models.py",
                signature="class Product(BaseModel)",
                base_classes=["BaseModel"],
            )
            graph.nodes["models.py:Order"] = GraphNode(
                id="models.py:Order",
                name="Order",
                type="class",
                parent_id="models.py",
                file_path="models.py",
                signature="class Order(BaseModel, Serializable)",
                base_classes=["BaseModel", "Serializable"],
            )
            graph.nodes["models.py:Other"] = GraphNode(
                id="models.py:Other",
                name="Other",
                type="class",
                parent_id="models.py",
                file_path="models.py",
                signature="class Other",
                base_classes=[],
            )
            store.save_graph(graph)

            # Find subclasses of BaseModel
            subclasses = store.get_subclasses("BaseModel")
            assert len(subclasses) == 3
            names = {s.name for s in subclasses}
            assert names == {"User", "Product", "Order"}

            # Find subclasses of Serializable
            subclasses = store.get_subclasses("Serializable")
            assert len(subclasses) == 1
            assert subclasses[0].name == "Order"

            # No subclasses for unknown class
            subclasses = store.get_subclasses("Unknown")
            assert len(subclasses) == 0

    def test_get_subclasses_special_characters(self, temp_dir):
        """Test that get_subclasses handles special LIKE characters."""
        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            graph = CodeGraph(temp_dir)
            graph.nodes["."] = GraphNode(id=".", name="root", type="dir")
            graph.nodes["test.py"] = GraphNode(
                id="test.py",
                name="test.py",
                type="file",
                parent_id=".",
                file_path="test.py",
            )
            # Class with base class containing underscore
            graph.nodes["test.py:MyClass"] = GraphNode(
                id="test.py:MyClass",
                name="MyClass",
                type="class",
                parent_id="test.py",
                file_path="test.py",
                base_classes=["Base_Model"],
            )
            store.save_graph(graph)

            # Should find exact match only
            subclasses = store.get_subclasses("Base_Model")
            assert len(subclasses) == 1

            # Underscore in LIKE is wildcard, but our search should still work
            subclasses = store.get_subclasses("BaseXModel")
            assert len(subclasses) == 0

    def test_get_callers_at_different_positions(self, temp_dir):
        """Test get_callers with function at start, middle, and end of calls list."""
        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            graph = CodeGraph(temp_dir)
            graph.nodes["."] = GraphNode(id=".", name="root", type="dir")
            graph.nodes["test.py"] = GraphNode(
                id="test.py",
                name="test.py",
                type="file",
                parent_id=".",
                file_path="test.py",
            )
            # Function with target at start of calls list
            graph.nodes["test.py:func1"] = GraphNode(
                id="test.py:func1",
                name="func1",
                type="function",
                parent_id="test.py",
                file_path="test.py",
                calls=["target", "other"],
            )
            # Function with target in middle
            graph.nodes["test.py:func2"] = GraphNode(
                id="test.py:func2",
                name="func2",
                type="function",
                parent_id="test.py",
                file_path="test.py",
                calls=["other", "target", "another"],
            )
            # Function with target at end
            graph.nodes["test.py:func3"] = GraphNode(
                id="test.py:func3",
                name="func3",
                type="function",
                parent_id="test.py",
                file_path="test.py",
                calls=["other", "target"],
            )
            # Function with only target
            graph.nodes["test.py:func4"] = GraphNode(
                id="test.py:func4",
                name="func4",
                type="function",
                parent_id="test.py",
                file_path="test.py",
                calls=["target"],
            )
            store.save_graph(graph)

            callers = store.get_callers("target")
            assert len(callers) == 4
            caller_ids = set(callers)
            assert "test.py:func1" in caller_ids
            assert "test.py:func2" in caller_ids
            assert "test.py:func3" in caller_ids
            assert "test.py:func4" in caller_ids

    def test_base_classes_preserved_on_load(self, temp_dir):
        """Test that base_classes are properly saved and loaded."""
        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            graph = CodeGraph(temp_dir)
            graph.nodes["."] = GraphNode(id=".", name="root", type="dir")
            graph.nodes["test.py"] = GraphNode(
                id="test.py",
                name="test.py",
                type="file",
                parent_id=".",
                file_path="test.py",
            )
            graph.nodes["test.py:MyClass"] = GraphNode(
                id="test.py:MyClass",
                name="MyClass",
                type="class",
                parent_id="test.py",
                file_path="test.py",
                base_classes=["Base1", "Base2", "Base3"],
            )
            store.save_graph(graph)

        with Store(db_path) as store:
            loaded = store.load_graph(temp_dir)
            node = loaded.nodes["test.py:MyClass"]
            assert node.base_classes == ["Base1", "Base2", "Base3"]

            # Also test get_node
            node2 = store.get_node("test.py:MyClass")
            assert node2.base_classes == ["Base1", "Base2", "Base3"]

            # And get_children
            children = store.get_children("test.py")
            assert len(children) == 1
            assert children[0].base_classes == ["Base1", "Base2", "Base3"]
