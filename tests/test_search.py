"""Tests for the search engine."""

from kontexto.graph import CodeGraph
from kontexto.store import Store
from kontexto.search import SearchEngine


class TestSearchEngine:
    """Tests for SearchEngine."""

    def test_build_index(self, indexed_project):
        """Test building the search index."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            # Index should already be built by fixture
            cursor = store.conn.cursor()

            # Check that search_index has entries
            cursor.execute("SELECT COUNT(*) FROM search_index")
            count = cursor.fetchone()[0]
            assert count > 0

            # Check that idf table has entries
            cursor.execute("SELECT COUNT(*) FROM idf")
            count = cursor.fetchone()[0]
            assert count > 0

    def test_search_by_name(self, indexed_project):
        """Test searching by function/class name."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("Calculator")

            assert len(results) > 0
            # Calculator class should be in results
            names = [node.name for node, _ in results]
            assert "Calculator" in names

    def test_search_by_docstring(self, indexed_project):
        """Test searching by docstring content."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("add two numbers")

            assert len(results) > 0

    def test_search_empty_query(self, indexed_project):
        """Test searching with empty query."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("")

            assert results == []

    def test_search_no_results(self, indexed_project):
        """Test searching with no matching results."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("xyznonexistent123")

            assert results == []

    def test_search_limit(self, indexed_project):
        """Test search result limit."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("def", limit=2)

            # Should respect limit
            assert len(results) <= 2

    def test_search_scores_normalized(self, indexed_project):
        """Test that search scores are normalized between 0 and 1."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("Calculator")

            for _, score in results:
                assert 0 <= score <= 1

    def test_search_results_sorted_by_score(self, indexed_project):
        """Test that search results are sorted by score descending."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("add")

            scores = [score for _, score in results]
            assert scores == sorted(scores, reverse=True)

    def test_tokenize_camelcase(self, indexed_project):
        """Test tokenization of camelCase identifiers."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            tokens = engine._split_identifier("getUserData")

            assert "get" in tokens
            assert "user" in tokens
            assert "data" in tokens

    def test_tokenize_snake_case(self, indexed_project):
        """Test tokenization of snake_case identifiers."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            tokens = engine._split_identifier("get_user_data")

            assert "get" in tokens
            assert "user" in tokens
            assert "data" in tokens

    def test_tokenize_filters_stop_words(self, indexed_project):
        """Test that stop words are filtered."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            tokens = engine._tokenize("the function return a value")

            assert "the" not in tokens
            assert "return" not in tokens  # 'return' is a stop word
            assert "function" in tokens
            assert "value" in tokens

    def test_tokenize_filters_short_words(self, indexed_project):
        """Test that short words are filtered."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            tokens = engine._tokenize("ab cd efg")

            assert "ab" not in tokens
            assert "cd" not in tokens
            assert "efg" in tokens

    def test_idf_cache_loading(self, indexed_project):
        """Test that IDF cache is loaded correctly."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)

            # Cache should be empty initially
            assert engine._idf_cache == {}

            # Trigger cache load
            engine._load_idf_cache()

            # Cache should now have values
            assert len(engine._idf_cache) > 0

    def test_search_async_function(self, indexed_project):
        """Test searching for async function."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            results = engine.search("async fetch")

            # Should find our async_fetch function
            names = [node.name for node, _ in results]
            assert "async_fetch" in names


