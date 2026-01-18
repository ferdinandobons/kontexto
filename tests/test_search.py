"""Tests for the search engine."""

import pytest

from contexto.graph import CodeGraph
from contexto.store import Store
from contexto.search import SearchEngine


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
