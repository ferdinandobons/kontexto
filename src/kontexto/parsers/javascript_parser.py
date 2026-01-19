"""Tree-sitter based JavaScript and TypeScript parser."""

import logging
from pathlib import Path
from typing import Optional

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser, Node

from kontexto.parsers.base import BaseParser, CodeEntity, LanguageConfig

logger = logging.getLogger(__name__)


class JavaScriptParser(BaseParser):
    """Tree-sitter based parser for JavaScript and TypeScript source files."""

    def __init__(self) -> None:
        self._js_language = Language(tsjs.language())
        self._ts_language = Language(tsts.language_typescript())
        self._tsx_language = Language(tsts.language_tsx())
        self._parser = Parser()

    @property
    def config(self) -> LanguageConfig:
        return LanguageConfig(
            name="javascript",
            extensions=(".js", ".jsx", ".mjs", ".ts", ".tsx"),
            exclude_patterns=("node_modules", ".npm", "bower_components", "dist"),
        )

    def parse_file(self, file_path: Path) -> tuple[list[CodeEntity], Optional[int]]:
        """Parse a JavaScript/TypeScript file and extract all entities."""
        ext = file_path.suffix.lower()

        # Select appropriate language grammar
        if ext == ".ts":
            self._parser.language = self._ts_language
            lang = "typescript"
        elif ext == ".tsx":
            self._parser.language = self._tsx_language
            lang = "typescript"
        else:
            self._parser.language = self._js_language
            lang = "javascript"

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

        self._extract_entities(tree.root_node, content, rel_path, entities, lang=lang)

        return entities, line_count

    def _extract_entities(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        entities: list[CodeEntity],
        parent_id: Optional[str] = None,
        lang: str = "javascript",
    ) -> None:
        """Recursively extract entities from the AST."""
        for child in node.children:
            # Function declarations
            if child.type in ("function_declaration", "generator_function_declaration"):
                entity = self._extract_function(
                    child, content, file_path, parent_id, lang
                )
                if entity:
                    entities.append(entity)

            # Arrow functions via variable declarations
            elif child.type in ("lexical_declaration", "variable_declaration"):
                self._extract_variable_functions(
                    child, content, file_path, entities, parent_id, lang
                )

            # Class declarations
            elif child.type == "class_declaration":
                class_entities = self._extract_class(
                    child, content, file_path, parent_id, lang
                )
                entities.extend(class_entities)

            # TypeScript interface declarations
            elif child.type == "interface_declaration":
                entity = self._extract_interface(
                    child, content, file_path, parent_id, lang
                )
                if entity:
                    entities.append(entity)

            # TypeScript type alias declarations
            elif child.type == "type_alias_declaration":
                entity = self._extract_type_alias(
                    child, content, file_path, parent_id, lang
                )
                if entity:
                    entities.append(entity)

            # Export statements may contain declarations
            elif child.type in ("export_statement", "export_default_declaration"):
                self._extract_entities(
                    child, content, file_path, entities, parent_id, lang
                )

            # Program node - recurse into children
            elif child.type == "program":
                self._extract_entities(
                    child, content, file_path, entities, parent_id, lang
                )

    def _extract_variable_functions(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        entities: list[CodeEntity],
        parent_id: Optional[str],
        lang: str,
    ) -> None:
        """Extract arrow functions or function expressions from variable declarations."""
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = self._get_child_by_type(child, "identifier")
                value_node = self._get_child_by_type(child, "arrow_function")

                if not value_node:
                    value_node = self._get_child_by_type(child, "function_expression")
                if not value_node:
                    value_node = self._get_child_by_type(child, "function")

                if name_node and value_node:
                    name = name_node.text.decode("utf-8") if name_node.text else ""
                    entity_id = (
                        f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"
                    )

                    entities.append(
                        CodeEntity(
                            id=entity_id,
                            name=name,
                            type="method" if parent_id else "function",
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            signature=self._get_arrow_signature(name, value_node),
                            docstring=self._get_jsdoc(node, content),
                            parent_id=parent_id,
                            calls=self._extract_calls(value_node, content),
                            language=lang,
                        )
                    )

    def _extract_function(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
        lang: str,
    ) -> Optional[CodeEntity]:
        """Extract a function declaration entity."""
        name = self._get_name(node)
        if not name:
            return None

        entity_type = "method" if parent_id else "function"
        entity_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        # Check if async or generator
        is_async = any(c.type == "async" for c in node.children)
        is_generator = "generator" in node.type

        return CodeEntity(
            id=entity_id,
            name=name,
            type=entity_type,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_function_signature(node, is_async, is_generator),
            docstring=self._get_jsdoc(node, content),
            parent_id=parent_id,
            calls=self._extract_calls(node, content),
            language=lang,
        )

    def _extract_class(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
        lang: str,
    ) -> list[CodeEntity]:
        """Extract a class and its methods."""
        name = self._get_name(node)
        if not name:
            return []

        class_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"
        entities: list[CodeEntity] = []

        # Get base class (extends)
        base_classes = self._get_extends(node)

        # Get implemented interfaces (TypeScript)
        implements = self._get_implements(node)
        base_classes.extend(implements)

        entities.append(
            CodeEntity(
                id=class_id,
                name=name,
                type="class",
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=self._get_class_signature(node),
                docstring=self._get_jsdoc(node, content),
                parent_id=parent_id,
                base_classes=base_classes,
                language=lang,
            )
        )

        # Extract methods from class body
        body = self._get_child_by_type(node, "class_body")
        if body:
            for child in body.children:
                if child.type == "method_definition":
                    method = self._extract_method(
                        child, content, file_path, class_id, lang
                    )
                    if method:
                        entities.append(method)
                elif child.type == "public_field_definition":
                    # Arrow function as class field
                    self._extract_class_field_function(
                        child, content, file_path, entities, class_id, lang
                    )

        return entities

    def _extract_method(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: str,
        lang: str,
    ) -> Optional[CodeEntity]:
        """Extract a method from a class."""
        name_node = self._get_child_by_type(node, "property_identifier")
        if not name_node:
            # Could be a computed property or constructor
            for child in node.children:
                if child.type == "property_identifier" or child.text == b"constructor":
                    name_node = child
                    break

        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{parent_id}.{name}"

        is_async = any(c.type == "async" for c in node.children)
        is_generator = any(c.type == "*" for c in node.children)
        is_static = any(c.type == "static" for c in node.children)

        return CodeEntity(
            id=entity_id,
            name=name,
            type="method",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=self._get_method_signature(
                node, is_async, is_generator, is_static
            ),
            docstring=self._get_jsdoc(node, content),
            parent_id=parent_id,
            calls=self._extract_calls(node, content),
            language=lang,
        )

    def _extract_class_field_function(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        entities: list[CodeEntity],
        parent_id: str,
        lang: str,
    ) -> None:
        """Extract arrow functions defined as class fields."""
        name_node = self._get_child_by_type(node, "property_identifier")
        value_node = self._get_child_by_type(node, "arrow_function")

        if name_node and value_node and name_node.text:
            name = name_node.text.decode("utf-8")
            entity_id = f"{parent_id}.{name}"

            entities.append(
                CodeEntity(
                    id=entity_id,
                    name=name,
                    type="method",
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=self._get_arrow_signature(name, value_node),
                    docstring=self._get_jsdoc(node, content),
                    parent_id=parent_id,
                    calls=self._extract_calls(value_node, content),
                    language=lang,
                )
            )

    def _extract_interface(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
        lang: str,
    ) -> Optional[CodeEntity]:
        """Extract a TypeScript interface."""
        name_node = self._get_child_by_type(node, "type_identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        # Get extended interfaces
        extends = self._get_interface_extends(node)

        return CodeEntity(
            id=entity_id,
            name=name,
            type="interface",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=f"interface {name}",
            docstring=self._get_jsdoc(node, content),
            parent_id=parent_id,
            base_classes=extends,
            language=lang,
        )

    def _extract_type_alias(
        self,
        node: Node,
        content: bytes,
        file_path: str,
        parent_id: Optional[str],
        lang: str,
    ) -> Optional[CodeEntity]:
        """Extract a TypeScript type alias."""
        name_node = self._get_child_by_type(node, "type_identifier")
        if not name_node or not name_node.text:
            return None

        name = name_node.text.decode("utf-8")
        entity_id = f"{parent_id}.{name}" if parent_id else f"{file_path}:{name}"

        return CodeEntity(
            id=entity_id,
            name=name,
            type="type",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=f"type {name}",
            docstring=self._get_jsdoc(node, content),
            parent_id=parent_id,
            language=lang,
        )

    def _get_name(self, node: Node) -> str:
        """Get the name identifier from a node."""
        # Try identifier first (JavaScript)
        name_node = self._get_child_by_type(node, "identifier")
        if name_node and name_node.text:
            return name_node.text.decode("utf-8")
        # Try type_identifier (TypeScript classes)
        name_node = self._get_child_by_type(node, "type_identifier")
        if name_node and name_node.text:
            return name_node.text.decode("utf-8")
        return ""

    def _get_child_by_type(self, node: Node, type_name: str) -> Optional[Node]:
        """Find the first child node of a given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _get_function_signature(
        self,
        node: Node,
        is_async: bool = False,
        is_generator: bool = False,
    ) -> str:
        """Build function signature string."""
        name = self._get_name(node)
        params = self._get_child_by_type(node, "formal_parameters")
        params_text = params.text.decode("utf-8") if params and params.text else "()"

        prefix = ""
        if is_async:
            prefix = "async "
        if is_generator:
            prefix += "function* "
        else:
            prefix += "function "

        return f"{prefix}{name}{params_text}"

    def _get_method_signature(
        self,
        node: Node,
        is_async: bool = False,
        is_generator: bool = False,
        is_static: bool = False,
    ) -> str:
        """Build method signature string."""
        name_node = None
        for child in node.children:
            if child.type == "property_identifier" or child.text == b"constructor":
                name_node = child
                break

        name = name_node.text.decode("utf-8") if name_node and name_node.text else ""
        params = self._get_child_by_type(node, "formal_parameters")
        params_text = params.text.decode("utf-8") if params and params.text else "()"

        prefix = ""
        if is_static:
            prefix = "static "
        if is_async:
            prefix += "async "
        if is_generator:
            prefix += "*"

        return f"{prefix}{name}{params_text}"

    def _get_arrow_signature(self, name: str, node: Node) -> str:
        """Build arrow function signature string."""
        params = self._get_child_by_type(node, "formal_parameters")
        if not params:
            # Single parameter without parentheses
            params = self._get_child_by_type(node, "identifier")

        params_text = params.text.decode("utf-8") if params and params.text else "()"
        if not params_text.startswith("("):
            params_text = f"({params_text})"

        is_async = any(c.type == "async" for c in node.children)
        prefix = "async " if is_async else ""

        return f"{prefix}{name} = {params_text} =>"

    def _get_class_signature(self, node: Node) -> str:
        """Build class signature string."""
        name = self._get_name(node)
        extends = self._get_extends(node)

        if extends:
            return f"class {name} extends {extends[0]}"
        return f"class {name}"

    def _get_extends(self, node: Node) -> list[str]:
        """Get the extended class from a class declaration."""
        # Check for class_heritage node
        for child in node.children:
            if child.type == "class_heritage":
                # Could have extends_clause as child, or directly identifier
                for heritage_child in child.children:
                    if heritage_child.type == "extends_clause":
                        for c in heritage_child.children:
                            if c.type == "identifier" and c.text:
                                return [c.text.decode("utf-8")]
                    elif heritage_child.type == "identifier" and heritage_child.text:
                        return [heritage_child.text.decode("utf-8")]
        # Fallback: Check for direct extends_clause child (some tree-sitter versions)
        extends_clause = self._get_child_by_type(node, "extends_clause")
        if extends_clause:
            for c in extends_clause.children:
                if c.type == "identifier" and c.text:
                    return [c.text.decode("utf-8")]
        return []

    def _get_implements(self, node: Node) -> list[str]:
        """Get implemented interfaces from a class declaration (TypeScript)."""
        implements: list[str] = []
        for child in node.children:
            if child.type == "class_heritage":
                for heritage_child in child.children:
                    if heritage_child.type == "implements_clause":
                        for c in heritage_child.children:
                            if c.type == "type_identifier" and c.text:
                                implements.append(c.text.decode("utf-8"))
                            elif c.type == "identifier" and c.text:
                                implements.append(c.text.decode("utf-8"))
        return implements

    def _get_interface_extends(self, node: Node) -> list[str]:
        """Get extended interfaces from an interface declaration."""
        extends: list[str] = []
        for child in node.children:
            if child.type == "extends_type_clause":
                for c in child.children:
                    if c.type == "type_identifier" and c.text:
                        extends.append(c.text.decode("utf-8"))
        return extends

    def _get_jsdoc(self, node: Node, content: bytes) -> Optional[str]:
        """Extract JSDoc comment before a node."""
        # Look for comment node before the current node
        if node.prev_sibling and node.prev_sibling.type == "comment":
            comment = (
                node.prev_sibling.text.decode("utf-8") if node.prev_sibling.text else ""
            )
            if comment.startswith("/**"):
                # Extract content from JSDoc
                lines = comment[3:-2].strip().split("\n")
                cleaned = []
                for line in lines:
                    line = line.strip()
                    if line.startswith("*"):
                        line = line[1:].strip()
                    if line and not line.startswith("@"):
                        cleaned.append(line)
                return " ".join(cleaned) if cleaned else None
        return None

    def _extract_calls(self, node: Node, content: bytes) -> list[str]:
        """Extract function/method calls from a function/method body."""
        calls: set[str] = set()

        def walk(n: Node) -> None:
            if n.type == "call_expression":
                func = self._get_child_by_type(n, "identifier")
                if func and func.text:
                    calls.add(func.text.decode("utf-8"))
                else:
                    # Handle member expression like obj.method()
                    member = self._get_child_by_type(n, "member_expression")
                    if member:
                        prop = self._get_child_by_type(member, "property_identifier")
                        if prop and prop.text:
                            calls.add(prop.text.decode("utf-8"))

            for child in n.children:
                walk(child)

        # Walk only the function body (statement_block), not the entire node
        body = self._get_child_by_type(node, "statement_block")
        if body:
            walk(body)
        else:
            # For arrow functions, the body might be an expression
            # Walk children that are not parameters or identifiers
            for child in node.children:
                if child.type not in (
                    "identifier",
                    "formal_parameters",
                    "type_annotation",
                ):
                    walk(child)

        return list(calls)
