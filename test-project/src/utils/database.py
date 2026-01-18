"""Database utilities."""

import sqlite3
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager


class DatabaseConnection:
    """SQLite database connection wrapper."""

    def __init__(self, db_path: str | Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Establish database connection."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the active connection."""
        if not self._conn:
            self.connect()
        return self._conn

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute query and return first row.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            First row as dict, or None.
        """
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute query and return all rows.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            List of rows as dicts.
        """
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Execute a write query.

        Args:
            sql: SQL statement.
            params: Statement parameters.

        Returns:
            Last row ID for INSERT, or affected row count.
        """
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        self.connection.commit()

        if sql.strip().upper().startswith("INSERT"):
            return cursor.lastrowid
        return cursor.rowcount

    def execute_many(self, sql: str, params_list: list[tuple]) -> int:
        """Execute statement for multiple parameter sets.

        Args:
            sql: SQL statement.
            params_list: List of parameter tuples.

        Returns:
            Total affected row count.
        """
        cursor = self.connection.cursor()
        cursor.executemany(sql, params_list)
        self.connection.commit()
        return cursor.rowcount

    @contextmanager
    def transaction(self):
        """Context manager for transactions.

        Usage:
            with db.transaction():
                db.execute(...)
                db.execute(...)
        """
        try:
            yield
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise


class ConnectionPool:
    """Simple connection pool for database connections."""

    def __init__(self, db_path: str | Path, max_connections: int = 10):
        """Initialize pool.

        Args:
            db_path: Database path.
            max_connections: Maximum pool size.
        """
        self.db_path = Path(db_path)
        self.max_connections = max_connections
        self._available: list[DatabaseConnection] = []
        self._in_use: set[DatabaseConnection] = set()

    def acquire(self) -> DatabaseConnection:
        """Get a connection from the pool.

        Returns:
            Available database connection.

        Raises:
            RuntimeError: If pool is exhausted.
        """
        if self._available:
            conn = self._available.pop()
        elif len(self._in_use) < self.max_connections:
            conn = DatabaseConnection(self.db_path)
            conn.connect()
        else:
            raise RuntimeError("Connection pool exhausted")

        self._in_use.add(conn)
        return conn

    def release(self, conn: DatabaseConnection) -> None:
        """Return a connection to the pool."""
        if conn in self._in_use:
            self._in_use.remove(conn)
            self._available.append(conn)

    def close_all(self) -> None:
        """Close all connections."""
        for conn in self._available:
            conn.close()
        for conn in self._in_use:
            conn.close()
        self._available.clear()
        self._in_use.clear()

    @contextmanager
    def connection(self):
        """Context manager for acquiring connection.

        Usage:
            with pool.connection() as db:
                db.query_one(...)
        """
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)
