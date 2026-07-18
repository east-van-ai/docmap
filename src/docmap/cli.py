#!/usr/bin/env python3
"""
# ==============================================
# East Van AI -- AI for the rest of us!
# https://github.com/east-van-ai
# contact: east-van-ai@proton.me
# ==============================================
#
# ~~~ ~~~ ~~~ ~~~ docmap ~~~ ~~~ ~~~ ~~~
#
# cli.py -- entry point for docmap.
#
# Walk a project directory, find Python files, and emit a YAML manifest of
# every function and class definition along with the first line of its
# docstring. Designed as a lightweight "what exists right now" index to pair
# with DESIGN.md (intent) and git log (history) when kicking off a thread.
#
# Usage:
#    docmap [--include-private] [--include-tests] [--out FILE] [--force] [ROOT]
#
#    ROOT               project root to walk, always the last argument.
#                       Bare `docmap` prints this help; walking the current
#                       directory is an explicit `docmap .`
#    --include-private  include functions/methods starting with a single
#                       underscore (dunders are always skipped)
#    --include-tests    include files under test directories / test_*.py
#    --out FILE         write YAML to FILE instead of stdout
#    --force            walk a root that failed the system-root safety check
#
# Exit codes: 0 success; 1 any docmap-raised error (usage, bad root,
# guardrail refusals); 2 argparse's own errors.
#
# License: MIT
# ==============================================
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Directories we never want to walk into.
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "data",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "build",
    "dist",
    ".eggs",
    ".tox",
    ".idea",
    ".vscode",
}

# Top-level directory names that, when clustered together at a root,
# strongly suggest "this is an OS root" rather than "this is a project."
# Seeing a couple of these alone is normal (a project might have a "lib"
# folder); seeing several together at the same level is the real signal.
OS_ROOT_MARKERS = {
    "bin",
    "sbin",
    "etc",
    "proc",
    "sys",
    "usr",
    "lib",
    "lib64",
    "boot",
    "dev",
    "opt",
    "var",
    "mnt",
    "media",
    "Library",
    "System",
    "Applications",
    "Volumes",
    "Windows",
    "Program Files",
    "Program Files (x86)",
}

# If a root directory contains this many top-level entries or more,
# it's almost certainly not a hand-built project directory.
SUSPICIOUS_TOPLEVEL_COUNT = 30

# Hard ceiling on total .py files found mid-walk. If we cross this,
# something is wrong (wrong root, accidental vendor/ or node_modules
# leak, etc.) and we bail loudly rather than grind on for ten minutes.
MAX_PY_FILES = 5000


def smells_like_system_root(root: Path) -> str:
    """Return a non-empty reason string if root looks like an OS root,
    or an empty string if it looks like an ordinary project directory.
    """
    try:
        entries = list(root.iterdir())
    except (PermissionError, OSError) as e:
        return f"cannot list {root}: {e}"

    names = {e.name for e in entries}
    hits = names & OS_ROOT_MARKERS
    if len(hits) >= 3:
        return f"root contains {len(hits)} OS-root-like dirs: {sorted(hits)}"

    if len(entries) >= SUSPICIOUS_TOPLEVEL_COUNT:
        return f"root has {len(entries)} top-level entries (>= {SUSPICIOUS_TOPLEVEL_COUNT}), unusual for a project"

    if root == Path(root.anchor):
        return f"root {root} is a filesystem anchor (drive/volume root)"

    return ""


# File/dir name fragments that mark something as test-related.
TEST_MARKERS = {"test", "tests", "conftest"}


def is_hidden(path: Path) -> bool:
    """Return True if the path's own name starts with a dot."""
    return path.name.startswith(".")


def should_skip_dir(path: Path, include_tests: bool) -> bool:
    """Return True if a directory should never be walked into."""
    if path.name in SKIP_DIRS:
        return True
    if is_hidden(path):
        return True
    if not include_tests and path.name.lower() in {"test", "tests"}:
        return True
    return False


def is_test_file(path: Path) -> bool:
    """Return True if the file name marks it as test code."""
    stem = path.stem.lower()
    return stem.startswith("test_") or stem.endswith("_test") or stem == "conftest"


def first_doc_sentence(node) -> str:
    """Extract the first sentence of a docstring, regardless of line breaks.

    Splits on '.', '!', or '?' followed by whitespace/end-of-string, so a
    docstring written as one long paragraph still yields just the first
    sentence, not the whole block.
    """
    doc = ast.get_docstring(node, clean=True)
    if not doc:
        return ""
    doc = " ".join(doc.split())  # collapse all whitespace/newlines to single spaces
    match = re.search(r"[.!?](\s|$)", doc)
    if match:
        return doc[: match.start() + 1].strip()
    return doc.strip()


def format_args(args: ast.arguments) -> str:
    parts = []
    for a in args.posonlyargs:
        parts.append(a.arg)
    for a in args.args:
        parts.append(a.arg)
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    for a in args.kwonlyargs:
        parts.append(a.arg)
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    return ", ".join(parts)


