"""CLI commands for Contexto."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from contexto.graph import CodeGraph
from contexto.store import Store
from contexto.search import SearchEngine
from contexto.output import XMLFormatter

app = typer.Typer(
    name="contexto",
    help="A navigable graph of your Python codebase for LLMs",
    no_args_is_help=True,
)
console = Console()


@app.command()
def index(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project to index (default: current directory)",
    ),
    incremental: bool = typer.Option(
        False,
        "--incremental", "-i",
        help="Only update changed files",
    ),
) -> None:
    """Index a Python project and build the navigation graph."""
    project_path = (path or Path.cwd()).resolve()

    if not project_path.is_dir():
        console.print(f"[red]Error:[/red] {project_path} is not a directory")
        raise typer.Exit(1)

    db_path = project_path / ".contexto.db"

    if incremental and db_path.exists():
        console.print(f"Incremental indexing [bold]{project_path}[/bold]...")
        _incremental_index(project_path, db_path)
    else:
        console.print(f"Indexing [bold]{project_path}[/bold]...")
        _full_index(project_path, db_path)


def _full_index(project_path: Path, db_path: Path) -> None:
    """Perform a full index of the project."""
    # Build the graph
    graph = CodeGraph(project_path)
    graph.build()

    # Save to database using context manager
    with Store(db_path) as store:
        store.save_graph(graph)

        # Save file hashes for incremental updates
        for node in graph.nodes.values():
            if node.type == "file" and node.file_path:
                file_path = project_path / node.file_path
                if file_path.exists():
                    file_hash = Store.compute_file_hash(file_path)
                    store.save_file_hash(node.file_path, file_hash)

        # Build search index
        console.print("Building search index...")
        search_engine = SearchEngine(store)
        search_engine.build_index()

    # Print stats
    stats = graph.get_stats(".")
    console.print(Panel(
        f"[green]✓[/green] Indexed successfully!\n\n"
        f"  Files: {stats['files']}\n"
        f"  Classes: {stats['classes']}\n"
        f"  Functions: {stats['functions']}\n"
        f"  Methods: {stats['methods']}\n\n"
        f"Database: [dim]{db_path}[/dim]",
        title="Contexto",
    ))


def _incremental_index(project_path: Path, db_path: Path) -> None:
    """Perform an incremental index, only updating changed files."""
    with Store(db_path) as store:
        # Load existing graph
        graph = store.load_graph(project_path)
        indexed_files = store.get_indexed_files()

        # Find all current Python files
        current_files: set[str] = set()
        exclude_patterns = [
            "__pycache__", ".git", ".venv", "venv", "node_modules",
            ".pytest_cache", ".mypy_cache", "*.egg-info", "dist", "build"
        ]

        for py_file in project_path.rglob("*.py"):
            if any(py_file.match(f"**/{pattern}/**") or py_file.match(pattern)
                   for pattern in exclude_patterns):
                continue
            rel_path = str(py_file.relative_to(project_path))
            current_files.add(rel_path)

        files_added = 0
        files_updated = 0
        files_removed = 0

        # Check for new or modified files
        for rel_path in current_files:
            file_path = project_path / rel_path
            current_hash = Store.compute_file_hash(file_path)
            stored_hash = indexed_files.get(rel_path)

            if stored_hash is None:
                # New file
                parent_id = str(Path(rel_path).parent)
                if parent_id == ".":
                    parent_id = "."
                graph.add_single_file(file_path, rel_path, parent_id)
                store.save_file_hash(rel_path, current_hash)
                files_added += 1
            elif stored_hash != current_hash:
                # Modified file
                parent_id = str(Path(rel_path).parent)
                if parent_id == ".":
                    parent_id = "."
                graph.add_single_file(file_path, rel_path, parent_id)
                store.save_file_hash(rel_path, current_hash)
                files_updated += 1

        # Check for deleted files
        for rel_path in indexed_files:
            if rel_path not in current_files:
                store.delete_file_nodes(rel_path)
                files_removed += 1

        # Save updated graph
        store.save_graph(graph)

        # Rebuild search index
        console.print("Rebuilding search index...")
        search_engine = SearchEngine(store)
        search_engine.build_index()

    # Print stats
    stats = graph.get_stats(".")
    console.print(Panel(
        f"[green]✓[/green] Incremental index complete!\n\n"
        f"  Added: {files_added} files\n"
        f"  Updated: {files_updated} files\n"
        f"  Removed: {files_removed} files\n\n"
        f"  Total Files: {stats['files']}\n"
        f"  Classes: {stats['classes']}\n"
        f"  Functions: {stats['functions']}\n"
        f"  Methods: {stats['methods']}\n\n"
        f"Database: [dim]{db_path}[/dim]",
        title="Contexto",
    ))


@app.command()
def serve(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Start the MCP server for LLM integration."""
    project_path = (path or Path.cwd()).resolve()
    db_path = project_path / ".contexto.db"

    if not db_path.exists():
        console.print(
            f"[red]Error:[/red] No index found at {db_path}\n"
            "Run [bold]contexto index[/bold] first."
        )
        raise typer.Exit(1)

    # Import here to avoid loading mcp unless needed
    from contexto.mcp_server import run_server

    # Run the server
    asyncio.run(run_server(project_path))


