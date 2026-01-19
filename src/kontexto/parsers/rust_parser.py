"""Tree-sitter based Rust parser."""

import logging
from pathlib import Path
from typing import Optional

import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser, Node

from kontexto.parsers.base import BaseParser, CodeEntity, LanguageConfig

logger = logging.getLogger(__name__)


class RustParser(BaseParser):
    """Tree-sitter based parser for Rust source files."""

    def __init__(self) -> None:
        self._language = Language(tsrust.language())
        self._parser = Parser(self._language)

    @property
    def config(self) -> LanguageConfig:
        return LanguageConfig(
            name="rust",
            extensions=(".rs",),
            exclude_patterns=("target",),
        )

    def parse_file(self, file_path: Path) -> tuple[list[CodeEntity], Optional[int]]:
        """Parse a Rust file and extract all entities."""
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
            # Function items
            if child.type == "function_item":
                entity = self._extract_function(child, content, file_path, parent_id)
                if entity:
                    entities.append(entity)

            # Struct definitions
            elif child.type == "struct_item":
                entity = self._extract_struct(child, content, file_path)
                if entity:
                    entities.append(entity)

            # Enum definitions
            elif child.type == "enum_item":
                entity = self._extract_enum(child, content, file_path)
                if entity:
                    entities.append(entity)

            # Trait definitions
            elif child.type == "trait_item":
                trait_entities = self._extract_trait(child, content, file_path)
                entities.extend(trait_entities)

            # Impl blocks
            elif child.type == "impl_item":
                impl_entities = self._extract_impl(child, content, file_path)
                entities.extend(impl_entities)

            # Mod items - recurse into module contents
            elif child.type == "mod_item":
                self._extract_mod(child, content, file_path, entities)

    def _extract_function(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
    ) -> Optional[CodeEntity]:
        """Extract a function item."""
        name_node = self._get_child_by_type(node, "identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_type = "method" if parent_id else "function"
        entity_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type=entity_type,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_function_signature(node),
            docstring=self._get_rust_doc(node, content),
            parent_id=parent_id,
            calls=self._extract_calls(node, content),
            language="rust",
        )

    def _extract_struct(
        self,
        node: Node,
        content: bytes,
        file_path: str,
    ) -> Optional[CodeEntity]:
        """Extract a struct definition."""
        name_node = self._get_child_by_type(node, "type_identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{file_path}:{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="struct",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=f"struct {name}",
            docstring=self._get_rust_doc(node, content),
            language="rust",
        )

    def _extract_enum(
        self,
        node: Node,
        content: bytes,
        file_path: str,
    ) -> Optional[CodeEntity]:
        """Extract an enum definition."""
        name_node = self._get_child_by_type(node, "type_identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{file_path}:{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="enum",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=f"enum {name}",
            docstring=self._get_rust_doc(node, content),
            language="rust",
        )

    def _extract_trait(
        self,
        node: Node,
        content: bytes,
        file_path: str,
    ) -> list[CodeEntity]:
        """Extract a trait definition and its methods."""
        name_node = self._get_child_by_type(node, "type_identifier")
        if not name_node or not name_node.text:
            return []

        name = name_node.text.decode("utf-8")
        trait_id = f"{file_path}:{name}"

        entities: list[CodeEntity] = []

        entities.append(
            CodeEntity(
                id=trait_id,
                name=name,
                type="trait",
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=f"trait {name}",
                docstring=self._get_rust_doc(node, content),
                language="rust",
            )
        )

        # Extract trait methods
        body = self._get_child_by_type(node, "declaration_list")
        if body:
            for child in body.children:
                if child.type in ("function_item", "function_signature_item"):
                    method = self._extract_function(child, content, file_path, trait_id)
                    if method:
                        entities.append(method)

        return entities

    def _extract_impl(
        self,
        node: Node,
        content: bytes,
        file_path: str,
    ) -> list[CodeEntity]:
        """Extract an impl block and its methods."""
        # Get the type being implemented
        type_name = self._get_impl_type(node, content)
        if not type_name:
            return []

        # Check if implementing a trait
        trait_name = self._get_impl_trait(node, content)

        if trait_name:
            impl_id = f"{file_path}:{type_name}::{trait_name}"
            impl_name = f"{type_name}::{trait_name}"
            signature = f"impl {trait_name} for {type_name}"
            base_classes = [trait_name]
        else:
            impl_id = f"{file_path}:{type_name}::impl"
            impl_name = type_name
            signature = f"impl {type_name}"
            base_classes = []

        entities: list[CodeEntity] = []

        entities.append(
            CodeEntity(
                id=impl_id,
                name=impl_name,
                type="impl",
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=signature,
                base_classes=base_classes,
                language="rust",
            )
        )

        # Extract impl methods
        body = self._get_child_by_type(node, "declaration_list")
        if body:
            for child in body.children:
                if child.type == "function_item":
                    method = self._extract_function(child, content, file_path, impl_id)
                    if method:
                        entities.append(method)

        return entities

    def _extract_mod(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        entities: list[CodeEntity],
    ) -> None:
        """Extract entities from a mod block."""
        body = self._get_child_by_type(node, "declaration_list")
        if body:
            self._extract_entities(body, content, file_path, entities)

    def _get_impl_type(self, node: Node, content: bytes) -> Optional[str]:
        """Get the type being implemented in an impl block."""
        # Look for "impl Type" or "impl Trait for Type"
        # We need to find the type AFTER "for" if present, otherwise the first type_identifier
        found_for = False
        first_type = None

        for child in node.children:
            if child.text == b"for":
                found_for = True
            elif child.type == "type_identifier" and child.text:
                if found_for:
                    # This is the type after "for"
                    return child.text.decode("utf-8")
                elif first_type is None:
                    first_type = child.text.decode("utf-8")
            elif child.type == "generic_type":
                type_id = self._get_child_by_type(child, "type_identifier")
                if type_id and type_id.text:
                    if found_for:
                        return type_id.text.decode("utf-8")
                    elif first_type is None:
                        first_type = type_id.text.decode("utf-8")

        # If no "for" was found, return the first type (impl Type)
        return first_type

    def _get_impl_trait(self, node: Node, content: bytes) -> Optional[str]:
        """Get the trait being implemented in an impl block (if any)."""
        # Look for "impl Trait for Type" pattern
        found_for = False
        first_type = None

        for child in node.children:
            if child.type == "type_identifier" and child.text:
                if first_type is None:
                    first_type = child.text.decode("utf-8")
            elif child.text == b"for":
                found_for = True
                break

        return first_type if found_for else None

    def _get_child_by_type(self, node: Node, type_name: str) -> Optional[Node]:
        """Find the first child node of a given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _get_function_signature(self, node: Node) -> str:
        """Build function signature string."""
        # Extract visibility, async, const, etc.
        visibility = ""
        is_async = False
        is_const = False
        is_unsafe = False

        for child in node.children:
            if child.type == "visibility_modifier" and child.text:
                visibility = child.text.decode("utf-8") + " "
            elif child.type == "async" or (child.text and child.text == b"async"):
                is_async = True
            elif child.type == "const" or (child.text and child.text == b"const"):
                is_const = True
            elif child.type == "unsafe" or (child.text and child.text == b"unsafe"):
                is_unsafe = True

        name_node = self._get_child_by_type(node, "identifier")
        name = name_node.text.decode("utf-8") if name_node and name_node.text else ""

        params = self._get_child_by_type(node, "parameters")
        params_text = params.text.decode("utf-8") if params and params.text else "()"

        prefix = visibility
        if is_const:
            prefix += "const "
        if is_async:
            prefix += "async "
        if is_unsafe:
            prefix += "unsafe "

        signature = f"{prefix}fn {name}{params_text}"

        # Get return type
        return_type = self._get_child_by_type(node, "return_type")
        if return_type and return_type.text:
            signature += f" {return_type.text.decode('utf-8')}"

        return signature

    def _get_rust_doc(self, node: Node, content: bytes) -> Optional[str]:
        """Extract Rust doc comment before a node."""
        # Look for doc comments (///, //!, /** */)
        comments: list[str] = []

        sibling = node.prev_sibling
        while sibling:
            if sibling.type in ("line_comment", "block_comment"):
                comment = sibling.text.decode("utf-8") if sibling.text else ""
                if comment.startswith("///") or comment.startswith("//!"):
                    comments.insert(0, comment[3:].strip())
                elif comment.startswith("/**"):
                    # Block doc comment
                    content_text = comment[3:-2].strip()
                    lines = [
                        line.strip().lstrip("*").strip()
                        for line in content_text.split("\n")
                    ]
                    comments.insert(0, " ".join(lines))
                else:
                    # Regular comment, stop looking
                    break
                sibling = sibling.prev_sibling
            else:
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
                    # Handle method call like self.method() or obj.method()
                    field_expr = self._get_child_by_type(n, "field_expression")
                    if field_expr:
                        field = self._get_child_by_type(field_expr, "field_identifier")
                        if field and field.text:
                            calls.add(field.text.decode("utf-8"))
                    # Handle scoped calls like Module::function()
                    scoped = self._get_child_by_type(n, "scoped_identifier")
                    if scoped:
                        name = self._get_child_by_type(scoped, "identifier")
                        if name and name.text:
                            calls.add(name.text.decode("utf-8"))

            for child in n.children:
                walk(child)

        # Walk the function body
        body = self._get_child_by_type(node, "block")
        if body:
            walk(body)

        return list(calls)
