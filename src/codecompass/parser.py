"""AST parsing to extract code entities from Python files."""

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeEntity:
    """Represents a code entity (function, class, method)."""

    id: str
    name: str
    type: str  # 'function', 'class', 'method'
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_id: Optional[str] = None
    calls: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)


class PythonParser:
    """Parses Python files and extracts code entities."""

    def parse_file(self, file_path: Path) -> tuple[list[CodeEntity], Optional[int]]:
        """Parse a Python file and extract all entities.

        Returns:
            Tuple of (entities list, total line count or None on error)
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            line_count = len(content.splitlines())
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return [], None
        except UnicodeDecodeError as e:
            logger.warning(f"Encoding error in {file_path}: {e}")
            return [], None

        entities = []
        rel_path = str(file_path)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                entities.append(self._extract_function(node, rel_path))
            elif isinstance(node, ast.ClassDef):
                entities.extend(self._extract_class(node, rel_path))

        return entities, line_count

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        parent_id: Optional[str] = None,
    ) -> CodeEntity:
        """Extract a function or method entity."""
        entity_type = "method" if parent_id else "function"
        entity_id = (
            f"{file_path}:{node.name}" if not parent_id else f"{parent_id}.{node.name}"
        )

        return CodeEntity(
            id=entity_id,
            name=node.name,
            type=entity_type,
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=self._get_signature(node),
            docstring=ast.get_docstring(node),
            parent_id=parent_id,
            calls=self._extract_calls(node),
        )

    def _extract_class(
        self,
        node: ast.ClassDef,
        file_path: str,
        parent_id: Optional[str] = None,
    ) -> list[CodeEntity]:
        """Extract a class and its methods, including nested classes."""
        if parent_id:
            # Nested class
            class_id = f"{parent_id}.{node.name}"
        else:
            class_id = f"{file_path}:{node.name}"

        entities = []

        # Extract base classes
        base_classes = [ast.unparse(base) for base in node.bases]

        # Add the class itself
        entities.append(
            CodeEntity(
                id=class_id,
                name=node.name,
                type="class",
                file_path=file_path,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                signature=self._get_class_signature(node),
                docstring=ast.get_docstring(node),
                parent_id=parent_id,
                base_classes=base_classes,
            )
        )

        # Add methods and nested classes
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                entities.append(
                    self._extract_function(child, file_path, parent_id=class_id)
                )
            elif isinstance(child, ast.ClassDef):
                # Recursively handle nested classes
                entities.extend(
                    self._extract_class(child, file_path, parent_id=class_id)
                )

        return entities

    def _get_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Build function signature string with full argument support."""
        args_node = node.args
        parts = []

        # Calculate default value offsets
        # Positional defaults apply to the last N positional args
        num_pos_args = len(args_node.posonlyargs) + len(args_node.args)
        num_pos_defaults = len(args_node.defaults)
        pos_default_start = num_pos_args - num_pos_defaults

        # Build positional-only args (before /)
        arg_index = 0
        for arg in args_node.posonlyargs:
            arg_str = self._format_arg(arg)
            default_idx = arg_index - pos_default_start
            if 0 <= default_idx < len(args_node.defaults):
                arg_str += f"={ast.unparse(args_node.defaults[default_idx])}"
            parts.append(arg_str)
            arg_index += 1

        # Add / separator if there were positional-only args
        if args_node.posonlyargs:
            parts.append("/")

        # Regular args
        for arg in args_node.args:
            arg_str = self._format_arg(arg)
            default_idx = arg_index - pos_default_start
            if 0 <= default_idx < len(args_node.defaults):
                arg_str += f"={ast.unparse(args_node.defaults[default_idx])}"
            parts.append(arg_str)
            arg_index += 1

        # *args or bare * for keyword-only separator
        if args_node.vararg:
            vararg_str = f"*{args_node.vararg.arg}"
            if args_node.vararg.annotation:
                vararg_str += f": {ast.unparse(args_node.vararg.annotation)}"
            parts.append(vararg_str)
        elif args_node.kwonlyargs:
            # Bare * to indicate keyword-only args follow
            parts.append("*")

        # Keyword-only args
        for i, arg in enumerate(args_node.kwonlyargs):
            arg_str = self._format_arg(arg)
            kw_default = (
                args_node.kw_defaults[i] if i < len(args_node.kw_defaults) else None
            )
            if kw_default is not None:
                arg_str += f"={ast.unparse(kw_default)}"
            parts.append(arg_str)

        # **kwargs
        if args_node.kwarg:
            kwarg_str = f"**{args_node.kwarg.arg}"
            if args_node.kwarg.annotation:
                kwarg_str += f": {ast.unparse(args_node.kwarg.annotation)}"
            parts.append(kwarg_str)

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        signature = f"{prefix} {node.name}({', '.join(parts)})"

        # Return type
        if node.returns:
            signature += f" -> {ast.unparse(node.returns)}"

        return signature

    def _format_arg(self, arg: ast.arg) -> str:
        """Format a single argument with optional type annotation."""
        if arg.annotation:
            return f"{arg.arg}: {ast.unparse(arg.annotation)}"
        return arg.arg

    def _get_class_signature(self, node: ast.ClassDef) -> str:
        """Build class signature string."""
        bases = [ast.unparse(base) for base in node.bases]
        if bases:
            return f"class {node.name}({', '.join(bases)})"
        return f"class {node.name}"

    def _extract_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Extract function calls from a function body."""
        calls = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    # e.g., self.method() or obj.method()
                    calls.append(child.func.attr)

        return list(set(calls))  # Remove duplicates