@app.command(name="map")
def show_map(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Show the project map."""
    project_path = (path or Path.cwd()).resolve()
    db_path = project_path / ".contexto.db"

    if not db_path.exists():
        console.print(
            f"[red]Error:[/red] No index found at {db_path}\n"
            "Run [bold]contexto index[/bold] first."
        )
        raise typer.Exit(1)

    with Store(db_path) as store:
        formatter = XMLFormatter()

        root = store.get_node(".")
        if not root:
            console.print("[red]Error:[/red] No root node found")
            raise typer.Exit(1)

        children = store.get_children(".")
        child_stats = []

        for child in children:
            if child.type == "dir":
                stats = store.get_stats(child.id)
                child_stats.append((child.id, stats))

        output = formatter.format_map(
            root_name=root.name,
            root_path=str(project_path),
            stats=store.get_stats("."),
            children=child_stats,
        )

        console.print(output)


@app.command()
def expand(
    node_path: str = typer.Argument(
        ...,
        help="Path to expand (e.g., 'src/api' or 'src/api/users.py')",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--project", "-p",
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Expand a node to see its children."""
    project_path = (path or Path.cwd()).resolve()
    db_path = project_path / ".contexto.db"

    if not db_path.exists():
        console.print(
            f"[red]Error:[/red] No index found at {db_path}\n"
            "Run [bold]contexto index[/bold] first."
        )
        raise typer.Exit(1)

    with Store(db_path) as store:
        formatter = XMLFormatter()

        node = store.get_node(node_path)
        if not node:
            console.print(f"[red]Error:[/red] Node not found: {node_path}")
            raise typer.Exit(1)

        children = store.get_children(node_path)
        stats_map = {child.id: store.get_stats(child.id) for child in children}

        output = formatter.format_expand(node, children, stats_map)
        console.print(output)


@app.command()
def search(
    query: str = typer.Argument(
        ...,
        help="Search query",
    ),
    limit: int = typer.Option(
        10,
        "--limit", "-l",
        help="Maximum number of results",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--project", "-p",
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Search for entities by keyword."""
    project_path = (path or Path.cwd()).resolve()
    db_path = project_path / ".contexto.db"

    if not db_path.exists():
        console.print(
            f"[red]Error:[/red] No index found at {db_path}\n"
            "Run [bold]contexto index[/bold] first."
        )
        raise typer.Exit(1)

    with Store(db_path) as store:
        search_engine = SearchEngine(store)
        formatter = XMLFormatter()

        results = search_engine.search(query, limit=limit)
        output = formatter.format_search_results(query, results)

        console.print(output)


if __name__ == "__main__":
    app()