class TestSearchResultCaching:
    """Tests for search result caching."""

    def test_cache_stores_results(self, indexed_project):
        """Test that search results are cached."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)

            # Cache should be empty
            assert len(engine._result_cache) == 0

            # Perform a search
            results1 = engine.search("Calculator")

            # Cache should now have one entry
            assert len(engine._result_cache) == 1

            # Same search should return cached results
            results2 = engine.search("Calculator")

            # Results should be identical (same object reference due to cache)
            assert results1 is results2

    def test_cache_key_includes_limit(self, indexed_project):
        """Test that cache key includes the limit parameter."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)

            engine.search("Calculator", limit=5)
            engine.search("Calculator", limit=10)

            # Different limits should have different cache entries
            assert len(engine._result_cache) == 2
            assert "Calculator:5" in engine._result_cache
            assert "Calculator:10" in engine._result_cache

    def test_cache_cleared_on_build_index(self, indexed_project):
        """Test that cache is cleared when index is rebuilt."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)

            # Populate cache
            engine.search("Calculator")
            assert len(engine._result_cache) > 0

            # Rebuild index
            engine.build_index()

            # Cache should be cleared
            assert len(engine._result_cache) == 0


class TestIncrementalIndexing:
    """Tests for incremental search index updates."""

    def test_update_index_for_nodes(self, temp_dir):
        """Test updating search index for specific nodes."""
        from kontexto.graph import GraphNode

        db_path = temp_dir / "test.db"

        with Store(db_path) as store:
            # Create initial graph with one function
            graph = CodeGraph(temp_dir)
            graph.nodes["."] = GraphNode(id=".", name="root", type="dir")
            graph.nodes["test.py"] = GraphNode(
                id="test.py",
                name="test.py",
                type="file",
                parent_id=".",
                file_path="test.py",
            )
            graph.nodes["test.py:foo"] = GraphNode(
                id="test.py:foo",
                name="foo",
                type="function",
                parent_id="test.py",
                file_path="test.py",
                signature="def foo()",
                docstring="Original function",
            )
            store.save_graph(graph)

            engine = SearchEngine(store)
            engine.build_index()

            # Search should find "foo"
            results = engine.search("foo")
            assert len(results) == 1
            assert results[0][0].name == "foo"

            # Now add a new function to the graph
            graph.nodes["test.py:bar"] = GraphNode(
                id="test.py:bar",
                name="bar",
                type="function",
                parent_id="test.py",
                file_path="test.py",
                signature="def bar()",
                docstring="New function for searching",
            )
            store.save_graph(graph)

            # Update index just for the new node
            engine.update_index_for_nodes(["test.py:bar"], total_docs_changed=1)

            # Search should now find "bar"
            results = engine.search("bar")
            assert len(results) == 1
            assert results[0][0].name == "bar"

    def test_update_index_clears_cache(self, temp_dir):
        """Test that updating index clears the result cache."""
        from kontexto.graph import GraphNode

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
            graph.nodes["test.py:foo"] = GraphNode(
                id="test.py:foo",
                name="foo",
                type="function",
                parent_id="test.py",
                file_path="test.py",
            )
            store.save_graph(graph)

            engine = SearchEngine(store)
            engine.build_index()

            # Populate cache
            engine.search("foo")
            assert len(engine._result_cache) > 0

            # Update index
            engine.update_index_for_nodes(["test.py:foo"])

            # Cache should be cleared
            assert len(engine._result_cache) == 0

    def test_remove_nodes_from_index(self, temp_dir):
        """Test removing nodes from search index."""
        from kontexto.graph import GraphNode

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
            graph.nodes["test.py:removable"] = GraphNode(
                id="test.py:removable",
                name="removable",
                type="function",
                parent_id="test.py",
                file_path="test.py",
                signature="def removable()",
                docstring="This function will be removed",
            )
            store.save_graph(graph)

            engine = SearchEngine(store)
            engine.build_index()

            # Search should find it
            results = engine.search("removable")
            assert len(results) == 1

            # Remove from index
            engine.remove_nodes_from_index(["test.py:removable"])

            # Search should no longer find it
            results = engine.search("removable")
            assert len(results) == 0

    def test_remove_nodes_clears_cache(self, temp_dir):
        """Test that removing nodes clears the result cache."""
        from kontexto.graph import GraphNode

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
            graph.nodes["test.py:foo"] = GraphNode(
                id="test.py:foo",
                name="foo",
                type="function",
                parent_id="test.py",
                file_path="test.py",
            )
            store.save_graph(graph)

            engine = SearchEngine(store)
            engine.build_index()

            # Populate cache
            engine.search("foo")
            assert len(engine._result_cache) > 0

            # Remove from index
            engine.remove_nodes_from_index(["test.py:foo"])

            # Cache should be cleared
            assert len(engine._result_cache) == 0

    def test_update_empty_node_list(self, indexed_project):
        """Test that updating with empty list does nothing."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            engine.build_index()

            # Populate cache
            engine.search("Calculator")
            cache_size = len(engine._result_cache)

            # Update with empty list should not clear cache
            engine.update_index_for_nodes([])

            # Cache should still be populated
            assert len(engine._result_cache) == cache_size

    def test_remove_empty_node_list(self, indexed_project):
        """Test that removing with empty list does nothing."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            engine.build_index()

            # Populate cache
            engine.search("Calculator")
            cache_size = len(engine._result_cache)

            # Remove with empty list should not clear cache
            engine.remove_nodes_from_index([])

            # Cache should still be populated
            assert len(engine._result_cache) == cache_size

    def test_update_nonexistent_nodes(self, indexed_project):
        """Test updating index for nodes that don't exist."""
        _, db_path = indexed_project

        with Store(db_path) as store:
            engine = SearchEngine(store)
            engine.build_index()

            # This should not raise an error
            engine.update_index_for_nodes(["nonexistent:node"])

            # Search should still work
            results = engine.search("Calculator")
            assert len(results) > 0
