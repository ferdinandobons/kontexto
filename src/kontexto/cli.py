"""CLI commands for Kontexto."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from kontexto.graph import CodeGraph, GraphNode
from kontexto.store import Store
from kontexto.search import SearchEngine
from kontexto.output import JsonFormatter
from kontexto.parsers import get_registry, DEFAULT_EXCLUDE_PATTERNS

HELP_TEXT = """
A CLI tool to explore codebases. Designed for LLMs and coding agents.
Supports: Python, JavaScript/TypeScript, Go, Rust, Java.
All output is JSON for easy parsing.

WORKFLOW FOR LLMs:
  1. kontexto index          # First, index the project (run once)
  2. kontexto map            # Get project overview
  3. kontexto expand <path>  # Drill into directories or files
  4. kontexto search <query> # Find code by keyword
  5. kontexto inspect <entity> # See entity details and call relationships
  6. kontexto hierarchy <class> # Find subclasses
  7. kontexto read <file> [start] [end] # Read source code

EXAMPLES:
  kontexto index                    # Index current directory
  kontexto map                      # Show project structure
  kontexto expand src/api           # List files in directory
  kontexto expand src/api/users.py  # Show classes/functions in file
  kontexto search "authentication"  # Find auth-related code
  kontexto inspect src/api/users.py:UserController.get_user
  kontexto hierarchy BaseModel      # Find all BaseModel subclasses
  kontexto read src/api/users.py 10 50  # Read lines 10-50

OUTPUT FORMAT:
  All commands return JSON with a "command" field identifying the response type.
  Entities include: id, name, type, language, file_path, line_start, line_end,
  signature, docstring, calls (functions called), base_classes (for classes).
