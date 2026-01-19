"""JSON formatters for LLM-friendly output."""

import json
from typing import Any

from kontexto.graph import GraphNode


def _node_to_dict(node: GraphNode) -> dict[str, Any]:
    """Convert a GraphNode to a dictionary for JSON serialization."""
    return {
        "id": node.id,
        "name": node.name,
        "type": node.type,
        "language": node.language,
        "parent_id": node.parent_id,
        "file_path": node.file_path,
        "line_start": node.line_start,
        "line_end": node.line_end,
        "signature": node.signature,
        "docstring": node.docstring,
        "children_ids": node.children_ids,
        "calls": node.calls,
        "base_classes": node.base_classes,
    }


class JsonFormatter:
    """Formats graph data as JSON for programmatic consumption by LLMs."""

    @staticmethod
    def format_map(
        root_name: str, root_path: str, stats: dict, children: list[tuple[str, dict]]
    ) -> str:
        """Format the project map as JSON."""
        data = {
            "command": "map",
            "project": root_name,
            "root": root_path,
            "stats": stats,
            "children": [
                {"id": child_id, "stats": child_stats}
                for child_id, child_stats in children
            ],
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def format_expand(
        node: GraphNode, children: list[GraphNode], stats_map: dict[str, dict]
    ) -> str:
        """Format expanded node with children as JSON."""
        data = {
            "command": "expand",
            "node": _node_to_dict(node),
            "children": [
                {
                    **_node_to_dict(child),
                    "stats": stats_map.get(child.id, {}),
                }
                for child in children
            ],
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def format_inspect(
        node: GraphNode, calls_to: list[str], called_by: list[str]
    ) -> str:
        """Format detailed inspection of an entity as JSON."""
        data = {
            "command": "inspect",
            "node": _node_to_dict(node),
            "calls": calls_to,
            "called_by": called_by,
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def format_search_results(
        query: str, results: list[tuple[GraphNode, float]]
    ) -> str:
        """Format search results as JSON."""
        data = {
            "command": "search",
            "query": query,
            "count": len(results),
            "results": [
                {
                    "node": _node_to_dict(node),
                    "score": round(score, 4),
                }
                for node, score in results
            ],
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def format_hierarchy(base_class: str, subclasses: list[GraphNode]) -> str:
        """Format class hierarchy as JSON."""
        data = {
            "command": "hierarchy",
            "base_class": base_class,
            "count": len(subclasses),
            "subclasses": [_node_to_dict(node) for node in subclasses],
        }
        return json.dumps(data, indent=2)
