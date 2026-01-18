"""TF-IDF search engine for the codebase graph."""

import math
import re
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contexto.store import Store
    from contexto.graph import GraphNode


class SearchEngine:
    """TF-IDF based search engine for code entities."""

    def __init__(self, store: "Store"):
        self.store = store
        self._idf_cache: dict[str, float] = {}
        self._total_docs = 0

    def build_index(self) -> None:
        """Build the TF-IDF index for all searchable entities."""
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

        # Calculate and store IDF
        for term, df in doc_freq.items():
            idf = math.log((self._total_docs + 1) / (df + 1)) + 1
            cursor.execute(
                "INSERT INTO idf (term, idf) VALUES (?, ?)",
                (term, idf),
            )
            self._idf_cache[term] = idf

        # Store TF values
        for node_id, terms in node_terms.items():
            max_tf = max(terms.values()) if terms else 1

            for term, count in terms.items():
                # Normalized TF
                tf = count / max_tf
                cursor.execute(
                    "INSERT INTO search_index (node_id, term, tf) VALUES (?, ?, ?)",
                    (node_id, term, tf),
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
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Load IDF cache if empty
        if not self._idf_cache:
            self._load_idf_cache()

        cursor = self.store.conn.cursor()

        # Calculate scores for each matching document
        scores: dict[str, float] = defaultdict(float)

        for term in query_terms:
            idf = self._idf_cache.get(term, 0)
            if idf == 0:
                continue

            cursor.execute(
                "SELECT node_id, tf FROM search_index WHERE term = ?",
                (term,),
            )

            for row in cursor.fetchall():
                tf_idf = row["tf"] * idf
                scores[row["node_id"]] += tf_idf

        # Sort by score and get top results
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        # Fetch nodes for results
        results = []

        # Calculate max possible score for normalization
        if self._idf_cache:
            max_idf = max(self._idf_cache.values())
        else:
            max_idf = 1.0
        max_possible = len(query_terms) * max_idf if query_terms else 1.0

        for node_id, score in sorted_results:
            node = self.store.get_node(node_id)
            if node:
                # Normalize score to 0-1 range
                normalized_score = min(score / max_possible, 1.0) if max_possible > 0 else 0.0
                results.append((node, normalized_score))

        return results

    def _load_idf_cache(self) -> None:
        """Load IDF values from database."""
        cursor = self.store.conn.cursor()
        cursor.execute("SELECT term, idf FROM idf")

        for row in cursor.fetchall():
            self._idf_cache[row["term"]] = row["idf"]

        cursor.execute("SELECT COUNT(*) FROM nodes WHERE type IN ('function', 'method', 'class')")
        self._total_docs = cursor.fetchone()[0]

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

        # Split camelCase
        result = []
        for part in parts:
            # Insert space before uppercase letters
            split = re.sub(r"([A-Z])", r" \1", part).split()
            result.extend(split)

        return [p.lower() for p in result if p]

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into searchable terms."""
        # Convert to lowercase and split on non-alphanumeric
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text.lower())

        # Filter short words and common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "self", "this", "that", "these", "those", "def", "class",
            "return", "if", "else", "elif", "try", "except", "finally",
            "and", "or", "not", "none", "true", "false",
        }

        return [w for w in words if len(w) > 2 and w not in stop_words]
