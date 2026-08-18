# docmap - YAML map of a Python project

Walk a Python project and emit a YAML manifest of every function and
class, paired with the first sentence of its docstring and the line
it's defined on.

## Why

Handing a codebase to a collaborator, human or AI, usually means
pasting whole files. Most of every file is implementation detail.
What the reader needs first is a map: what exists, what it's called,
what it claims to do, and where it lives.

`docmap` emits exactly that: every function and class signature, the
first sentence of its docstring, and its 1-indexed line number, as
minimal YAML. Built as a "what exists right now" index, to pair with
`DESIGN.md` for intent and `git log --oneline` for history at the
start of an AI-assisted coding session. You hand over the map, not
the territory. `vim +177 src/docmap/cli.py` drops a human on the
exact def, and an AI assistant can do the same with a ranged read
instead of pulling whole files into its context window.

## Example output

```yaml
src/docmap/cli.py:
  - def: "first_doc_sentence(node)"
    doc: "Extract the first sentence of a docstring, regardless of line breaks."
    line: 145
  - def: "collect_defs(tree, include_private)"
    doc: "Collect top-level and class-level function/class defs with their docstrings."
    line: 177
```

- One mapping per file, paths relative to the root, files sorted
- Line numbers are 1-indexed, matching what your editor expects
- Methods carry dotted qualnames (`Foo.bar`, `Foo.Inner.baz`)
- Nested defs inside function bodies are deliberately not descended
  into, so the map stays flat and shows the public-ish surface

## Install

`docmap` requires Python 3.9 or newer and has no runtime
dependencies: standard library only. Tested in CI on Python 3.9
through 3.14.

```bash
pipx install "git+https://github.com/east-van-ai/docmap.git"
```

No dependencies to worry about, this is a small, self-contained tool.

## Usage

```bash
docmap --src-root PATH [--include-private] [--include-tests] [--out FILE] [--force]
```

- `--src-root PATH` names the directory to walk. Flag order is free.
  (Curious about the grammar? See the "CLI Grammar" section of
  [DESIGN.md](DESIGN.md).)
- Bare `docmap` prints this usage information. Walking the current
  directory is an explicit `docmap --src-root .`
- `--include-private` includes single-underscore names. Dunders are
  always skipped.
- `--include-tests` includes files under test directories and
  `test_*.py`
- `--out FILE` writes YAML to `FILE` instead of stdout
- `--force` walks a root that failed the safety sniff (see below)

Exit codes: `0` success, `1` for any error docmap raises itself
(usage errors, bad root, safety refusals), `2` for argparse's own
errors. `docmap` does not read piped input: its unit of work is a
directory, not a stream.

### What it filters out by default

- `.git`, `__pycache__`, `.venv`, `venv`, `env`, `node_modules`,
  `.pytest_cache`, `.mypy_cache`, `build`, `dist`, `.eggs`, `.tox`,
  `.idea`, `.vscode`, and any hidden directory
- Test files (`test_*.py`, `*_test.py`, `conftest.py`) and directories
  named `test`/`tests`, unless `--include-tests` is passed
- Dunder methods (`__init__`, `__repr__`, etc.) always;
  single-underscore names unless `--include-private` is passed

### Safety rails

`docmap` refuses to walk a directory that looks like an OS root (a
cluster of dirs like `bin`, `etc`, `usr`; an unusually large number of
top-level entries; or a filesystem anchor like `/`). Pass `--force` if
you really mean it.

It also caps out at 5000 `.py` files mid-walk and aborts loudly, on
the assumption that crossing that ceiling means the wrong root got
passed in, not that you have a 5000-file Python project. The rationale
for both rails lives in the "The Guardrails" section of
[DESIGN.md](DESIGN.md).

## Notes

- Works on any directory tree of `.py` files. Files that fail to
  parse are skipped with a note to stderr, never fatally.
- The YAML writer is hand-rolled to keep the tool zero-dependency

## Use of AI

This project is built with Artificial Intelligence (AI), deliberately
and in the open. Code and documentation are written in collaboration
with remote and local AI; design decisions, code review, and final
judgment stay human.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
