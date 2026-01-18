"""XML formatters for LLM-friendly output."""

from xml.etree.ElementTree import Element, SubElement, tostring

from contexto.graph import GraphNode


class XMLFormatter:
    """Formats graph data as compact XML for LLM consumption."""

    @staticmethod
    def format_map(root_name: str, root_path: str, stats: dict, children: list[tuple[str, dict]]) -> str:
        """Format the project map.

        Args:
            root_name: Project name
            root_path: Absolute path to project root
            stats: Stats for root node
            children: List of (node_id, stats) tuples for top-level directories
        """
        root = Element("map", project=root_name, root=root_path)

        for child_id, child_stats in children:
            name = child_id.split("/")[-1] if "/" in child_id else child_id
            dir_elem = SubElement(root, "dir", name=name)

            if child_stats["files"]:
                dir_elem.set("files", str(child_stats["files"]))
            if child_stats["classes"]:
                dir_elem.set("classes", str(child_stats["classes"]))
            if child_stats["functions"] + child_stats["methods"]:
                dir_elem.set("functions", str(child_stats["functions"] + child_stats["methods"]))

        return tostring(root, encoding="unicode")

    @staticmethod
    def format_expand(node: GraphNode, children: list[GraphNode], stats_map: dict[str, dict]) -> str:
        """Format expanded node with children.

        Args:
            node: The node being expanded
            children: List of child nodes
            stats_map: Map of child_id -> stats dict
        """
        if node.type == "dir":
            root = Element("dir", name=node.name)
            if node.id != ".":
                root.set("path", node.id)

            for child in children:
                if child.type == "dir":
                    child_elem = SubElement(root, "dir", name=child.name)
                    child_stats = stats_map.get(child.id, {})
                    if child_stats.get("files"):
                        child_elem.set("files", str(child_stats["files"]))
                elif child.type == "file":
                    child_elem = SubElement(root, "file", name=child.name)
                    child_stats = stats_map.get(child.id, {})
                    if child_stats.get("classes"):
                        child_elem.set("classes", str(child_stats["classes"]))
                    funcs = child_stats.get("functions", 0) + child_stats.get("methods", 0)
                    if funcs:
                        child_elem.set("functions", str(funcs))

        elif node.type == "file":
            root = Element("file", path=node.id)
            if node.line_end:
                root.set("lines", f"1-{node.line_end}")

            for child in children:
                if child.type == "class":
                    class_elem = SubElement(root, "class", name=child.name)
                    if child.line_start and child.line_end:
                        class_elem.set("lines", f"{child.line_start}-{child.line_end}")
                    if child.docstring:
                        doc_elem = SubElement(class_elem, "docstring")
                        doc_elem.text = _truncate(child.docstring, 100)

                    # Add methods
                    for method_id in child.children_ids:
                        method_name = method_id.split(".")[-1]
                        method_elem = SubElement(class_elem, "method", name=method_name)

                elif child.type == "function":
                    func_elem = SubElement(root, "function", name=child.name)
                    if child.line_start and child.line_end:
                        func_elem.set("lines", f"{child.line_start}-{child.line_end}")

        elif node.type == "class":
            root = Element("class", name=node.name, path=node.file_path or "")
            if node.line_start and node.line_end:
                root.set("lines", f"{node.line_start}-{node.line_end}")
            if node.docstring:
                doc_elem = SubElement(root, "docstring")
                doc_elem.text = _truncate(node.docstring, 200)

            for child in children:
                method_elem = SubElement(root, "method", name=child.name)
                if child.line_start and child.line_end:
                    method_elem.set("lines", f"{child.line_start}-{child.line_end}")
                if child.signature:
                    sig_elem = SubElement(method_elem, "signature")
                    sig_elem.text = child.signature
                if child.docstring:
                    doc_elem = SubElement(method_elem, "docstring")
                    doc_elem.text = _truncate(child.docstring, 100)

        else:
            root = Element("node", id=node.id, type=node.type)

        return tostring(root, encoding="unicode")

    @staticmethod
    def format_inspect(node: GraphNode, calls_to: list[str], called_by: list[str]) -> str:
        """Format detailed inspection of an entity.

        Args:
            node: The node to inspect
            calls_to: List of entity IDs this node calls
            called_by: List of entity IDs that call this node
        """
        type_name = node.type
        root = Element(type_name, name=node.name, path=node.file_path or "")

        if node.line_start and node.line_end:
            root.set("lines", f"{node.line_start}-{node.line_end}")

        if node.signature:
            sig_elem = SubElement(root, "signature")
            sig_elem.text = node.signature

        if node.docstring:
            doc_elem = SubElement(root, "docstring")
            doc_elem.text = node.docstring

        if calls_to:
            calls_elem = SubElement(root, "calls")
            for call in calls_to:
                SubElement(calls_elem, "ref", path=call)

        if called_by:
            called_elem = SubElement(root, "called_by")
            for caller in called_by:
                SubElement(called_elem, "ref", path=caller)

        return tostring(root, encoding="unicode")

    @staticmethod
    def format_search_results(query: str, results: list[tuple[GraphNode, float]]) -> str:
        """Format search results.

        Args:
            query: The search query
            results: List of (node, score) tuples
        """
        root = Element("results", query=query, count=str(len(results)))

        for node, score in results:
            result_elem = SubElement(root, "result", score=f"{score:.2f}", path=node.id)
            type_elem = SubElement(result_elem, "type")
            type_elem.text = node.type
            if node.signature:
                sig_elem = SubElement(result_elem, "signature")
                sig_elem.text = node.signature

        return tostring(root, encoding="unicode")

    @staticmethod
    def format_read(file_path: str, content: str, start_line: int = 1) -> str:
        """Format file content with line numbers.

        Args:
            file_path: Path to the file
            content: File content
            start_line: Starting line number
        """
        root = Element("file", path=file_path)

        lines = content.split("\n")
        code_elem = SubElement(root, "code", start=str(start_line))

        numbered_lines = []
        for i, line in enumerate(lines, start=start_line):
            numbered_lines.append(f"{i:4d} | {line}")

        code_elem.text = "\n".join(numbered_lines)

        return tostring(root, encoding="unicode")


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max length, preserving first line if possible."""
    if len(text) <= max_len:
        return text

    first_line = text.split("\n")[0]
    if len(first_line) <= max_len:
        return first_line + "..."

    return text[:max_len - 3] + "..."