def collect_defs(tree: ast.Module, include_private: bool):
    """Collect top-level and class-level function/class defs with their docstrings."""
    entries = []

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
                if name.startswith("__") and name.endswith("__"):
                    continue
                if name.startswith("_") and not include_private:
                    continue
                qualname = f"{prefix}{name}"
                entries.append(
                    {
                        "name": qualname,
                        "args": format_args(child.args),
                        "doc": first_doc_sentence(child),
                        "line": child.lineno,
                    }
                )
            elif isinstance(child, ast.ClassDef):
                name = child.name
                if name.startswith("_") and not include_private:
                    continue
                qualname = f"{prefix}{name}"
                entries.append(
                    {
                        "name": qualname,
                        "args": "",
                        "doc": first_doc_sentence(child),
                        "line": child.lineno,
                        "is_class": True,
                    }
                )
                visit(child, prefix=f"{qualname}.")
            # Don't descend into function bodies for nested defs by default;
            # keeps the map flat and focused on the public-ish surface.

    visit(tree)
    return entries


def yaml_escape(s: str) -> str:
    """Minimal YAML-safe quoting for a scalar string value."""
    if s == "":
        return '""'
    needs_quote = any(c in s for c in ":#\"'{}[]&*!|>%@`") or s.strip() != s
    if needs_quote:
        escaped = s.replace('"', '\\"')
        return f'"{escaped}"'
    return s


def dump_yaml(file_entries: dict) -> str:
    """Hand-rolled minimal YAML writer, no external deps required."""
    lines = []
    for filepath in sorted(file_entries.keys()):
        defs = file_entries[filepath]
        if not defs:
            continue
        lines.append(f"{filepath}:")
        for d in defs:
            if d.get("is_class"):
                lines.append(f"  - class: {yaml_escape(d['name'])}")
            else:
                sig = f"{d['name']}({d['args']})"
                lines.append(f"  - def: {yaml_escape(sig)}")
            lines.append(f"    doc: {yaml_escape(d['doc'])}")
            lines.append(f"    line: {d['line']}")
    return "\n".join(lines) + "\n"


def walk_project(root: Path, include_private: bool, include_tests: bool):
    """Walk root for .py files, applying filters and the file ceiling.

    Returns a dict of relative path -> collected def entries. Files that
    fail to parse or decode are skipped with a note to stderr, never
    fatally. Crossing the MAX_PY_FILES ceiling aborts the whole run --
    it means the wrong root got passed in, and --force does not bypass
    this one.
    """
    file_entries = {}
    py_count = 0
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if any(should_skip_dir(Path(p), include_tests) for p in rel_parts[:-1]):
            continue
        if is_hidden(path):
            continue
        if not include_tests and is_test_file(path):
            continue

        py_count += 1
        if py_count > MAX_PY_FILES:
            print(
                f"docmap: found more than {MAX_PY_FILES} .py files under {root}, "
                f"this almost certainly isn't a single project. Aborting walk.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"# skipped {path}: {e}", file=sys.stderr)
            continue

        entries = collect_defs(tree, include_private)
        rel = str(path.relative_to(root))
        file_entries[rel] = entries

    return file_entries


USAGE = (
    "Usage: docmap [--include-private] [--include-tests] [--out FILE] " "[--force] ROOT"
)


def main():
    """Parse arguments, enforce the CLI grammar, and emit the map."""
    parser = argparse.ArgumentParser(
        prog="docmap",
        description="Generate a YAML docstring manifest for a project.",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="project root to walk, always the last argument",
    )
    parser.add_argument(
        "--include-private", action="store_true", help="include single-underscore names"
    )
    parser.add_argument(
        "--include-tests", action="store_true", help="include test files/dirs"
    )
    parser.add_argument("--out", default=None, help="write to file instead of stdout")
    parser.add_argument(
        "--force", action="store_true", help="skip the system-root safety check"
    )
    args = parser.parse_args()

    if len(sys.argv) == 1:

        # a human typed bare `docmap`
        if sys.stdin.isatty():
            print(__doc__, file=sys.stdout)
            sys.exit(0)

        # piped input, real usage error -- docmap maps directories, not streams
        print("docmap: missing ROOT; docmap takes no piped input.", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    # Flags first, root last -- enforced, not just documented. argparse
    # accepts the root anywhere; see DESIGN.md "CLI Grammar" for why
    # other orders are rejected on purpose.
    if args.root is not None and sys.argv[-1] != args.root:
        print("docmap: the root must be the last argument.", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    if args.root is None:
        print("docmap: missing ROOT argument.", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"docmap: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    if not args.force:
        reason = smells_like_system_root(root)
        if reason:
            print(f"docmap: refusing to walk {root}: {reason}", file=sys.stderr)
            print("if you really mean it, rerun with --force", file=sys.stderr)
            sys.exit(1)

    file_entries = walk_project(root, args.include_private, args.include_tests)
    yaml_text = dump_yaml(file_entries)

    if args.out:
        try:
            Path(args.out).write_text(yaml_text, encoding="utf-8")
        except OSError as e:
            print(f"docmap: cannot write '{args.out}': {e}", file=sys.stderr)
            sys.exit(1)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(yaml_text)


if __name__ == "__main__":
    main()
