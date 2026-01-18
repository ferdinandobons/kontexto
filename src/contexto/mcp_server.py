"""MCP server exposing codebase navigation tools."""

from pathlib import Path
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from contexto.store import Store
from contexto.output import XMLFormatter
from contexto.search import SearchEngine


class ContextoServer:
    """MCP server for codebase navigation."""

    def __init__(self, project_path: Path):
        self.project_path = project_path.resolve()
        self.db_path = project_path / ".contexto.db"

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"No index found at {self.db_path}. Run 'contexto index' first."
            )

        self.store = Store(self.db_path)
        self.search_engine = SearchEngine(self.store)
        self.formatter = XMLFormatter()
        self.server = Server("contexto")

        self._register_tools()

    def _register_tools(self) -> None:
        """Register MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="map",
                    description="Get a compact map of the project structure",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="expand",
                    description="Expand a node to see its children (directories, files, classes, methods)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to expand (e.g., 'src/api' or 'src/api/users.py')",
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="inspect",
                    description="Get detailed info about an entity (signature, docstring, calls, called_by)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Entity path (e.g., 'src/api/users.py:UserController.get_user')",
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="read",
                    description="Read source code from a file or specific line range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path to read",
                            },
                            "start_line": {
                                "type": "integer",
                                "description": "Starting line number (optional)",
                            },
                            "end_line": {
                                "type": "integer",
                                "description": "Ending line number (optional)",
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="search",
                    description="Search for entities by keyword (searches names, docstrings, signatures)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 10)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                if name == "map":
                    result = self._handle_map()
                elif name == "expand":
                    result = self._handle_expand(arguments["path"])
                elif name == "inspect":
                    result = self._handle_inspect(arguments["path"])
                elif name == "read":
                    result = self._handle_read(
                        arguments["path"],
                        arguments.get("start_line"),
                        arguments.get("end_line"),
                    )
                elif name == "search":
                    result = self._handle_search(
                        arguments["query"],
                        arguments.get("limit", 10),
                    )
                else:
                    result = f"<error>Unknown tool: {name}</error>"

                return [TextContent(type="text", text=result)]

            except Exception as e:
                return [TextContent(type="text", text=f"<error>{str(e)}</error>")]

    def _handle_map(self) -> str:
        """Handle map() tool call."""
        root = self.store.get_node(".")
        if not root:
            return "<error>No root node found</error>"

        children = self.store.get_children(".")
        child_stats = []

        for child in children:
            if child.type == "dir":
                stats = self.store.get_stats(child.id)
                child_stats.append((child.id, stats))

        return self.formatter.format_map(
            root_name=root.name,
            root_path=str(self.project_path),
            stats=self.store.get_stats("."),
            children=child_stats,
        )

    def _handle_expand(self, path: str) -> str:
        """Handle expand() tool call."""
        node = self.store.get_node(path)
        if not node:
            return f"<error>Node not found: {path}</error>"

        children = self.store.get_children(path)

        # Get stats for each child
        stats_map = {}
        for child in children:
            stats_map[child.id] = self.store.get_stats(child.id)

        return self.formatter.format_expand(node, children, stats_map)

    def _handle_inspect(self, path: str) -> str:
        """Handle inspect() tool call."""
        node = self.store.get_node(path)
        if not node:
            return f"<error>Node not found: {path}</error>"

        # Find calls_to relationships (what this entity calls)
        calls_to = node.calls if node.calls else []

        # Find called_by relationships (what calls this entity)
        called_by = self.store.get_callers(node.name)
        # Filter out self-references
        called_by = [caller for caller in called_by if caller != path]

        return self.formatter.format_inspect(node, calls_to, called_by)

    def _handle_read(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Handle read() tool call."""
        # Extract file path if this is an entity path
        file_path = path.split(":")[0] if ":" in path else path

        full_path = (self.project_path / file_path).resolve()

        # Security: Prevent path traversal attacks
        try:
            full_path.relative_to(self.project_path)
        except ValueError:
            return f"<error>Access denied: path outside project directory</error>"

        if not full_path.exists():
            return f"<error>File not found: {file_path}</error>"

        if not full_path.is_file():
            return f"<error>Not a file: {file_path}</error>"

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"<error>Error reading file: {e}</error>"

        lines = content.split("\n")

        if start_line is not None or end_line is not None:
            start = (start_line or 1) - 1
            end = end_line or len(lines)
            lines = lines[start:end]
            actual_start = (start_line or 1)
        else:
            actual_start = 1

        return self.formatter.format_read(
            file_path=file_path,
            content="\n".join(lines),
            start_line=actual_start,
        )

    def _handle_search(self, query: str, limit: int = 10) -> str:
        """Handle search() tool call."""
        results = self.search_engine.search(query, limit=limit)
        return self.formatter.format_search_results(query, results)

    async def run(self) -> None:
        """Run the MCP server."""
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )
        finally:
            self.store.close()

    def close(self) -> None:
        """Clean up resources."""
        self.store.close()


async def run_server(project_path: Path) -> None:
    """Entry point to run the MCP server."""
    server = ContextoServer(project_path)
    try:
        await server.run()
    except Exception:
        server.close()
        raise
