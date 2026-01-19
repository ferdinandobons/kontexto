"""Tree-sitter based Python parser."""

import logging
from pathlib import Path
from typing import Optional

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node

from kontexto.parsers.base import BaseParser, CodeEntity, LanguageConfig

logger = logging.getLogger(__name__)


class PythonParser(BaseParser):
    """Tree-sitter based parser for Python source files."""

    def __init__(self) -> None:
        self._language = Language(tspython.language())
        self._parser = Parser(self._language)

    @property
    def config(self) -> LanguageConfig:
        return LanguageConfig(
            name="python",
            extensions=(".py", ".pyi"),
            exclude_patterns=(
                "__pycache__",
                ".venv",
                "venv",
                ".pytest_cache",
                ".mypy_cache",
            ),
        )

    def parse_file(self, file_path: Path) -> tuple[list[CodeEntity], Optional[int]]:
        """Parse a Python file and extract all entities."""
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
        parent_id: Optional[str] = None,
    ) -> None:
        """Recursively extract entities from the AST."""
        for child in node.children:
            if child.type == "function_definition":
                entity = self._extract_function(child, content, file_path, parent_id)
                entities.append(entity)
            elif child.type == "class_definition":
                class_entities = self._extract_class(
                    child, content, file_path, parent_id
                )
                entities.extend(class_entities)

    def _extract_function(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
    ) -> CodeEntity:
        """Extract a function or method entity."""
        name = self._get_name(node)
        entity_type = "method" if parent_id else "function"
        entity_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        # Check if async (first child is "async" keyword)
        first_keyword = node.children[0] if node.children else None
        is_async = first_keyword is not None and first_keyword.type == "async"

        return CodeEntity(
            id=entity_id,
            name=name,
            type=entity_type,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_function_signature(node, is_async),
            docstring=self._get_docstring(node, content),
            parent_id=parent_id,
            calls=self._extract_calls(node, content),
            language="python",
        )

    def _extract_class(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
    ) -> list[CodeEntity]:
        """Extract a class and its methods/nested classes."""
        name = self._get_name(node)
        class_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        entities: list[CodeEntity] = []

        # Extract base classes
        base_classes = self._get_base_classes(node)

        entities.append(
            CodeEntity(
                id=class_id,
                name=name,
                type="class",
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._get_class_signature(node),
                docstring=self._get_docstring(node, content),
                parent_id=parent_id,
                base_classes=base_classes,
                language="python",
            )
        )

        # Extract methods and nested classes from the class body
        body = self._get_child_by_type(node, "block")
        if body:
            for child in body.children:
                if child.type == "function_definition":
                    entities.append(
                        self._extract_function(child, content, file_path, class_id)
                    )
                elif child.type == "class_definition":
                    entities.extend(
                        self._extract_class(child, content, file_path, class_id)
                    )

        return entities

    def _get_name(self, node: Node) -> str:
        """Get the name identifier from a function or class definition."""
        name_node = self._get_child_by_type(node, "identifier")
        if name_node:
            return name_node.text.decode("utf-8") if name_node.text else ""
        return ""

    def _get_child_by_type(self, node: Node, type_name: str) -> Optional[Node]:
        """Find the first child node of a given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _get_function_signature(self, node: Node, is_async: bool = False) -> str:
        """Build function signature string."""
        name = self._get_name(node)
        params = self._get_child_by_type(node, "parameters")
        params_text = params.text.decode("utf-8") if params and params.text else "()"

        prefix = "async def" if is_async else "def"
        signature = f"{prefix} {name}{params_text}"

        # Get return type annotation
        return_type = self._get_child_by_type(node, "type")
        if return_type and return_type.text:
            signature += f" -> {return_type.text.decode('utf-8')}"

        return signature

    def _get_class_signature(self, node: Node) -> str:
        """Build class signature string."""
        name = self._get_name(node)
        bases = self._get_base_classes(node)

        if bases:
            return f"class {name}({', '.join(bases)})"
        return f"class {name}"

    def _get_base_classes(self, node: Node) -> list[str]:
        """Extract base class names from a class definition."""
        bases: list[str] = []
        arg_list = self._get_child_by_type(node, "argument_list")

        if arg_list:
            for child in arg_list.children:
                if child.type in ("identifier", "attribute", "subscript"):
                    if child.text:
                        bases.append(child.text.decode("utf-8"))

        return bases

    def _get_docstring(self, node: Node, content: bytes) -> Optional[str]:
        """Extract docstring from a function or class definition."""
        body = self._get_child_by_type(node, "block")
        if not body or not body.children:
            return None

        # First statement in the block
        for child in body.children:
            if child.type == "expression_statement":
                string_node = self._get_child_by_type(child, "string")
                if string_node and string_node.text:
                    docstring = string_node.text.decode("utf-8")
                    # Remove quotes (single, double, or triple)
                    if docstring.startswith('"""') or docstring.startswith("'''"):
                        return docstring[3:-3].strip()
                    elif docstring.startswith('"') or docstring.startswith("'"):
                        return docstring[1:-1].strip()
                break

        return None

    def _extract_calls(self, node: Node, content: bytes) -> list[str]:
        """Extract function/method calls from a function body."""
        calls: set[str] = set()

        def walk(n: Node) -> None:
            if n.type == "call":
                func = self._get_child_by_type(n, "identifier")
                if func and func.text:
                    calls.add(func.text.decode("utf-8"))
                else:
                    # Handle attribute access like obj.method()
                    attr = self._get_child_by_type(n, "attribute")
                    if attr:
                        # Get the last identifier (method name)
                        attr_name = self._get_child_by_type(attr, "identifier")
                        if attr_name and attr_name.text:
                            calls.add(attr_name.text.decode("utf-8"))

            for child in n.children:
                walk(child)

        # Walk only the function body
        body = self._get_child_by_type(node, "block")
        if body:
            walk(body)

        return list(calls)
