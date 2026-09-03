"""
# ==============================================
# East Van AI -- AI for the rest of us!
# https://github.com/east-van-ai
# contact: east-van-ai@proton.me
# ==============================================
#
# ~~~ ~~~ ~~~ ~~~ ~~~ docmap ~~~ ~~~ ~~~ ~~~ ~~~
#
# Walk a project directory, find Python files, and emit a YAML manifest of
# every function and class definition along with the first sentence of its
# docstring. Designed as a lightweight "what exists right now" index.
#
# Usage:
#
#    docmap print PATH [--include-private] [--include-tests] [--force]
#
# Commands:
#
#    print PATH         walk PATH and print the map to stdout
#
# PATH is the directory to walk, and it is required. Use `.` for the
# current directory. The map goes to stdout, so a shell redirect writes a
# file.
#
# Options:
#
#    --include-private  include functions/methods starting with a single
#                       underscore (dunders are always skipped)
#    --include-tests    include files under test directories / test_*.py
#    --force            walk a root that failed the system-root safety check
#
# PATH comes before the flags, whose order among themselves is free. Bare
# `docmap` prints this text, and so does `docmap print` with nothing after
# it. Asking is not a usage error.
#
# docmap reads no piped input.
#
# Exit codes:
#
#    0:     success, and documentation
#    1:     docmap's own error, a usage slip, a root that failed the safety
#           check, or either guardrail refusing the walk
#    2:     an unknown command, an unknown flag, or a bad value
#
# License: MIT
# ==============================================
"""

import argparse
import ast
import re
import sys
from importlib import metadata
from pathlib import Path

PROG = "docmap"

# Argparse hardcodes 2 in `ArgumentParser.error()`, which calls `sys.exit`
# itself, so EXIT_ARGPARSE is never returned, only asserted against. See
# DESIGN.md, "CLI Grammar", for what the three cover.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ARGPARSE = 2

# Directories we never want to walk into. Only names that cannot plausibly
# hold hand-written source belong here; see DESIGN.md.
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
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


def is_hidden(path: Path) -> bool:
    """Return True if the path's own name starts with a dot."""
    return path.name.startswith(".")


def should_skip_dir(path: Path, include_tests: bool) -> bool:
    """Return True if a directory should never be walked into."""
    if path.name in SKIP_DIRS:
        return True
    if is_hidden(path):
        return True
    return not include_tests and path.name.lower() in {"test", "tests"}


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


USAGE = "docmap print PATH [--include-private] [--include-tests] [--force]"

PRINT_HELP = "Walk PATH and print the map to stdout"


def leading_paths(tokens):
    """Return the tokens ahead of the first flag."""
    paths = []
    for token in tokens:
        if token.startswith("-"):
            break
        paths.append(token)
    return paths


def usage_error(message):
    """Report a command line docmap could not read, with the usage line."""
    print(f"docmap: {message}", file=sys.stderr)
    print(f"Usage: {USAGE}", file=sys.stderr)
    return EXIT_ERROR


def installed_version():
    """Return the version of the installed docmap distribution."""
    try:
        return metadata.version("docmap")
    except metadata.PackageNotFoundError:
        return "unknown (not installed)"


def version_line():
    """Return the program name and the installed version on one line.

    Both spellings call this, so `docmap version` and `docmap --version`
    cannot drift apart.
    """
    return f"{PROG} {installed_version()}"


def build_parser():
    """Construct the argument parser for the whole CLI.

    PATH is optional to argparse so that a bare command word reaches `main`
    and gets an answer instead of a usage error. Its parsed value goes
    unused: `main` reads the slot itself.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Print a YAML docstring manifest for a project.",
    )
    # Top-level only, so `docmap print --version` stays an unknown flag.
    parser.add_argument(
        "--version",
        action="version",
        version=version_line(),
        help="print the installed version and exit",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    printer = subparsers.add_parser("print", help=PRINT_HELP, description=PRINT_HELP)
    printer.add_argument(
        "path", metavar="PATH", nargs="?", help="Project directory to walk"
    )
    printer.add_argument(
        "--include-private", action="store_true", help="include single-underscore names"
    )
    printer.add_argument(
        "--include-tests", action="store_true", help="include test files/dirs"
    )
    printer.add_argument(
        "--force", action="store_true", help="skip the system-root safety check"
    )

    # No arguments and no flags of its own, so a stray word after it is
    # docmap's usage error rather than argparse's.
    subparsers.add_parser("version", help="print the installed version and exit")
    return parser


def main():
    """Parse arguments, enforce the CLI grammar, and print the map.

    A bare word is a question and gets documentation, exit 0. Any other
    shortfall in the PATH slot is a slip and gets an error, exit 1.
    Argparse keeps the vocabulary it owns: an unknown command, an unknown
    flag, or a bad value, exiting 2.
    """
    tokens = sys.argv[1:]

    # A bare word is a question: bare `docmap`, or the command word alone.
    # One command in one file means one document, so both get the banner.
    if not tokens or tokens == ["print"]:
        print(__doc__.strip())
        return EXIT_OK

    parser = build_parser()
    args, extras = parser.parse_known_args(tokens)

    if any(extra.startswith("-") for extra in extras):
        parser.parse_args(tokens)  # argparse names the flag better, exit 2

    # `version` takes no argument, so nothing about it is incomplete: it
    # answers with the number rather than with the banner.
    if args.command == "version":
        strays = leading_paths(tokens[1:])
        if strays:
            return usage_error(f"version takes no arguments: {strays[0]!r}")
        print(version_line())
        return EXIT_OK

    # Not args.path: what argparse resolves from a token after a flag varies
    # by interpreter, and the grammar should not.
    paths = leading_paths(tokens[1:])
    if not paths:
        return usage_error("print needs PATH")
    if len(paths) > 1:
        return usage_error(f"print takes nothing after PATH: {paths[1]!r}")

    root = Path(paths[0]).resolve()
    if not root.is_dir():
        print(f"docmap: {root} is not a directory", file=sys.stderr)
        return EXIT_ERROR

    if not args.force:
        reason = smells_like_system_root(root)
        if reason:
            print(f"docmap: refusing to walk {root}: {reason}", file=sys.stderr)
            print("if you really mean it, rerun with --force", file=sys.stderr)
            return EXIT_ERROR

    file_entries = walk_project(root, args.include_private, args.include_tests)
    sys.stdout.write(dump_yaml(file_entries))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
