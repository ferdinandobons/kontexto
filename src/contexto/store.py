"""SQLite storage for the codebase graph."""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Optional

from contexto.graph import CodeGraph, GraphNode


class Store:
    """SQLite-based persistence for the codebase graph.

    Can be used as a context manager:
        with Store(db_path) as store:
            store.save_graph(graph)
    """

    SCHEMA = """
    -- Nodes of the graph
    CREATE TABLE IF NOT EXISTS nodes (
        id TEXT PRIMARY KEY,
        parent_id TEXT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        file_path TEXT,
        line_start INTEGER,
        line_end INTEGER,
        signature TEXT,
        docstring TEXT,
        calls TEXT,
        FOREIGN KEY (parent_id) REFERENCES nodes(id)
    );

    -- Edges for relationships
    CREATE TABLE IF NOT EXISTS edges (
        source_id TEXT,
        target_id TEXT,
        relation TEXT,
        PRIMARY KEY (source_id, target_id, relation)
    );

    -- TF-IDF search index
    CREATE TABLE IF NOT EXISTS search_index (
        node_id TEXT,
        term TEXT,
        tf REAL,
        FOREIGN KEY (node_id) REFERENCES nodes(id)
    );

    -- Global IDF values
    CREATE TABLE IF NOT EXISTS idf (
        term TEXT PRIMARY KEY,
        idf REAL
    );

    -- File metadata for incremental updates
    CREATE TABLE IF NOT EXISTS files (
        path TEXT PRIMARY KEY,
        hash TEXT,
        indexed_at TEXT
    );

    -- Performance indexes
    CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id);
    CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
    CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
    CREATE INDEX IF NOT EXISTS idx_search_term ON search_index(term);
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        self.conn.executescript(self.SCHEMA)
        self.conn.commit()

    def __enter__(self) -> "Store":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit context manager, ensuring connection is closed."""
        self.close()

    def save_graph(self, graph: CodeGraph) -> None:
        """Save the entire graph to the database.

        Uses explicit transaction to ensure atomicity.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("BEGIN TRANSACTION")

            # Clear existing data
            cursor.execute("DELETE FROM nodes")
            cursor.execute("DELETE FROM edges")
            cursor.execute("DELETE FROM search_index")
            cursor.execute("DELETE FROM idf")

            # Insert nodes
            for node in graph.nodes.values():
                cursor.execute(
                    """
                    INSERT INTO nodes (id, parent_id, name, type, file_path,
                                       line_start, line_end, signature, docstring, calls)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.id,
                        node.parent_id,
                        node.name,
                        node.type,
                        node.file_path,
                        node.line_start,
                        node.line_end,
                        node.signature,
                        node.docstring,
                        ",".join(node.calls) if node.calls else None,
                    ),
                )

            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    def load_graph(self, root_path: Path) -> CodeGraph:
        """Load the graph from the database."""
        graph = CodeGraph(root_path)
        cursor = self.conn.cursor()

        cursor.execute("SELECT * FROM nodes")
        rows = cursor.fetchall()

        for row in rows:
            node = GraphNode(
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
            )
            graph.nodes[node.id] = node

        # Rebuild children_ids
        for node in graph.nodes.values():
            if node.parent_id and node.parent_id in graph.nodes:
                graph.nodes[node.parent_id].children_ids.append(node.id)

        return graph

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a single node by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Get children
        cursor.execute("SELECT id FROM nodes WHERE parent_id = ?", (node_id,))
        children = [r["id"] for r in cursor.fetchall()]

        return GraphNode(
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
            children_ids=children,
        )

    def get_children(self, node_id: str) -> list[GraphNode]:
        """Get all children of a node."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nodes WHERE parent_id = ?", (node_id,))
        rows = cursor.fetchall()

        children = []
        for row in rows:
            # Get grandchildren count for each child
            cursor.execute("SELECT id FROM nodes WHERE parent_id = ?", (row["id"],))
            grandchildren = [r["id"] for r in cursor.fetchall()]

            children.append(GraphNode(
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
                children_ids=grandchildren,
            ))

        return children

    def get_stats(self, node_id: str = ".") -> dict:
        """Get statistics for a node and its descendants."""
        cursor = self.conn.cursor()

        # Get all descendant IDs using recursive CTE
        cursor.execute(
            """
            WITH RECURSIVE descendants AS (
                SELECT id, type FROM nodes WHERE id = ?
                UNION ALL
                SELECT n.id, n.type FROM nodes n
                INNER JOIN descendants d ON n.parent_id = d.id
            )
            SELECT type, COUNT(*) as count FROM descendants GROUP BY type
            """,
            (node_id,),
        )

        stats = {"files": 0, "classes": 0, "functions": 0, "methods": 0}
        type_map = {"file": "files", "class": "classes", "function": "functions", "method": "methods"}
        for row in cursor.fetchall():
            stat_key = type_map.get(row["type"])
            if stat_key:
                stats[stat_key] = row["count"]

        return stats

    def save_file_hash(self, file_path: str, content_hash: str) -> None:
        """Save file hash for incremental updates."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO files (path, hash, indexed_at)
            VALUES (?, ?, ?)
            """,
            (file_path, content_hash, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get stored hash for a file."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT hash FROM files WHERE path = ?", (file_path,))
        row = cursor.fetchone()
        return row["hash"] if row else None

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute hash of a file's contents using SHA256."""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def delete_file_nodes(self, file_path: str) -> None:
        """Delete all nodes belonging to a specific file."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM nodes WHERE file_path = ? OR id = ?",
            (file_path, file_path),
        )
        cursor.execute("DELETE FROM files WHERE path = ?", (file_path,))
        self.conn.commit()

    def get_indexed_files(self) -> dict[str, str]:
        """Get all indexed files with their hashes."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT path, hash FROM files")
        return {row["path"]: row["hash"] for row in cursor.fetchall()}

    def get_callers(self, entity_name: str) -> list[str]:
        """Find all entities that call a given entity name.

        Args:
            entity_name: The name of the function/method being called

        Returns:
            List of node IDs that contain calls to this entity
        """
        cursor = self.conn.cursor()
        # Search for entities whose 'calls' field contains the entity name
        cursor.execute(
            """
            SELECT id FROM nodes
            WHERE calls LIKE ? OR calls LIKE ? OR calls LIKE ? OR calls = ?
            """,
            (
                f"{entity_name},%",  # At start
                f"%,{entity_name},%",  # In middle
                f"%,{entity_name}",  # At end
                entity_name,  # Exact match (single call)
            ),
        )
        return [row["id"] for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
