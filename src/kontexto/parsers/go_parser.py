"""Tree-sitter based Go parser."""

import logging
from pathlib import Path
from typing import Optional

import tree_sitter_go as tsgo
from tree_sitter import Language, Parser, Node

from kontexto.parsers.base import BaseParser, CodeEntity, LanguageConfig

logger = logging.getLogger(__name__)


class GoParser(BaseParser):
    """Tree-sitter based parser for Go source files."""

    def __init__(self) -> None:
        self._language = Language(tsgo.language())
        self._parser = Parser(self._language)

    @property
    def config(self) -> LanguageConfig:
        return LanguageConfig(
            name="go",
            extensions=(".go",),
            exclude_patterns=("vendor",),
        )

    def parse_file(self, file_path: Path) -> tuple[list[CodeEntity], Optional[int]]:
        """Parse a Go file and extract all entities."""
        try:
            content = file_path.read_bytes()
            text = content.decode("utf-8")
            tree = self._parser.parse(content)
            line_count = text.count("\n") + 1
        except UnicodeDecodeError as e:
            logger.warning(f"Encoding error in {file_path}: {e}")
            return [], None
        except Exception as e:
            logger.warning(f"Parse error in {file_path}: {e}")
            return [], None

        entities: list[CodeEntity] = []
        rel_path = str(file_path)

        self._extract_entities(tree.root_node, content, rel_path, entities)

        return entities, line_count

    def _extract_entities(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        entities: list[CodeEntity],
    ) -> None:
        """Recursively extract entities from the AST."""
        for child in node.children:
            # Function declarations
            if child.type == "function_declaration":
                entity = self._extract_function(child, content, file_path)
                if entity:
                    entities.append(entity)

            # Method declarations (with receiver)
            elif child.type == "method_declaration":
                entity = self._extract_method(child, content, file_path)
                if entity:
                    entities.append(entity)

            # Type declarations (struct, interface)
            elif child.type == "type_declaration":
                self._extract_type_declarations(child, content, file_path, entities)

    def _extract_function(
        self,
        node: Node,
        content: bytes,
        file_path: str,
    ) -> Optional[CodeEntity]:
        """Extract a function declaration entity."""
        name = self._get_name(node)
        if not name:
            return None

        entity_id = f"{file_path}:{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="function",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_function_signature(node),
            docstring=self._get_go_comment(node, content),
            calls=self._extract_calls(node, content),
            language="go",
        )

    def _extract_method(
        self,
        node: Node,
        content: bytes,
        file_path: str,
    ) -> Optional[CodeEntity]:
        """Extract a method declaration entity (with receiver)."""
        name_node = self._get_child_by_type(node, "field_identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")

        # Get receiver type to establish parent relationship
        receiver_type = self._get_receiver_type(node, content)
        if receiver_type:
            parent_id = f"{file_path}:{receiver_type}"
            entity_id = f"{parent_id}.{name}"
        else:
            parent_id = None
            entity_id = f"{file_path}:{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="method",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_method_signature(node),
            docstring=self._get_go_comment(node, content),
            parent_id=parent_id,
            calls=self._extract_calls(node, content),
            language="go",
        )

    def _extract_type_declarations(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        entities: list[CodeEntity],
    ) -> None:
        """Extract type declarations (structs, interfaces)."""
        for child in node.children:
            if child.type == "type_spec":
                self._extract_type_spec(child, content, file_path, entities)

    def _extract_type_spec(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        entities: list[CodeEntity],
    ) -> None:
        """Extract a single type specification."""
        name_node = self._get_child_by_type(node, "type_identifier")
        if not name_node or not name_node.text:
            return

        name = name_node.text.decode("utf-8")
        entity_id = f"{file_path}:{name}"

        # Determine the type kind
        type_node = None
        for child in node.children:
            if child.type in ("struct_type", "interface_type"):
                type_node = child
                break

        if type_node:
            if type_node.type == "struct_type":
                entities.append(
                    CodeEntity(
                        id=entity_id,
                        name=name,
                        type="struct",
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=f"type {name} struct",
                        docstring=self._get_go_comment(node, content),
                        language="go",
                    )
                )
            elif type_node.type == "interface_type":
                entities.append(
                    CodeEntity(
                        id=entity_id,
                        name=name,
                        type="interface",
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=f"type {name} interface",
                        docstring=self._get_go_comment(node, content),
                        language="go",
                    )
                )

    def _get_name(self, node: Node) -> str:
        """Get the name identifier from a function declaration."""
        name_node = self._get_child_by_type(node, "identifier")
        if name_node and name_node.text:
            return name_node.text.decode("utf-8")
        return ""

    def _get_child_by_type(self, node: Node, type_name: str) -> Optional[Node]:
        """Find the first child node of a given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _get_receiver_type(self, node: Node, content: bytes) -> Optional[str]:
        """Get the receiver type from a method declaration."""
        params = self._get_child_by_type(node, "parameter_list")
        if not params:
            return None

        for child in params.children:
            if child.type == "parameter_declaration":
                # Find the type identifier (could be pointer type or direct)
                for c in child.children:
                    if c.type == "type_identifier" and c.text:
                        return c.text.decode("utf-8")
                    elif c.type == "pointer_type":
                        # Get the inner type
                        inner = self._get_child_by_type(c, "type_identifier")
                        if inner and inner.text:
                            return inner.text.decode("utf-8")
        return None

    def _get_function_signature(self, node: Node) -> str:
        """Build function signature string."""
        name = self._get_name(node)
        params = self._get_child_by_type(node, "parameter_list")
        params_text = params.text.decode("utf-8") if params and params.text else "()"

        signature = f"func {name}{params_text}"

        # Get return type(s)
        result = self._get_child_by_type(node, "result")
        if not result:
            # Could be a simple return type
            for child in node.children:
                if child.type in (
                    "type_identifier",
                    "pointer_type",
                    "slice_type",
                    "map_type",
                ):
                    result = child
                    break
                elif child.type == "parameter_list" and child != params:
                    result = child
                    break

        if result and result.text:
            signature += f" {result.text.decode('utf-8')}"

        return signature

    def _get_method_signature(self, node: Node) -> str:
        """Build method signature string."""
        name_node = self._get_child_by_type(node, "field_identifier")
        name = name_node.text.decode("utf-8") if name_node and name_node.text else ""

        # Get receiver
        receiver = ""
        params_list = []
        for child in node.children:
            if child.type == "parameter_list":
                params_list.append(child)

        if params_list:
            receiver = (
                params_list[0].text.decode("utf-8") if params_list[0].text else ""
            )
            params = (
                params_list[1].text.decode("utf-8")
                if len(params_list) > 1 and params_list[1].text
                else "()"
            )
        else:
            params = "()"

        signature = f"func {receiver} {name}{params}"

        # Get return type
        result = self._get_child_by_type(node, "result")
        if not result:
            for child in node.children:
                if child.type in (
                    "type_identifier",
                    "pointer_type",
                    "slice_type",
                    "map_type",
                ):
                    result = child
                    break
                elif child.type == "parameter_list" and child not in params_list:
                    result = child
                    break

        if result and result.text:
            signature += f" {result.text.decode('utf-8')}"

        return signature

    def _get_go_comment(self, node: Node, content: bytes) -> Optional[str]:
        """Extract Go doc comment before a node.

        Supports both single-line (//) and multi-line (/* */) comments.
        Multiple consecutive // comments are joined together.
        """
        comments: list[str] = []

        sibling = node.prev_sibling
        while sibling:
            if sibling.type == "comment":
                comment = sibling.text.decode("utf-8") if sibling.text else ""
                if comment.startswith("//"):
                    comments.insert(0, comment[2:].strip())
                elif comment.startswith("/*"):
                    # Block comment - extract content
                    block_content = comment[2:-2].strip()
                    comments.insert(0, block_content)
                sibling = sibling.prev_sibling
            else:
                # Stop at non-comment nodes
                break

        return " ".join(comments) if comments else None

    def _extract_calls(self, node: Node, content: bytes) -> list[str]:
        """Extract function/method calls from a node."""
        calls: set[str] = set()

        def walk(n: Node) -> None:
            if n.type == "call_expression":
                func = self._get_child_by_type(n, "identifier")
                if func and func.text:
                    calls.add(func.text.decode("utf-8"))
                else:
                    # Handle selector expression like obj.Method()
                    selector = self._get_child_by_type(n, "selector_expression")
                    if selector:
                        field = self._get_child_by_type(selector, "field_identifier")
                        if field and field.text:
                            calls.add(field.text.decode("utf-8"))

            for child in n.children:
                walk(child)

        # Walk the function body
        body = self._get_child_by_type(node, "block")
        if body:
            walk(body)

        return list(calls)
