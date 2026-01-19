"""TF-IDF search engine for the codebase graph."""

import math
import re
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kontexto.store import Store
    from kontexto.graph import GraphNode

# Pre-compiled regex patterns for performance (2x faster tokenization)
_TOKENIZE_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9]*")
_CAMELCASE_PATTERN = re.compile(r"([A-Z])")

# Stop words set - defined at module level to avoid recreation on every tokenize call
_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "self",
        "this",
        "that",
        "these",
        "those",
        "def",
        "class",
        "return",
        "if",
        "else",
        "elif",
        "try",
        "except",
        "finally",
        "and",
        "or",
        "not",
        "none",
        "true",
        "false",
    }
)


class SearchEngine:
    """TF-IDF based search engine for code entities."""

    def __init__(self, store: "Store"):
        self.store = store
        self._idf_cache: dict[str, float] = {}
        self._total_docs = 0
        self._result_cache: dict[str, list[tuple["GraphNode", float]]] = {}
        self._idf_loaded = False

    def build_index(self) -> None:
        """Build the TF-IDF index for all searchable entities."""
        # Clear caches when rebuilding index
        self._result_cache.clear()
        self._idf_cache.clear()
        self._idf_loaded = False

        cursor = self.store.conn.cursor()

        # Clear existing index
        cursor.execute("DELETE FROM search_index")
        cursor.execute("DELETE FROM idf")

        # Get all searchable nodes (functions, methods, classes)
        cursor.execute(
            """
            SELECT id, name, signature, docstring
            FROM nodes
            WHERE type IN ('function', 'method', 'class')
            """
        )
        nodes = cursor.fetchall()
        self._total_docs = len(nodes)

        if not nodes:
            self.store.conn.commit()
            return

        # Count document frequency for each term
        doc_freq: dict[str, int] = defaultdict(int)
        node_terms: dict[str, dict[str, int]] = {}  # node_id -> {term: count}

        for node in nodes:
            node_id = node["id"]
            text = self._get_searchable_text(node)
            terms = self._tokenize(text)

            # Count term frequency in this document
            term_counts: dict[str, int] = defaultdict(int)
            for term in terms:
                term_counts[term] += 1

            node_terms[node_id] = dict(term_counts)

            # Count document frequency
            for term in set(terms):
                doc_freq[term] += 1

        # Batch insert IDF values using executemany for 10-50x speedup
        idf_data = []
        for term, df in doc_freq.items():
            idf = math.log((self._total_docs + 1) / (df + 1)) + 1
            idf_data.append((term, idf))
            self._idf_cache[term] = idf

        cursor.executemany("INSERT INTO idf (term, idf) VALUES (?, ?)", idf_data)

        # Batch insert TF values
        tf_data = []
        for node_id, term_counts in node_terms.items():
            max_tf = max(term_counts.values()) if term_counts else 1

            for term, count in term_counts.items():
                # Normalized TF
                tf = count / max_tf
                tf_data.append((node_id, term, tf))

        cursor.executemany(
            "INSERT OR REPLACE INTO search_index (node_id, term, tf) VALUES (?, ?, ?)",
            tf_data,
        )

        self.store.conn.commit()

    def update_index_for_nodes(
        self, node_ids: list[str], total_docs_changed: int = 0
    ) -> None:
        """Update the search index incrementally for specific nodes.

        Args:
            node_ids: List of node IDs that were added or modified
            total_docs_changed: Net change in document count (positive for additions, negative for deletions)
        """
        if not node_ids:
            return

        # Clear search result cache since index is changing
        self._result_cache.clear()

        cursor = self.store.conn.cursor()

        # Remove old entries for these nodes
        placeholders = ",".join("?" * len(node_ids))
        cursor.execute(
            f"DELETE FROM search_index WHERE node_id IN ({placeholders})", node_ids
        )

        # Get the nodes to index
        cursor.execute(
            f"""
            SELECT id, name, signature, docstring
            FROM nodes
            WHERE id IN ({placeholders}) AND type IN ('function', 'method', 'class')
            """,
            node_ids,
        )
        nodes = cursor.fetchall()

        if not nodes:
            self.store.conn.commit()
            return

        # Load current IDF cache if needed
        if not self._idf_cache:
            self._load_idf_cache()

        # Update total docs count
        self._total_docs += total_docs_changed

        # Get current document frequencies for terms we're updating
        # Track which terms are affected
        affected_terms: set[str] = set()
        node_terms: dict[str, dict[str, int]] = {}

        for node in nodes:
            node_id = node["id"]
            text = self._get_searchable_text(node)
            terms = self._tokenize(text)

            term_counts: dict[str, int] = defaultdict(int)
            for term in terms:
                term_counts[term] += 1
                affected_terms.add(term)

            node_terms[node_id] = dict(term_counts)

        # For incremental updates, we use existing IDF values
        # Full IDF recalculation is expensive, so we only do it if >5% of docs changed
        should_recalculate_idf = (
            abs(total_docs_changed) > 0.05 * self._total_docs
            if self._total_docs > 0
            else False
        )

        if should_recalculate_idf:
            # Recalculate IDF for affected terms
            for term in affected_terms:
                cursor.execute(
                    "SELECT COUNT(DISTINCT node_id) FROM search_index WHERE term = ?",
                    (term,),
                )
                df = cursor.fetchone()[0]
                # Add 1 for the new nodes we're about to add
                df += sum(1 for nt in node_terms.values() if term in nt)

                new_idf = math.log((self._total_docs + 1) / (df + 1)) + 1
                self._idf_cache[term] = new_idf

                # Update IDF in database
                cursor.execute(
                    "INSERT OR REPLACE INTO idf (term, idf) VALUES (?, ?)",
                    (term, new_idf),
                )

        # Insert TF values for new/updated nodes
        tf_data = []
        for node_id, term_counts in node_terms.items():
            max_tf = max(term_counts.values()) if term_counts else 1

            for term, count in term_counts.items():
                tf = count / max_tf
                tf_data.append((node_id, term, tf))

                # Ensure we have IDF for new terms
                if term not in self._idf_cache:
                    # Approximate IDF for new terms
                    new_idf = math.log((self._total_docs + 1) / 2) + 1  # Assume df=1
                    self._idf_cache[term] = new_idf
                    cursor.execute(
                        "INSERT OR REPLACE INTO idf (term, idf) VALUES (?, ?)",
                        (term, new_idf),
                    )

        cursor.executemany(
            "INSERT OR REPLACE INTO search_index (node_id, term, tf) VALUES (?, ?, ?)",
            tf_data,
        )

        self.store.conn.commit()

    def remove_nodes_from_index(self, node_ids: list[str]) -> None:
        """Remove nodes from the search index.

        Args:
            node_ids: List of node IDs to remove from the index
        """
        if not node_ids:
            return

        # Clear search result cache
        self._result_cache.clear()

        cursor = self.store.conn.cursor()
        placeholders = ",".join("?" * len(node_ids))
        cursor.execute(
            f"DELETE FROM search_index WHERE node_id IN ({placeholders})", node_ids
        )
        self.store.conn.commit()

    def search(self, query: str, limit: int = 10) -> list[tuple["GraphNode", float]]:
        """Search for entities matching the query.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of (node, score) tuples sorted by relevance
        """
        # Check cache first
        cache_key = f"{query}:{limit}"
        if cache_key in self._result_cache:
            return self._result_cache[cache_key]

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Load IDF cache if not loaded yet
        if not self._idf_loaded:
            self._load_idf_cache()

        # Filter to terms that exist in our index
        valid_terms = [(term, self._idf_cache.get(term, 0)) for term in query_terms]
        valid_terms = [(term, idf) for term, idf in valid_terms if idf > 0]

        if not valid_terms:
            return []

        cursor = self.store.conn.cursor()

        # Single query to get all matching TF values at once
        placeholders = ",".join("?" * len(valid_terms))
        term_list = [term for term, _ in valid_terms]

        cursor.execute(
            f"""
            SELECT node_id, term, tf
            FROM search_index
            WHERE term IN ({placeholders})
            """,
            term_list,
        )

        # Build IDF lookup for valid terms
        idf_lookup = {term: idf for term, idf in valid_terms}

        # Calculate scores
        scores: dict[str, float] = defaultdict(float)
        for row in cursor.fetchall():
            tf_idf = row["tf"] * idf_lookup[row["term"]]
            scores[row["node_id"]] += tf_idf

        # Sort by score and get top results
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]

        if not sorted_results:
            return []

        # Fetch all result nodes in a single query
        node_ids = [node_id for node_id, _ in sorted_results]
        placeholders = ",".join("?" * len(node_ids))

        cursor.execute(
            f"""
            SELECT id, name, type, parent_id, file_path,
                   line_start, line_end, signature, docstring, calls, base_classes, language
            FROM nodes
            WHERE id IN ({placeholders})
            """,
            node_ids,
        )

        # Build node lookup
        from kontexto.graph import GraphNode

        node_lookup = {}
        for row in cursor.fetchall():
            node_lookup[row["id"]] = GraphNode(
                id=row["id"],
                name=row["name"],
                type=row["type"],
                parent_id=row["parent_id"],
                file_path=row["file_path"],
                line_start=row["line_start"],
                line_end=row["line_end"],
                signature=row["signature"],
                docstring=row["docstring"],
                calls=row["calls"].split(",") if row["calls"] else [],
                base_classes=row["base_classes"].split(",")
                if row["base_classes"]
                else [],
                language=row["language"],
            )

        # Calculate max possible score for normalization
        if self._idf_cache:
            max_idf = max(self._idf_cache.values())
        else:
            max_idf = 1.0
        max_possible = len(query_terms) * max_idf if query_terms else 1.0

        # Build results in score order
        results = []
        for node_id, score in sorted_results:
            node = node_lookup.get(node_id)
            if node:
                normalized_score = (
                    min(score / max_possible, 1.0) if max_possible > 0 else 0.0
                )
                results.append((node, normalized_score))

        # Cache the results
        self._result_cache[cache_key] = results

        return results

    def _load_idf_cache(self) -> None:
        """Load IDF values from database."""
        cursor = self.store.conn.cursor()
        cursor.execute("SELECT term, idf FROM idf")

        for row in cursor.fetchall():
            self._idf_cache[row["term"]] = row["idf"]

        cursor.execute(
            "SELECT COUNT(*) FROM nodes WHERE type IN ('function', 'method', 'class')"
        )
        self._total_docs = cursor.fetchone()[0]
        self._idf_loaded = True

    def _get_searchable_text(self, node) -> str:
        """Extract searchable text from a node."""
        parts = []

        if node["name"]:
            # Split camelCase and snake_case
            name = node["name"]
            parts.append(name)
            parts.extend(self._split_identifier(name))

        if node["signature"]:
            parts.append(node["signature"])

        if node["docstring"]:
            parts.append(node["docstring"])

        return " ".join(parts)

    def _split_identifier(self, name: str) -> list[str]:
        """Split an identifier into words (camelCase, snake_case)."""
        # Split on underscores
        parts = name.split("_")

        # Split camelCase using pre-compiled pattern
        result = []
        for part in parts:
            # Insert space before uppercase letters
            split = _CAMELCASE_PATTERN.sub(r" \1", part).split()
            result.extend(split)

        return [p.lower() for p in result if p]

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into searchable terms."""
        # Use pre-compiled pattern for 2x speedup
        words = _TOKENIZE_PATTERN.findall(text.lower())

        # Filter short words and common stop words (using module-level constant)
        return [w for w in words if len(w) > 2 and w not in _STOP_WORDS]
