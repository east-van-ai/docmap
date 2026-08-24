---
name: docmap
description: Generate a YAML manifest that maps every function and class in a Python project to its docstring's first sentence and line number, using the docmap CLI. Use this skill whenever the user wants a map or index of a Python codebase's functions/classes, wants to hand a Python project's "public surface" to someone (human or AI) without pasting whole files, mentions "docmap", or asks what functions/classes exist in a project and where they're defined. Use it proactively, without being asked, before touching code you have not read this session when the change reaches past a single file. Always use this instead of grepping for `def`/`class` and counting line numbers by hand, which misses docstrings and method qualnames, and drifts out of date immediately.
---

# docmap: YAML function/class map for Python projects

`docmap` walks a Python project and emits a YAML manifest: every top-level and
class-level function/class, the first sentence of its docstring, and its
1-indexed line number. It is a "what exists right now" index. Hand over the
map, not the territory.

## When to run it

Reach for it before touching code you have not read this session, whenever the
task reaches past a single file: a change spanning modules, a plan that has to
say where new code goes, or any question shaped like "where does X live" or
"does this already exist". Its output is what makes a ranged read possible, so
it replaces opening files to find out what is in them.

Skip it for a task confined to a file already open in the session, or a
question one grep answers. Re-run it rather than trusting an earlier run in a
session that has since moved code around.

Not a start-of-session ritual. Running it before knowing what the task needs
is the speculative load it exists to prevent.

Never grep for `def`/`class` and hand-assemble this yourself. That misses
dotted method qualnames, docstring-derived summaries, and the filtering rules
below (tests, dunders, `__pycache__`). The tool exists to get all of that
right consistently.

## Basic usage

```bash
docmap print PATH [--include-private] [--include-tests] [--force]
docmap --version
```

- PATH comes before the flags. `docmap print . --force` is right;
  `docmap print --force .` is a usage error.
- Bare `docmap` is not an error. It prints the usage banner and exits 0, and
  so does `docmap print` on its own.
- `--version` prints the installed version and exits 0. It belongs to `docmap`
  itself, so `docmap print --version` is an unknown flag, exit 2.
- `docmap` does not read piped input; its unit of work is a directory, not a
  stream.
- Output goes to stdout. A shell redirect writes it to a file:
  `docmap print . > map.yaml`

## Typical workflow

1. Run it against the project root, or a single subpackage if you only need
   part of the map:

   ```bash
   docmap print src/
   ```

2. Read the YAML. Each top-level key is a file path relative to the root, and
   under it sits a list of `def`/`doc`/`line` entries. Methods carry dotted
   qualnames like `Foo.bar`.

3. Use it to orient. Jump straight to a definition with a ranged read or
   `vim +<line> <file>` instead of reading the whole file.

## What is filtered out by default

- Noise directories: `.git`, `__pycache__`, `.venv`, `venv`, `env`,
  `node_modules`, `.pytest_cache`, `.mypy_cache`, `build`, `dist`, `.eggs`,
  `.tox`, `.idea`, `.vscode`, and any hidden directory.
- Test files (`test_*.py`, `*_test.py`, `conftest.py`) and `test`/`tests`
  directories. Pass `--include-tests` to map them too.
- Dunder methods (`__init__`, `__repr__`, and the rest) are always skipped and
  no flag brings them back. Single-underscore names are skipped unless
  `--include-private` is passed.
- Nested defs *inside* function bodies are deliberately not descended into.
  The map stays flat, showing the public-ish surface, not every closure.

## Safety rails

These are intentional. Do not fight them.

- Refuses to walk a directory that looks like an OS root: clustered dirs like
  `bin`/`etc`/`usr`, an unusually large number of top-level entries, or a
  filesystem anchor. If the root really is right, pass `--force`.
- Hard ceiling of 5000 `.py` files mid-walk, aborting loudly rather than
  assuming a 5000-file project was meant. This one is **not** bypassed by
  `--force`. Hitting it means the root is almost certainly wrong.
- Files that fail to parse are skipped with a note to stderr, never fatal to
  the whole run.

## Exit codes

- `0`: success, and documentation. A bare word is a question, so it prints
    its usage banner and exits 0, and `--version` answers the same way
- `1`: any error `docmap` raises itself (a usage slip, a root that failed the
    system-root sniff, or either guardrail refusing the walk)
- `2`: argparse's own errors (an unknown command, an unknown flag, or a bad
    value)

## If docmap is not installed

Check with `docmap --version`, which names the version on PATH rather than
only its presence. If it is missing, install it. Python 3.9 or newer, no
runtime dependencies:

```bash
pipx install "git+https://github.com/east-van-ai/docmap.git"
```

If pipx or the network is unavailable but the repo is on disk, run it from
source:

```bash
PYTHONPATH=/path/to/docmap/src python3 -m docmap.cli print PATH
```
