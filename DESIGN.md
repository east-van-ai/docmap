# docmap DESIGN

## Architecture

`docmap` requires Python 3.9 or newer and uses the standard library
only, with no runtime dependencies (`ast`, `argparse`, `pathlib`,
`re`, `sys`). The hand-rolled YAML writer exists precisely to keep it
that way; do not add runtime dependencies. The GitHub CI matrix tests
Python 3.9 through 3.14.

The whole implementation is one module, `src/docmap/cli.py`: pure
functions with one job each, plus a `main()` that wires them into a
pipeline. Data is plain dicts and strings; the only state is the
filesystem being read.

## File Tree

Trimmed view of the layout

```text
.
├── src/
│   └── docmap/
│       ├── __init__.py
│       └── cli.py
├── tests/
│   ├── conftest.py
│   ├── test_cli_integration.py
│   ├── test_extraction.py
│   └── test_walking.py
├── CHANGELOG.md
├── CLAUDE.md
├── DESIGN.md
├── LICENSE
├── pyproject.toml
└── README.md
```

## CLI Grammar

The walk target is a named option, not a positional:
`docmap --src-root PATH [--include-private] [--include-tests] [--out FILE] [--force]`.
Flag order is free, because `--src-root` is unambiguous anywhere on
the command line. An earlier revision used a bare `ROOT` positional
with an enforced root-must-be-last rule. The fixed slot existed to
keep the positional unambiguous next to future flags. A named option
carries its own label, so both the positional and the position rule
are gone. Sibling project `mdmap` still uses the positional-last
grammar and will converge on this shape later.

Bare `docmap` on a TTY prints the module docstring (the usage banner)
and exits 0. Walking the current directory costs one explicit flag,
`docmap --src-root .`. That deliberately echoes the guardrail posture
below, where the harmless invocation is the default and anything that
touches the filesystem tree is asked for by name.

`docmap` takes no piped input: its unit of work is a directory, not a
stream. Bare `docmap` with stdin attached to a pipe is therefore a
usage error (exit 1), not a help dump. Printing help to stdout in the
middle of a pipeline would silently pollute it with exit 0, and an
error is the honest signal.

Exit codes:

- `0` is success: a map was emitted, or bare-on-TTY printed help.
- `1` covers every error docmap raises itself, meaning usage errors,
  a root that is not a directory, and both guardrail refusals below.
- `2` is argparse's own errors (unknown flag, bad value), argparse's
  convention, left untouched.

All self-raised errors go to stderr as `docmap: <message>`. Usage
errors additionally print the usage line; the sniff refusal prints the
exact `--force` re-run hint instead, since the fix there is a flag,
not a different grammar.

## The Guardrails

docmap's distinguishing concern. The business logic is a read-only
walk, but the walk is aimed by a single `--src-root` value, and the
cost of aiming it wrong is grinding through an OS root or a monorepo
parent for minutes, then emitting a useless map of the world. The
guardrails exist to make the wrong invocation loud and cheap instead
of slow and silent.

1. **Root sniff** (`smells_like_system_root`). Refuses to walk a root
   that doesn't look like a project, on three heuristics:
   - A *cluster* of OS-root marker names (`bin`, `etc`, `usr`,
     `Library`, `Windows`, ...) at the top level. One alone is
     normal, since plenty of projects have a `lib/`. Three or more
     together at the same level is the real signal.
   - Thirty or more top-level entries. Hand-built project roots are
     small; home directories and drive roots are not.
   - The root is a filesystem anchor (`/`, a drive, a volume).

   `--force` is the single escalation past the sniff, the same
   posture as `mdmap`'s `--apply`: the default invocation is safe,
   the risky step costs one deliberate token. Refusal, not a
   confirmation prompt. docmap is built to run non-interactively at
   session start and inside scripts, where a prompt would hang, and
   a refusal carrying the exact re-run flag is script-friendly and
   just as explicit.

2. **File ceiling.** A hard cap of 5000 `.py` files counted mid-walk.
   This is the second net, for wrong roots that pass the sniff: a
   vendored `node_modules`-style leak, or a parent directory holding
   fifty checkouts. Crossing it means "this almost certainly isn't a
   single project", so docmap aborts loudly (exit 1) rather than
   grind on. It is deliberately *not* overridable by `--force`;
   `--force` vouches for the root looking odd, not for unbounded
   output.

3. **Default filters.** VCS/cache/build/venv directories, hidden
   files and directories, and test files are skipped by default (see
   README for the list). This is a guardrail in the small: the map is
   meant to show a project's own public-ish surface, and every
   filtered entry is noise that would drown it.

## The Walk/Extract Pipeline

`main()` runs: parse args -> grammar guards (missing src-root, bare
invocation, stdin) -> root checks (is a directory, root sniff) ->
`walk_project` -> `dump_yaml` -> stdout or `--out FILE`.

- `walk_project` does a sorted `rglob("*.py")` under the root,
  applying the filters (`should_skip_dir`, `is_test_file`, hidden
  checks) and the file ceiling. Each surviving file is read and
  `ast.parse`d; a file that fails to parse or decode is skipped with
  a note to stderr, never fatally, since one broken file shouldn't
  cost the map of the other two hundred.
- `collect_defs` walks the AST of one module: top-level and
  class-level defs only, with dotted qualnames for methods
  (`Foo.bar`, `Foo.Inner.baz`). It deliberately does **not** descend
  into function bodies, because nested defs are implementation
  detail. The map stays flat, showing the public-ish surface. Dunders
  are always skipped; single-underscore names are skipped unless
  `--include-private`.
- `first_doc_sentence` extracts the first sentence of a docstring
  regardless of line breaks, splitting on `.`, `!`, or `?` followed
  by whitespace or end-of-string. A one-paragraph docstring yields
  one sentence, not the whole block.

## YAML Output Shape

One mapping per file (path relative to the root), each holding a list
of entries:

```yaml
src/docmap/cli.py:
  - def: "collect_defs(tree, include_private)"
    doc: "Collect top-level and class-level function/class defs with their docstrings."
    line: 177
  - class: Walker
    doc: ""
    line: 40
```

`dump_yaml` and `yaml_escape` are hand-rolled: the zero-dependency
rule is worth more than full YAML generality, and the output grammar
is tiny, being keys, two-space indented list items, and scalar
strings. `yaml_escape` quotes only when it must (YAML-significant
characters or surrounding whitespace), so the common case stays clean
to read. Files with no surviving entries are omitted entirely.

## Open Questions

- Module-level constants and assignments are not captured; undecided
  whether they belong on the map. Nothing forces the issue yet.
- `--out` overwrites without ceremony. A plan/apply split like
  `mdmap`'s doesn't obviously pay for itself here (the default is
  already a dry run to stdout), but it hasn't been ruled out.

## Known Bugs

Confirmed defects, recorded here until fixed. This file is the bug
tracker, since a solo project doesn't need GitHub Issues.

None currently open.

## Use of AI

Both the use of AI and its disclosure are deliberate. Code and
documentation in this project are written in collaboration with
Artificial Intelligence (AI). The division of labor: the AI explores,
challenges assumptions and edge cases, and drafts; the human
initiates, drafts the designs, explores alongside the AI, reviews
every change, and decides what gets committed.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