"""

app = typer.Typer(
    name="kontexto",
    help=HELP_TEXT,
    no_args_is_help=True,
    add_completion=False,  # Remove shell completion options (not useful for LLMs)
)
console = Console()


def _get_db_path(project_path: Path) -> Path:
    """Get the database path for a project."""
    return project_path / ".kontexto" / "index.db"


def _check_index_exists(db_path: Path) -> None:
    """Check if index exists, raise error if not."""
    if not db_path.exists():
        console.print(
            f"[red]Error:[/red] No index found at {db_path}\n"
            "Run [bold]kontexto index[/bold] first."
        )
        raise typer.Exit(1)


@app.command()
def index(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project to index (default: current directory)",
    ),
    incremental: bool = typer.Option(
        False,
        "--incremental",
        "-i",
        help="Only update changed files (faster for large projects)",
    ),
) -> None:
    """Index a project. Run this first before other commands.

    Supports: Python, JavaScript/TypeScript, Go, Rust, Java.
    Creates .kontexto/index.db with: file structure, classes, functions,
    methods, signatures, docstrings, call relationships, and search index.
    Use -i for incremental updates after the first full index.
    """
    project_path = (path or Path.cwd()).resolve()

    if not project_path.is_dir():
        console.print(f"[red]Error:[/red] {project_path} is not a directory")
        raise typer.Exit(1)

    kontexto_dir = project_path / ".kontexto"
    db_path = kontexto_dir / "index.db"

    if incremental and db_path.exists():
        console.print(f"Incremental indexing [bold]{project_path}[/bold]...")
        _incremental_index(project_path, db_path)
    else:
        # Ensure .kontexto directory exists
        kontexto_dir.mkdir(exist_ok=True)
        console.print(f"Indexing [bold]{project_path}[/bold]...")
        _full_index(project_path, db_path)


def _ensure_parent_dirs(graph: CodeGraph, project_path: Path, rel_path: str) -> None:
    """Ensure all parent directories exist in the graph for a file path.

    Creates directory nodes for any missing parent directories.
    """
    parts = Path(rel_path).parts[:-1]  # Exclude the file name
    current_path = ""
    parent_id = "."

    for part in parts:
        current_path = f"{current_path}/{part}" if current_path else part
        if current_path not in graph.nodes:
            # Create the directory node
            dir_node = GraphNode(
                id=current_path,
                name=part,
                type="dir",
                parent_id=parent_id,
            )
            graph.nodes[current_path] = dir_node
            if parent_id in graph.nodes:
                graph.nodes[parent_id].children_ids.append(current_path)
        parent_id = current_path


def _full_index(project_path: Path, db_path: Path) -> None:
    """Perform a full index of the project."""
    # Build the graph
    graph = CodeGraph(project_path)
    graph.build()

    # Save to database using context manager
    with Store(db_path) as store:
        store.save_graph(graph)

        # Compute all file hashes and save in batch (single transaction)
        file_hashes: dict[str, str] = {}
        for node in graph.nodes.values():
            if node.type == "file" and node.file_path:
                file_path = project_path / node.file_path
                if file_path.exists():
                    file_hashes[node.file_path] = Store.compute_file_hash(file_path)

        store.save_file_hashes_batch(file_hashes)

        # Build search index
        console.print("Building search index...")
        search_engine = SearchEngine(store)
        search_engine.build_index()

    # Print stats
    stats = graph.get_stats(".")
    console.print(
        Panel(
            f"[green]Indexed successfully![/green]\n\n"
            f"  Files: {stats['files']}\n"
            f"  Classes: {stats['classes']}\n"
            f"  Functions: {stats['functions']}\n"
            f"  Methods: {stats['methods']}\n\n"
            f"Database: [dim]{db_path}[/dim]",
            title="Kontexto",
        )
    )


def _incremental_index(project_path: Path, db_path: Path) -> None:
    """Perform an incremental index, only updating changed files."""
    with Store(db_path) as store:
        # Load existing graph
        graph = store.load_graph(project_path)
        indexed_files = store.get_indexed_files()

        # Get registry for supported extensions
        registry = get_registry()
        supported_extensions = registry.get_supported_extensions()

        # Find all current source files efficiently
        current_files: set[str] = set()
        for source_file in project_path.rglob("*"):
            if not source_file.is_file():
                continue
            if source_file.suffix.lower() not in supported_extensions:
                continue
            # Check if any parent directory matches exclude patterns
            parts = source_file.relative_to(project_path).parts
            if any(
                part in DEFAULT_EXCLUDE_PATTERNS or part.endswith(".egg-info")
                for part in parts
            ):
                continue
            rel_path = str(source_file.relative_to(project_path))
            current_files.add(rel_path)

        files_added = 0
        files_updated = 0
        files_removed = 0
        new_hashes: dict[str, str] = {}

        # Track node IDs that need search index updates
        added_node_ids: list[str] = []
        updated_node_ids: list[str] = []
        removed_node_ids: list[str] = []

        # Check for new or modified files
        for rel_path in current_files:
            file_path = project_path / rel_path
            current_hash = Store.compute_file_hash(file_path)
            stored_hash = indexed_files.get(rel_path)

            if stored_hash is None:
                # New file - ensure parent directory exists in graph
                parent_id = str(Path(rel_path).parent)
                if parent_id != ".":
                    # Ensure all parent directories exist in the graph
                    _ensure_parent_dirs(graph, project_path, rel_path)

                # Track nodes before adding
                old_node_ids = set(graph.nodes.keys())
                graph.add_single_file(file_path, rel_path, parent_id)
                # Find newly added node IDs (entities from this file)
                new_node_ids = set(graph.nodes.keys()) - old_node_ids
                added_node_ids.extend(
                    nid
                    for nid in new_node_ids
                    if graph.nodes[nid].type in ("function", "method", "class")
                )

                new_hashes[rel_path] = current_hash
                files_added += 1
            elif stored_hash != current_hash:
                # Modified file - collect old node IDs to remove from index
                old_nodes_for_file = [
                    nid
                    for nid, node in graph.nodes.items()
                    if node.file_path == rel_path
                    and node.type in ("function", "method", "class")
                ]
                updated_node_ids.extend(old_nodes_for_file)

                # Update the graph
                parent_id = str(Path(rel_path).parent)
                graph.add_single_file(file_path, rel_path, parent_id)

                # Collect new node IDs after update
                new_nodes_for_file = [
                    nid
                    for nid, node in graph.nodes.items()
                    if node.file_path == rel_path
                    and node.type in ("function", "method", "class")
                ]
                updated_node_ids.extend(new_nodes_for_file)

                new_hashes[rel_path] = current_hash
                files_updated += 1

        # Check for deleted files - collect all to delete in batch
        files_to_delete = [
            rel_path for rel_path in indexed_files if rel_path not in current_files
        ]
        if files_to_delete:
            # Collect node IDs to remove from search index before deleting
            for rel_path in files_to_delete:
                nodes_for_file = [
                    nid
                    for nid, node in graph.nodes.items()
                    if node.file_path == rel_path
                    and node.type in ("function", "method", "class")
                ]
                removed_node_ids.extend(nodes_for_file)

            store.delete_file_nodes_batch(files_to_delete)
            files_removed = len(files_to_delete)

        # Save updated graph
        store.save_graph(graph)

        # Save new file hashes in batch
        if new_hashes:
            store.save_file_hashes_batch(new_hashes)

        # Update search index incrementally
        search_engine = SearchEngine(store)

        # Calculate net change in document count
        docs_added = len(added_node_ids)
        docs_removed = len(removed_node_ids)
        net_doc_change = docs_added - docs_removed

        # Remove deleted nodes from index
        if removed_node_ids:
            console.print(
                f"Removing {len(removed_node_ids)} entities from search index..."
            )
            search_engine.remove_nodes_from_index(removed_node_ids)

        # Update added and modified nodes
        nodes_to_update = list(set(added_node_ids + updated_node_ids))
        if nodes_to_update:
            console.print(
                f"Updating search index for {len(nodes_to_update)} entities..."
            )
            search_engine.update_index_for_nodes(nodes_to_update, net_doc_change)
        elif not removed_node_ids:
            console.print("No changes to search index.")

    # Print stats
    stats = graph.get_stats(".")
    console.print(
        Panel(
            f"[green]Incremental index complete![/green]\n\n"
            f"  Added: {files_added} files\n"
            f"  Updated: {files_updated} files\n"
            f"  Removed: {files_removed} files\n\n"
            f"  Total Files: {stats['files']}\n"
            f"  Classes: {stats['classes']}\n"
            f"  Functions: {stats['functions']}\n"
            f"  Methods: {stats['methods']}\n\n"
            f"Database: [dim]{db_path}[/dim]",
            title="Kontexto",
        )
    )


@app.command(name="map")
def show_map(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Show high-level project structure with stats.

    Returns: project name, root path, total stats (files, classes, functions),
    and top-level directories with their stats. Use 'expand' to drill deeper.
    """
    project_path = (path or Path.cwd()).resolve()
    db_path = _get_db_path(project_path)
    _check_index_exists(db_path)

    with Store(db_path) as store:
        root = store.get_node(".")
        if not root:
            console.print("[red]Error:[/red] No root node found")
            raise typer.Exit(1)

        children = store.get_children(".")
        dir_children = [child for child in children if child.type == "dir"]

        # Get stats for all directories in a single batch query
        dir_ids = [child.id for child in dir_children] + ["."]
        all_stats = store.get_stats_batch(dir_ids)

        child_stats = [
            (child.id, all_stats.get(child.id, {})) for child in dir_children
        ]

        output = JsonFormatter.format_map(
            root_name=root.name,
            root_path=str(project_path),
            stats=all_stats.get(".", {}),
            children=child_stats,
        )

        print(output)


