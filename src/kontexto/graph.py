"""Graph construction and navigation for the codebase."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from kontexto.parsers import get_registry, DEFAULT_EXCLUDE_PATTERNS
from kontexto.parsers.base import BaseParser


@dataclass
class GraphNode:
    """A node in the codebase graph."""

    id: str
    name: str
    type: str  # 'dir', 'file', 'class', 'function', 'method', 'interface', 'struct', 'trait', 'impl', 'enum', 'type'
    parent_id: Optional[str] = None
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    language: Optional[str] = None


class CodeGraph:
    """Manages the navigable graph of the codebase."""

    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()
        self.root_name = root_path.name
        self.nodes: dict[str, GraphNode] = {}
        self._registry = get_registry()

    def build(self, exclude_patterns: Optional[list[str]] = None) -> None:
        """Build the graph by scanning the codebase."""
        exclude_patterns = exclude_patterns or list(DEFAULT_EXCLUDE_PATTERNS)

        # Create root node
        root_node = GraphNode(
            id=".",
            name=self.root_name,
            type="dir",
        )
        self.nodes["."] = root_node

        # Walk the directory tree
        self._scan_directory(
            self.root_path, parent_id=".", exclude_patterns=exclude_patterns
        )

    def _scan_directory(
        self, dir_path: Path, parent_id: str, exclude_patterns: list[str]
    ) -> None:
        """Recursively scan a directory and build graph nodes."""
        try:
            items = sorted(dir_path.iterdir())
        except PermissionError:
            return

        for item in items:
            # Check exclusion patterns
            if any(item.match(pattern) for pattern in exclude_patterns):
                continue

            rel_path = str(item.relative_to(self.root_path))

            if item.is_dir():
                # Create directory node
                dir_node = GraphNode(
                    id=rel_path,
                    name=item.name,
                    type="dir",
                    parent_id=parent_id,
                )
                self.nodes[rel_path] = dir_node
                self.nodes[parent_id].children_ids.append(rel_path)

                # Recurse into directory
                self._scan_directory(
                    item, parent_id=rel_path, exclude_patterns=exclude_patterns
                )

            else:
                # Check if file is supported by any parser
                parser = self._registry.get_parser_for_file(item)
                if parser:
                    self._add_source_file(item, rel_path, parent_id, parser)

    def add_single_file(self, file_path: Path, rel_path: str, parent_id: str) -> None:
        """Add or update a single source file in the graph.

        Used for incremental updates.
        """
        # Remove existing nodes for this file
        nodes_to_remove = [
            nid
            for nid, node in self.nodes.items()
            if node.file_path == rel_path or nid == rel_path
        ]
        for nid in nodes_to_remove:
            # Remove from parent's children
            node = self.nodes[nid]
            if node.parent_id and node.parent_id in self.nodes:
                parent = self.nodes[node.parent_id]
                if nid in parent.children_ids:
                    parent.children_ids.remove(nid)
            del self.nodes[nid]

        # Get parser for file and re-add
        parser = self._registry.get_parser_for_file(file_path)
        if parser:
            self._add_source_file(file_path, rel_path, parent_id, parser)

    def _add_source_file(
        self,
        file_path: Path,
        rel_path: str,
        parent_id: str,
        parser: BaseParser,
    ) -> None:
        """Add a source file and its entities to the graph."""
        # Parse file first to get line count
        entities, line_count = parser.parse_file(file_path)

        # Get language from parser config
        language = parser.config.name

        # Create file node with line_end set to total lines (default to 0 if parsing failed)
        file_node = GraphNode(
            id=rel_path,
            name=file_path.name,
            type="file",
            parent_id=parent_id,
            file_path=rel_path,
            line_start=1,
            line_end=line_count or 0,
            language=language,
        )
        self.nodes[rel_path] = file_node
        self.nodes[parent_id].children_ids.append(rel_path)

        for entity in entities:
            # Update entity id to use relative path
            entity_id = f"{rel_path}:{entity.name}"
            if entity.parent_id:
                # This is a method or nested class - parent_id needs updating
                # Handle nested paths like "ClassName.NestedClass.method"
                parent_suffix = entity.parent_id.split(":")[-1]
                entity_parent_id = f"{rel_path}:{parent_suffix}"
                entity_id = f"{entity_parent_id}.{entity.name}"
            else:
                entity_parent_id = rel_path

            node = GraphNode(
                id=entity_id,
                name=entity.name,
                type=entity.type,
                parent_id=entity_parent_id,
                file_path=rel_path,
                line_start=entity.line_start,
                line_end=entity.line_end,
                signature=entity.signature,
                docstring=entity.docstring,
                calls=entity.calls,
                base_classes=entity.base_classes,
                language=entity.language,
            )
            self.nodes[entity_id] = node

            # Add to parent's children
            if entity_parent_id in self.nodes:
                self.nodes[entity_parent_id].children_ids.append(entity_id)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by its ID."""
        return self.nodes.get(node_id)

    def get_children(self, node_id: str) -> list[GraphNode]:
        """Get all children of a node."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]

    def get_root(self) -> Optional[GraphNode]:
        """Get the root node.

        Returns:
            The root GraphNode, or None if the graph hasn't been built yet.
        """
        return self.nodes.get(".")

    def get_stats(self, node_id: str = ".") -> dict:
        """Get statistics for a node and its descendants."""
        stats = {"files": 0, "classes": 0, "functions": 0, "methods": 0}

        def count_recursive(nid: str) -> None:
            node = self.nodes.get(nid)
            if not node:
                return

            if node.type == "file":
                stats["files"] += 1
            elif node.type == "class":
                stats["classes"] += 1
            elif node.type == "function":
                stats["functions"] += 1
            elif node.type == "method":
                stats["methods"] += 1

            for child_id in node.children_ids:
                count_recursive(child_id)

        count_recursive(node_id)
        return stats
