"""Text formatters for LLM-friendly output."""

from contexto.graph import GraphNode


class TextFormatter:
    """Formats graph data as structured text for LLM consumption."""

    @staticmethod
    def format_map(root_name: str, root_path: str, stats: dict, children: list[tuple[str, dict]]) -> str:
        """Format the project map.

        Args:
            root_name: Project name
            root_path: Absolute path to project root
            stats: Stats for root node
            children: List of (node_id, stats) tuples for top-level directories
        """
        lines = [
            f"project: {root_name}",
            f"root: {root_path}",
            "",
        ]

        for child_id, child_stats in children:
            name = child_id.split("/")[-1] if "/" in child_id else child_id
            stats_parts = []
            if child_stats.get("files"):
                stats_parts.append(f"{child_stats['files']} files")
            if child_stats.get("classes"):
                stats_parts.append(f"{child_stats['classes']} classes")
            funcs = child_stats.get("functions", 0) + child_stats.get("methods", 0)
            if funcs:
                stats_parts.append(f"{funcs} functions")

            stats_str = ", ".join(stats_parts) if stats_parts else ""
            lines.append(f"{name}/".ljust(20) + stats_str)

        return "\n".join(lines)

    @staticmethod
    def format_expand(node: GraphNode, children: list[GraphNode], stats_map: dict[str, dict]) -> str:
        """Format expanded node with children.

        Args:
            node: The node being expanded
            children: List of child nodes
            stats_map: Map of child_id -> stats dict
        """
        lines = []

        if node.type == "dir":
            path_display = node.id if node.id != "." else node.name
            lines.append(f"{path_display}/")
            lines.append("")

            for child in children:
                if child.type == "dir":
                    child_stats = stats_map.get(child.id, {})
                    stats_parts = []
                    if child_stats.get("files"):
                        stats_parts.append(f"{child_stats['files']} files")
                    stats_str = f"  ({', '.join(stats_parts)})" if stats_parts else ""
                    lines.append(f"  {child.name}/{stats_str}")
                elif child.type == "file":
                    child_stats = stats_map.get(child.id, {})
                    stats_parts = []
                    if child_stats.get("classes"):
                        stats_parts.append(f"{child_stats['classes']} classes")
                    funcs = child_stats.get("functions", 0) + child_stats.get("methods", 0)
                    if funcs:
                        stats_parts.append(f"{funcs} functions")
                    stats_str = f"  ({', '.join(stats_parts)})" if stats_parts else ""
                    lines.append(f"  {child.name}{stats_str}")

        elif node.type == "file":
            line_info = f" ({node.line_end} lines)" if node.line_end else ""
            lines.append(f"{node.id}{line_info}")
            lines.append("")

            for child in children:
                if child.type == "class":
                    line_range = f" [{child.line_start}-{child.line_end}]" if child.line_start else ""
                    lines.append(f"class {child.name}{line_range}")
                    if child.docstring:
                        lines.append(f'  """{_truncate(child.docstring, 80)}"""')

                    # Add methods
                    for method_id in child.children_ids:
                        method_name = method_id.split(".")[-1]
                        lines.append(f"  - {method_name}")

                    lines.append("")

                elif child.type == "function":
                    line_range = f" [{child.line_start}-{child.line_end}]" if child.line_start else ""
                    lines.append(f"function {child.name}{line_range}")

        elif node.type == "class":
            line_range = f" [{node.line_start}-{node.line_end}]" if node.line_start else ""
            lines.append(f"class {node.name}{line_range}")
            if node.file_path:
                lines.append(f"file: {node.file_path}")
            if node.docstring:
                lines.append(f'"""{_truncate(node.docstring, 150)}"""')
            lines.append("")

            for child in children:
                line_range = f" [{child.line_start}-{child.line_end}]" if child.line_start else ""
                lines.append(f"  {child.name}{line_range}")
                if child.signature:
                    lines.append(f"    {child.signature}")
                if child.docstring:
                    lines.append(f'    """{_truncate(child.docstring, 80)}"""')

        else:
            lines.append(f"{node.type}: {node.id}")

        return "\n".join(lines)

    @staticmethod
    def format_inspect(node: GraphNode, calls_to: list[str], called_by: list[str]) -> str:
        """Format detailed inspection of an entity.

        Args:
            node: The node to inspect
            calls_to: List of entity IDs this node calls
            called_by: List of entity IDs that call this node
        """
        lines = [f"{node.type}: {node.name}"]

        if node.file_path:
            line_range = f" [{node.line_start}-{node.line_end}]" if node.line_start else ""
            lines.append(f"file: {node.file_path}{line_range}")

        if node.signature:
            lines.append(f"signature: {node.signature}")

        if node.docstring:
            lines.append(f"docstring: {node.docstring}")

        if calls_to:
            lines.append("")
            lines.append("calls:")
            for call in calls_to:
                lines.append(f"  - {call}")

        if called_by:
            lines.append("")
            lines.append("called by:")
            for caller in called_by:
                lines.append(f"  - {caller}")

        return "\n".join(lines)

    @staticmethod
    def format_search_results(query: str, results: list[tuple[GraphNode, float]]) -> str:
        """Format search results.

        Args:
            query: The search query
            results: List of (node, score) tuples
        """
        lines = [f'search: "{query}" ({len(results)} results)', ""]

        for i, (node, score) in enumerate(results, 1):
            lines.append(f"{i}. {node.id} [{node.type}]")
            if node.signature:
                lines.append(f"   {node.signature}")
            elif node.docstring:
                lines.append(f'   """{_truncate(node.docstring, 60)}"""')
            lines.append("")

        return "\n".join(lines).rstrip()

    @staticmethod
    def format_read(file_path: str, content: str, start_line: int = 1) -> str:
        """Format file content with line numbers.

        Args:
            file_path: Path to the file
            content: File content
            start_line: Starting line number
        """
        lines = [f"file: {file_path}", ""]

        content_lines = content.split("\n")
        for i, line in enumerate(content_lines, start=start_line):
            lines.append(f"{i:4d} | {line}")

        return "\n".join(lines)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max length, preserving first line if possible."""
    if not text:
        return ""

    # Get first line only
    first_line = text.split("\n")[0].strip()

    if len(first_line) <= max_len:
        return first_line

    return first_line[: max_len - 3] + "..."
