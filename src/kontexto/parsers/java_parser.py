"""Tree-sitter based Java parser."""

import logging
from pathlib import Path
from typing import Optional

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser, Node

from kontexto.parsers.base import BaseParser, CodeEntity, LanguageConfig

logger = logging.getLogger(__name__)


class JavaParser(BaseParser):
    """Tree-sitter based parser for Java source files."""

    def __init__(self) -> None:
        self._language = Language(tsjava.language())
        self._parser = Parser(self._language)

    @property
    def config(self) -> LanguageConfig:
        return LanguageConfig(
            name="java",
            extensions=(".java",),
            exclude_patterns=("target", ".gradle", "build", "bin"),
        )

    def parse_file(self, file_path: Path) -> tuple[list[CodeEntity], Optional[int]]:
        """Parse a Java file and extract all entities."""
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
            # Class declarations
            if child.type == "class_declaration":
                class_entities = self._extract_class(
                    child, content, file_path, parent_id
                )
                entities.extend(class_entities)

            # Interface declarations
            elif child.type == "interface_declaration":
                interface_entities = self._extract_interface(
                    child, content, file_path, parent_id
                )
                entities.extend(interface_entities)

            # Enum declarations
            elif child.type == "enum_declaration":
                entity = self._extract_enum(child, content, file_path, parent_id)
                if entity:
                    entities.append(entity)

            # Record declarations (Java 14+)
            elif child.type == "record_declaration":
                class_entities = self._extract_record(
                    child, content, file_path, parent_id
                )
                entities.extend(class_entities)

            # Recurse into program node
            elif child.type == "program":
                self._extract_entities(child, content, file_path, entities, parent_id)

    def _extract_class(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
    ) -> list[CodeEntity]:
        """Extract a class and its methods."""
        name_node = self._get_child_by_type(node, "identifier")
        if not name_node or not name_node.text:
            return []

        name = name_node.text.decode("utf-8")
        class_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        entities: list[CodeEntity] = []

        # Get extends and implements
        extends = self._get_superclass(node)
        implements = self._get_interfaces(node)
        base_classes = ([extends] if extends else []) + implements

        entities.append(
            CodeEntity(
                id=class_id,
                name=name,
                type="class",
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._get_class_signature(node),
                docstring=self._get_javadoc(node, content),
                parent_id=parent_id,
                base_classes=base_classes,
                language="java",
            )
        )

        # Extract methods and nested types from class body
        body = self._get_child_by_type(node, "class_body")
        if body:
            for child in body.children:
                if child.type == "method_declaration":
                    method = self._extract_method(child, content, file_path, class_id)
                    if method:
                        entities.append(method)
                elif child.type == "constructor_declaration":
                    constructor = self._extract_constructor(
                        child, content, file_path, class_id
                    )
                    if constructor:
                        entities.append(constructor)
                elif child.type == "class_declaration":
                    entities.extend(
                        self._extract_class(child, content, file_path, class_id)
                    )
                elif child.type == "interface_declaration":
                    entities.extend(
                        self._extract_interface(child, content, file_path, class_id)
                    )
                elif child.type == "enum_declaration":
                    entity = self._extract_enum(child, content, file_path, class_id)
                    if entity:
                        entities.append(entity)

        return entities

    def _extract_interface(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
    ) -> list[CodeEntity]:
        """Extract an interface and its methods."""
        name_node = self._get_child_by_type(node, "identifier")
        if not name_node or not name_node.text:
            return []

        name = name_node.text.decode("utf-8")
        interface_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        entities: list[CodeEntity] = []

        # Get extended interfaces
        extends = self._get_extended_interfaces(node)

        entities.append(
            CodeEntity(
                id=interface_id,
                name=name,
                type="interface",
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=f"interface {name}",
                docstring=self._get_javadoc(node, content),
                parent_id=parent_id,
                base_classes=extends,
                language="java",
            )
        )

        # Extract interface methods
        body = self._get_child_by_type(node, "interface_body")
        if body:
            for child in body.children:
                if child.type == "method_declaration":
                    method = self._extract_method(
                        child, content, file_path, interface_id
                    )
                    if method:
                        entities.append(method)

        return entities

    def _extract_enum(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
    ) -> Optional[CodeEntity]:
        """Extract an enum declaration."""
        name_node = self._get_child_by_type(node, "identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="enum",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=f"enum {name}",
            docstring=self._get_javadoc(node, content),
            parent_id=parent_id,
            language="java",
        )

    def _extract_record(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
    ) -> list[CodeEntity]:
        """Extract a record declaration (Java 14+)."""
        name_node = self._get_child_by_type(node, "identifier")
        if not name_node or not name_node.text:
            return []

        name = name_node.text.decode("utf-8")
        record_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        entities: list[CodeEntity] = []

        entities.append(
            CodeEntity(
                id=record_id,
                name=name,
                type="class",  # Records are special classes
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=f"record {name}",
                docstring=self._get_javadoc(node, content),
                parent_id=parent_id,
                language="java",
            )
        )

        return entities

    def _extract_method(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: str,
    ) -> Optional[CodeEntity]:
        """Extract a method declaration."""
        name_node = self._get_child_by_type(node, "identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{parent_id}.{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="method",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_method_signature(node),
            docstring=self._get_javadoc(node, content),
            parent_id=parent_id,
            calls=self._extract_calls(node, content),
            language="java",
        )

    def _extract_constructor(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: str,
    ) -> Optional[CodeEntity]:
        """Extract a constructor declaration."""
        name_node = self._get_child_by_type(node, "identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{parent_id}.{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="constructor",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_constructor_signature(node),
            docstring=self._get_javadoc(node, content),
            parent_id=parent_id,
            calls=self._extract_calls(node, content),
            language="java",
        )

    def _get_child_by_type(self, node: Node, type_name: str) -> Optional[Node]:
        """Find the first child node of a given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _get_superclass(self, node: Node) -> Optional[str]:
        """Get the superclass from a class declaration."""
        for child in node.children:
            if child.type == "superclass":
                type_id = self._get_child_by_type(child, "type_identifier")
                if type_id and type_id.text:
                    return type_id.text.decode("utf-8")
        return None

    def _get_interfaces(self, node: Node) -> list[str]:
        """Get implemented interfaces from a class declaration."""
        interfaces: list[str] = []
        for child in node.children:
            if child.type == "super_interfaces":
                for c in child.children:
                    if c.type == "type_identifier" and c.text:
                        interfaces.append(c.text.decode("utf-8"))
                    elif c.type == "type_list":
                        for t in c.children:
                            if t.type == "type_identifier" and t.text:
                                interfaces.append(t.text.decode("utf-8"))
        return interfaces

    def _get_extended_interfaces(self, node: Node) -> list[str]:
        """Get extended interfaces from an interface declaration."""
        extends: list[str] = []
        for child in node.children:
            if child.type == "extends_interfaces":
                for c in child.children:
                    if c.type == "type_identifier" and c.text:
                        extends.append(c.text.decode("utf-8"))
                    elif c.type == "type_list":
                        for t in c.children:
                            if t.type == "type_identifier" and t.text:
                                extends.append(t.text.decode("utf-8"))
        return extends

    def _get_class_signature(self, node: Node) -> str:
        """Build class signature string."""
        modifiers = self._get_modifiers(node)
        name_node = self._get_child_by_type(node, "identifier")
        name = name_node.text.decode("utf-8") if name_node and name_node.text else ""

        extends = self._get_superclass(node)
        implements = self._get_interfaces(node)

        signature = f"{modifiers}class {name}"
        if extends:
            signature += f" extends {extends}"
        if implements:
            signature += f" implements {', '.join(implements)}"

        return signature

    def _get_method_signature(self, node: Node) -> str:
        """Build method signature string."""
        modifiers = self._get_modifiers(node)

        # Get return type
        return_type = ""
        for child in node.children:
            if child.type in (
                "type_identifier",
                "void_type",
                "generic_type",
                "array_type",
            ):
                return_type = child.text.decode("utf-8") if child.text else ""
                break
            elif child.type == "integral_type" or child.type == "floating_point_type":
                return_type = child.text.decode("utf-8") if child.text else ""
                break

        name_node = self._get_child_by_type(node, "identifier")
        name = name_node.text.decode("utf-8") if name_node and name_node.text else ""

        params = self._get_child_by_type(node, "formal_parameters")
        params_text = params.text.decode("utf-8") if params and params.text else "()"

        return f"{modifiers}{return_type} {name}{params_text}"

    def _get_constructor_signature(self, node: Node) -> str:
        """Build constructor signature string."""
        modifiers = self._get_modifiers(node)

        name_node = self._get_child_by_type(node, "identifier")
        name = name_node.text.decode("utf-8") if name_node and name_node.text else ""

        params = self._get_child_by_type(node, "formal_parameters")
        params_text = params.text.decode("utf-8") if params and params.text else "()"

        return f"{modifiers}{name}{params_text}"

    def _get_modifiers(self, node: Node) -> str:
        """Get access modifiers and other modifiers."""
        modifiers: list[str] = []
        for child in node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if mod.text:
                        modifiers.append(mod.text.decode("utf-8"))
        return " ".join(modifiers) + " " if modifiers else ""

    def _get_javadoc(self, node: Node, content: bytes) -> Optional[str]:
        """Extract Javadoc comment before a node."""
        # Check prev_sibling for different comment types
        sibling = node.prev_sibling
        while sibling:
            if sibling.type in ("comment", "block_comment"):
                comment = sibling.text.decode("utf-8") if sibling.text else ""
                if comment.startswith("/**"):
                    # Extract content from Javadoc
                    lines = comment[3:-2].strip().split("\n")
                    cleaned = []
                    for line in lines:
                        line = line.strip()
                        if line.startswith("*"):
                            line = line[1:].strip()
                        if line and not line.startswith("@"):
                            cleaned.append(line)
                    return " ".join(cleaned) if cleaned else None
            # Stop if we hit non-whitespace content
            elif sibling.type not in ("line_comment", "block_comment", "comment"):
                break
            sibling = sibling.prev_sibling
        return None

    def _extract_calls(self, node: Node, content: bytes) -> list[str]:
        """Extract method calls from a node."""
        calls: set[str] = set()

        def walk(n: Node) -> None:
            if n.type == "method_invocation":
                # Get the method name
                name_node = self._get_child_by_type(n, "identifier")
                if name_node and name_node.text:
                    calls.add(name_node.text.decode("utf-8"))

            for child in n.children:
                walk(child)

        # Walk the method body
        body = self._get_child_by_type(node, "block")
        if body:
            walk(body)

        return list(calls)
