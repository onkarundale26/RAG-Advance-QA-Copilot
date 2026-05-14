"""AST-aware code chunking via tree-sitter.

Java: one chunk per top-level class, plus one per method/constructor.
TS/JS: one chunk per function_declaration, method_definition, class_declaration,
       and Playwright `test(...)` call expressions (test blocks).

Each chunk includes file path, language, symbol name, kind, and start/end lines.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

# Lazy globals
_JAVA_LANG = None
_TS_LANG = None
_JAVA_PARSER = None
_TS_PARSER = None


def _get_java():
    global _JAVA_LANG, _JAVA_PARSER
    if _JAVA_PARSER is not None:
        return _JAVA_PARSER
    import tree_sitter_java
    from tree_sitter import Language, Parser
    _JAVA_LANG = Language(tree_sitter_java.language())
    _JAVA_PARSER = Parser(_JAVA_LANG)
    return _JAVA_PARSER


def _get_ts():
    global _TS_LANG, _TS_PARSER
    if _TS_PARSER is not None:
        return _TS_PARSER
    import tree_sitter_typescript
    from tree_sitter import Language, Parser
    _TS_LANG = Language(tree_sitter_typescript.language_typescript())
    _TS_PARSER = Parser(_TS_LANG)
    return _TS_PARSER


def _node_text(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _child_field_text(src: bytes, node, field: str) -> Optional[str]:
    n = node.child_by_field_name(field)
    if n is None:
        return None
    return _node_text(src, n)


def _line_span(node) -> tuple[int, int]:
    return node.start_point[0] + 1, node.end_point[0] + 1


# ----------------------- Java ----------------------------------------------

JAVA_SYMBOL_KINDS = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "method_declaration": "method",
    "constructor_declaration": "constructor",
}


def _java_walk(src: bytes, node, file_path: str, package: str | None,
               class_stack: list[str], out: list[dict]) -> None:
    kind = JAVA_SYMBOL_KINDS.get(node.type)
    name: str | None = None
    if kind:
        name = _child_field_text(src, node, "name")
        full = ".".join([*class_stack, name]) if name else None
        if kind in ("class", "interface", "enum"):
            new_stack = class_stack + ([name] if name else [])
        else:
            new_stack = class_stack

        # Emit chunk
        start, end = _line_span(node)
        text = _node_text(src, node)
        out.append({
            "id": f"{file_path}:{start}-{end}:{kind}:{name or 'anon'}",
            "text": text,
            "metadata": {
                "language": "java",
                "path": file_path,
                "package": package,
                "kind": kind,
                "symbol": name,
                "qualified": full,
                "start_line": start,
                "end_line": end,
            },
        })

        if kind in ("class", "interface", "enum"):
            for child in node.children:
                _java_walk(src, child, file_path, package, new_stack, out)
        return

    for child in node.children:
        _java_walk(src, child, file_path, package, class_stack, out)


def chunk_java_file(path: Path, repo_root: Path) -> list[dict]:
    parser = _get_java()
    src = path.read_bytes()
    if not src.strip():
        return []
    tree = parser.parse(src)
    rel = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)
    package = None
    for child in tree.root_node.children:
        if child.type == "package_declaration":
            for c in child.children:
                if c.type == "scoped_identifier" or c.type == "identifier":
                    package = _node_text(src, c)
                    break
            break
    out: list[dict] = []
    _java_walk(src, tree.root_node, rel, package, [], out)
    return out


# ----------------------- TS / JS -------------------------------------------

TS_SYMBOL_KINDS = {
    "function_declaration": "function",
    "method_definition": "method",
    "class_declaration": "class",
    "abstract_class_declaration": "class",
    "interface_declaration": "interface",
    "function_signature": "function",
}


def _ts_call_test_title(src: bytes, node) -> Optional[str]:
    """If node is a Playwright/Mocha-style test(...) call, return the title arg."""
    if node.type != "call_expression":
        return None
    func = node.child_by_field_name("function")
    if func is None:
        return None
    fname = _node_text(src, func)
    base = fname.split(".")[-1]
    if base not in ("test", "it", "describe"):
        return None
    args = node.child_by_field_name("arguments")
    if args is None:
        return None
    for c in args.children:
        if c.type in ("string", "template_string"):
            t = _node_text(src, c).strip("'\"`")
            return t[:200] if t else None
    return None


def _ts_walk(src: bytes, node, file_path: str, parents: list[str],
             out: list[dict]) -> None:
    kind = TS_SYMBOL_KINDS.get(node.type)
    if kind:
        name = _child_field_text(src, node, "name") or "anon"
        full = ".".join([*parents, name])
        start, end = _line_span(node)
        out.append({
            "id": f"{file_path}:{start}-{end}:{kind}:{name}",
            "text": _node_text(src, node),
            "metadata": {
                "language": "typescript",
                "path": file_path,
                "kind": kind,
                "symbol": name,
                "qualified": full,
                "start_line": start,
                "end_line": end,
            },
        })
        new_parents = parents + [name] if kind in ("class", "interface") else parents
        for child in node.children:
            _ts_walk(src, child, file_path, new_parents, out)
        return

    title = _ts_call_test_title(src, node)
    if title is not None:
        start, end = _line_span(node)
        out.append({
            "id": f"{file_path}:{start}-{end}:test:{title[:60]}",
            "text": _node_text(src, node),
            "metadata": {
                "language": "typescript",
                "path": file_path,
                "kind": "test",
                "symbol": title,
                "test_title": title,
                "start_line": start,
                "end_line": end,
            },
        })

    for child in node.children:
        _ts_walk(src, child, file_path, parents, out)


def chunk_ts_file(path: Path, repo_root: Path) -> list[dict]:
    parser = _get_ts()
    src = path.read_bytes()
    if not src.strip():
        return []
    tree = parser.parse(src)
    rel = str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path)
    out: list[dict] = []
    _ts_walk(src, tree.root_node, rel, [], out)
    return out


# ----------------------- Repo walkers --------------------------------------

JAVA_EXTS = {".java"}
TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", ".gradle",
             ".idea", ".vscode", "out", "bin"}


def iter_source_files(root: Path, exts: set[str]) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in exts:
            yield p


def chunk_repo(repo_root: Path, language: str) -> list[dict]:
    """language: 'java' or 'typescript'. Returns list of chunk dicts."""
    if language == "java":
        files = list(iter_source_files(repo_root, JAVA_EXTS))
        chunker = chunk_java_file
    elif language == "typescript":
        files = list(iter_source_files(repo_root, TS_EXTS))
        chunker = chunk_ts_file
    else:
        raise ValueError(f"Unsupported language: {language}")

    chunks: list[dict] = []
    for f in files:
        try:
            file_chunks = chunker(f, repo_root)
        except Exception as e:
            print(f"  WARN: failed to parse {f}: {e}")
            continue
        chunks.extend(file_chunks)
    return chunks
