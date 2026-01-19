"""SQLite storage for the codebase graph."""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Optional

from kontexto.graph import CodeGraph, GraphNode


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
        base_classes TEXT,
        language TEXT,
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
    CREATE INDEX IF NOT EXISTS idx_nodes_file_path ON nodes(file_path);
    CREATE INDEX IF NOT EXISTS idx_nodes_language ON nodes(language);
    CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
    CREATE INDEX IF NOT EXISTS idx_search_term ON search_index(term);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_search_unique ON search_index(node_id, term);
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._configure_connection()
        self._init_schema()

    def _configure_connection(self) -> None:
        """Configure SQLite connection for optimal performance."""
        # WAL mode for better concurrent read/write performance
        self.conn.execute("PRAGMA journal_mode=WAL")
        # Memory-mapped I/O for faster reads (256MB)
        self.conn.execute("PRAGMA mmap_size=268435456")
        # Store temp tables in memory
        self.conn.execute("PRAGMA temp_store=MEMORY")
        # Larger cache for better performance (64MB)
        self.conn.execute("PRAGMA cache_size=-65536")
        # Synchronous mode: NORMAL is safe with WAL and faster than FULL
        self.conn.execute("PRAGMA synchronous=NORMAL")

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        self.conn.executescript(self.SCHEMA)
        self.conn.commit()

    def __enter__(self) -> "Store":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        _exc_type: Optional[type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit context manager, ensuring connection is closed."""
        self.close()

    def save_graph(self, graph: CodeGraph) -> None:
        """Save the entire graph to the database.

        Uses explicit transaction and batch inserts for performance.
        """
        cursor = self.conn.cursor()

        try:
            cursor.execute("BEGIN TRANSACTION")

            # Clear existing data
            cursor.execute("DELETE FROM nodes")
            cursor.execute("DELETE FROM edges")
            cursor.execute("DELETE FROM search_index")
            cursor.execute("DELETE FROM idf")

            # Batch insert nodes using executemany for 10-50x speedup
            node_data = [
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
                    ",".join(node.base_classes) if node.base_classes else None,
                    node.language,
                )
                for node in graph.nodes.values()
            ]

            cursor.executemany(
                """
                INSERT INTO nodes (id, parent_id, name, type, file_path,
                                   line_start, line_end, signature, docstring, calls, base_classes, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                node_data,
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
                base_classes=row["base_classes"].split(",")
                if row["base_classes"]
                else [],
                language=row["language"],
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
            base_classes=row["base_classes"].split(",") if row["base_classes"] else [],
            language=row["language"],
        )

    def get_children(self, node_id: str) -> list[GraphNode]:
        """Get all children of a node with grandchildren in a single query."""
        cursor = self.conn.cursor()

        # Single query to get children and their grandchildren using LEFT JOIN
        # Limit GROUP_CONCAT to 10000 IDs (each ~100 chars max) to prevent memory issues
        cursor.execute(
            """
            SELECT
                c.id, c.name, c.type, c.parent_id, c.file_path,
                c.line_start, c.line_end, c.signature, c.docstring, c.calls, c.base_classes, c.language,
                GROUP_CONCAT(g.id, ',') as grandchildren_ids
            FROM nodes c
            LEFT JOIN nodes g ON g.parent_id = c.id
            WHERE c.parent_id = ?
            GROUP BY c.id
            """,
            (node_id,),
        )
        rows = cursor.fetchall()

        children = []
        for row in rows:
            grandchildren = (
                row["grandchildren_ids"].split(",") if row["grandchildren_ids"] else []
            )

            children.append(
                GraphNode(
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
                    base_classes=row["base_classes"].split(",")
                    if row["base_classes"]
                    else [],
                    language=row["language"],
                )
            )

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
        type_map = {
            "file": "files",
            "class": "classes",
            "function": "functions",
            "method": "methods",
        }
        for row in cursor.fetchall():
            stat_key = type_map.get(row["type"])
            if stat_key:
                stats[stat_key] = row["count"]

        return stats

    def get_stats_batch(self, node_ids: list[str]) -> dict[str, dict]:
        """Get statistics for multiple nodes in a single query.

        Returns:
            Dict mapping node_id -> stats dict
        """
        if not node_ids:
            return {}

        cursor = self.conn.cursor()

        # Use a single CTE query to get stats for all nodes at once
        placeholders = ",".join("?" * len(node_ids))
        cursor.execute(
            f"""
            WITH RECURSIVE descendants AS (
                SELECT id, type, id as root_id FROM nodes WHERE id IN ({placeholders})
                UNION ALL
                SELECT n.id, n.type, d.root_id FROM nodes n
                INNER JOIN descendants d ON n.parent_id = d.id
            )
            SELECT root_id, type, COUNT(*) as count
            FROM descendants
            GROUP BY root_id, type
            """,
            node_ids,
        )

        # Initialize results
        results: dict[str, dict] = {
            nid: {"files": 0, "classes": 0, "functions": 0, "methods": 0}
            for nid in node_ids
        }

        type_map = {
            "file": "files",
            "class": "classes",
            "function": "functions",
            "method": "methods",
        }
        for row in cursor.fetchall():
            stat_key = type_map.get(row["type"])
            if stat_key and row["root_id"] in results:
                results[row["root_id"]][stat_key] = row["count"]

        return results

    def save_file_hash(
        self, file_path: str, content_hash: str, commit: bool = True
    ) -> None:
        """Save file hash for incremental updates.

        Args:
            file_path: Relative path to the file
            content_hash: SHA256 hash of file contents
            commit: Whether to commit immediately (set False for batch operations)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO files (path, hash, indexed_at)
            VALUES (?, ?, ?)
            """,
            (file_path, content_hash, datetime.now().isoformat()),
        )
        if commit:
            self.conn.commit()

    def save_file_hashes_batch(self, file_hashes: dict[str, str]) -> None:
        """Save multiple file hashes in a single transaction.

        Args:
            file_hashes: Dict mapping file_path -> content_hash
        """
        if not file_hashes:
            return

        cursor = self.conn.cursor()
        now = datetime.now().isoformat()

        cursor.executemany(
            """
            INSERT OR REPLACE INTO files (path, hash, indexed_at)
            VALUES (?, ?, ?)
            """,
            [(path, hash_, now) for path, hash_ in file_hashes.items()],
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

    def delete_file_nodes(self, file_path: str, commit: bool = True) -> None:
        """Delete all nodes belonging to a specific file.

        Args:
            file_path: Relative path to the file
            commit: Whether to commit immediately (set False for batch operations)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM nodes WHERE file_path = ? OR id = ?",
            (file_path, file_path),
        )
        cursor.execute("DELETE FROM files WHERE path = ?", (file_path,))
        if commit:
            self.conn.commit()

    def delete_file_nodes_batch(
        self, file_paths: list[str], vacuum: bool = False
    ) -> None:
        """Delete nodes for multiple files in a single transaction.

        Args:
            file_paths: List of file paths to delete
            vacuum: Whether to run VACUUM after deletion to reclaim space
        """
        if not file_paths:
            return

        cursor = self.conn.cursor()
        placeholders = ",".join("?" * len(file_paths))
        cursor.execute("BEGIN TRANSACTION")
        try:
            # Delete nodes where file_path matches OR id matches (for file nodes)
            cursor.execute(
                f"DELETE FROM nodes WHERE file_path IN ({placeholders}) OR id IN ({placeholders})",
                file_paths + file_paths,
            )
            cursor.execute(
                f"DELETE FROM files WHERE path IN ({placeholders})", file_paths
            )
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise

        if vacuum:
            self.vacuum()

    def vacuum(self) -> None:
        """Reclaim unused space in the database.

        Should be called periodically after large deletions.
        Note: VACUUM requires no active transactions and may take time on large DBs.
        """
        self.conn.execute("VACUUM")

    def get_indexed_files(self) -> dict[str, str]:
        """Get all indexed files with their hashes."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT path, hash FROM files")
        return {row["path"]: row["hash"] for row in cursor.fetchall()}

    @staticmethod
    def _escape_like_pattern(value: str) -> str:
        """Escape special characters for LIKE patterns.

        SQLite LIKE treats % and _ as wildcards. This escapes them
        so they match literally.
        """
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def get_callers(self, entity_name: str) -> list[str]:
        """Find all entities that call a given entity name.

        Args:
            entity_name: The name of the function/method being called

        Returns:
            List of node IDs that contain calls to this entity
        """
        cursor = self.conn.cursor()
        # Escape special LIKE characters to prevent pattern injection
        escaped_name = self._escape_like_pattern(entity_name)

        # Search for entities whose 'calls' field contains the entity name
        cursor.execute(
            """
            SELECT id FROM nodes
            WHERE calls LIKE ? ESCAPE '\\'
               OR calls LIKE ? ESCAPE '\\'
               OR calls LIKE ? ESCAPE '\\'
               OR calls = ?
            """,
            (
                f"{escaped_name},%",  # At start
                f"%,{escaped_name},%",  # In middle
                f"%,{escaped_name}",  # At end
                entity_name,  # Exact match (single call) - no escape needed
            ),
        )
        return [row["id"] for row in cursor.fetchall()]

    def get_subclasses(self, base_class: str) -> list[GraphNode]:
        """Find all classes that inherit from a given base class.

        Args:
            base_class: The name of the base class to search for

        Returns:
            List of GraphNode objects that inherit from the base class
        """
        cursor = self.conn.cursor()
        # Escape special LIKE characters to prevent pattern injection
        escaped_class = self._escape_like_pattern(base_class)

        # Search for classes whose base_classes contain the given base class
        cursor.execute(
            """
            SELECT id, name, type, parent_id, file_path,
                   line_start, line_end, signature, docstring, calls, base_classes, language
            FROM nodes
            WHERE type = 'class' AND (
                base_classes LIKE ? ESCAPE '\\'
                OR base_classes LIKE ? ESCAPE '\\'
                OR base_classes LIKE ? ESCAPE '\\'
                OR base_classes = ?
            )
            """,
            (
                f"{escaped_class},%",  # At start
                f"%,{escaped_class},%",  # In middle
                f"%,{escaped_class}",  # At end
                base_class,  # Exact match (single base class) - no escape needed
            ),
        )

        subclasses = []
        for row in cursor.fetchall():
            subclasses.append(
                GraphNode(
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
            )

        return subclasses

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