@app.command()
def expand(
    node_path: str = typer.Argument(
        ...,
        help="Path to expand (e.g., 'src/api' or 'src/api/users.py')",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Drill into a directory or file to see its contents.

    For directories: shows subdirectories and files with stats.
    For files: shows classes (with base_classes) and functions with line ranges.
    For classes: shows methods with signatures and docstrings.
    """
    project_path = (path or Path.cwd()).resolve()
    db_path = _get_db_path(project_path)
    _check_index_exists(db_path)

    with Store(db_path) as store:
        node = store.get_node(node_path)
        if not node:
            console.print(f"[red]Error:[/red] Node not found: {node_path}")
            raise typer.Exit(1)

        children = store.get_children(node_path)

        # Get stats for all children in a single batch query
        child_ids = [child.id for child in children]
        stats_map = store.get_stats_batch(child_ids) if child_ids else {}

        output = JsonFormatter.format_expand(node, children, stats_map)
        print(output)


@app.command()
def inspect(
    entity_path: str = typer.Argument(
        ...,
        help="Entity ID (e.g., 'src/api/users.py:UserController.get_user')",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Get full details of a class, function, or method.

    Returns: type, name, file path, line range, signature, docstring,
    'calls' (what this entity calls), 'called_by' (what calls this entity).
    Entity ID format: 'file.py:ClassName.method_name' or 'file.py:function'.
    """
    project_path = (path or Path.cwd()).resolve()
    db_path = _get_db_path(project_path)
    _check_index_exists(db_path)

    with Store(db_path) as store:
        node = store.get_node(entity_path)
        if not node:
            console.print(f"[red]Error:[/red] Entity not found: {entity_path}")
            raise typer.Exit(1)

        # Get called by (what calls this entity)
        called_by = store.get_callers(node.name)

        output = JsonFormatter.format_inspect(node, node.calls, called_by)
        print(output)


@app.command()
def search(
    query: str = typer.Argument(
        ...,
        help="Search query (searches names, signatures, docstrings)",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of results (default: 10)",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Find classes, functions, methods by keyword using TF-IDF search.

    Searches entity names, signatures, and docstrings. Returns ranked results
    with relevance scores (0-1). Use the entity 'id' from results with
    'inspect' to get full details.
    """
    project_path = (path or Path.cwd()).resolve()
    db_path = _get_db_path(project_path)
    _check_index_exists(db_path)

    with Store(db_path) as store:
        search_engine = SearchEngine(store)

        results = search_engine.search(query, limit=limit)
        output = JsonFormatter.format_search_results(query, results)

        print(output)


@app.command()
def read(
    file_path: str = typer.Argument(
        ...,
        help="Relative file path (e.g., 'src/api/users.py')",
    ),
    start: Optional[int] = typer.Argument(
        None,
        help="Start line number (1-indexed, optional)",
    ),
    end: Optional[int] = typer.Argument(
        None,
        help="End line number (inclusive, optional)",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Read source code from a file.

    Returns raw file content (not JSON).
    Use line ranges from 'expand' or 'inspect' to read specific functions.
    Without start/end, reads entire file.
    """
    project_path = (path or Path.cwd()).resolve()
    db_path = _get_db_path(project_path)
    _check_index_exists(db_path)

    # Resolve the file path
    full_path = project_path / file_path
    if not full_path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    # Read file content with error handling
    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Try with latin-1 as fallback (handles most binary-ish files)
        try:
            content = full_path.read_text(encoding="latin-1")
        except Exception as e:
            console.print(f"[red]Error:[/red] Cannot read file {file_path}: {e}")
            raise typer.Exit(1)
    except PermissionError:
        console.print(f"[red]Error:[/red] Permission denied: {file_path}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Cannot read file {file_path}: {e}")
        raise typer.Exit(1)

    lines = content.split("\n")

    # Apply line range if specified
    start_line = start or 1
    end_line = end or len(lines)

    # Validate line range
    if start_line < 1:
        start_line = 1
    if end_line > len(lines):
        end_line = len(lines)
    if start_line > end_line:
        console.print(f"[red]Error:[/red] Invalid line range: {start_line}-{end_line}")
        raise typer.Exit(1)

    # Extract requested lines
    selected_lines = lines[start_line - 1 : end_line]
    selected_content = "\n".join(selected_lines)

    # Output raw content directly (no JSON wrapper)
    print(selected_content)


@app.command()
def hierarchy(
    base_class: str = typer.Argument(
        ...,
        help="Base class name (e.g., 'Exception', 'BaseModel', 'APIView')",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--project",
        "-p",
        help="Path to the project (default: current directory)",
    ),
) -> None:
    """Find all classes that inherit from a given base class.

    Returns list of subclasses with their file paths, signatures, and
    base_classes list. Useful for understanding class hierarchies and
    finding implementations of abstract base classes.
    """
    project_path = (path or Path.cwd()).resolve()
    db_path = _get_db_path(project_path)
    _check_index_exists(db_path)

    with Store(db_path) as store:
        subclasses = store.get_subclasses(base_class)
        output = JsonFormatter.format_hierarchy(base_class, subclasses)

        print(output)


if __name__ == "__main__":
    app()
