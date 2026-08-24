# docmap DESIGN

## Architecture

`docmap` requires Python 3.9 or newer and uses the standard library
only, with no runtime dependencies (`ast`, `argparse`,
`importlib.metadata`, `pathlib`, `re`, `sys`). The hand-rolled YAML
writer exists precisely to keep it that way; do not add runtime
dependencies. The GitHub CI matrix tests Python 3.9 through 3.14.

The whole implementation is one module, `src/docmap/cli.py`: pure
functions with one job each, plus a `main()` that wires them into a
pipeline. Data is plain dicts and strings; the only state is the
filesystem being read.

One module is a decision, not a leftover. The usual split gives a CLI
a file for the parser, a file per command, and a short entry point,
which is what keeps a many-command tool readable. docmap has one
command and one pipeline, and cutting that pipeline across three files
would cost imports and indirection to buy back nothing. The file stays
whole past the point where a line budget would call for the split.

The walk pays the visible price. `walk_project` exits on the file
ceiling rather than returning a code up to `main`, because the count
crosses deep inside the rglob loop and threading a result back out
would put a return path through every caller for one refusal. The
exit code is 1 either way and the message still reads `docmap: ...`
on stderr, so nothing about the contract changes.

docmap writes nothing. It reads, parses, and prints; the map arrives
on stdout, and a shell redirect takes it from there. The guardrails
below still matter, since a wrong PATH costs time and yields a useless
map, but with no write path it can never cost more than that.

## The Guardrails

docmap's distinguishing concern. The business logic is a read-only
walk, but the walk is aimed by a single PATH argument, and the cost of
aiming it wrong is grinding through an OS root or a monorepo parent for
minutes, then emitting a useless map of the world. The guardrails exist
to make the wrong invocation loud and cheap instead of slow and silent.

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
   posture as a plan/apply split: the default invocation is safe,
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

   Membership in `SKIP_DIRS` is narrow on purpose. Only names that
   cannot plausibly hold hand-written source qualify: VCS, caches,
   build output, virtualenvs, editor state. A name does not earn a
   place merely because this project happens to use it that way.
   `data` is the counter-example that put the rule here. It is an
   ordinary package name, so skipping it drops real source from the
   map.

## The Walk/Extract Pipeline

`main()` runs: parse args -> grammar guards (a bare word, then the PATH
slot) -> root checks (is a directory, root sniff) -> `walk_project` ->
`dump_yaml` -> stdout.

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
src/example/cli.py:
  - def: collect_defs(tree, include_private)
    doc: Collect top-level and class-level function/class defs with their docstrings.
    line: 195
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

## CLI Grammar

`docmap print PATH [--include-private] [--include-tests] [--force]`.
The command word sits at `argv[1]` and the walk target at `argv[2]`.
Flags follow PATH, and their order among themselves is free.

| Command line | Result | Exit |
| --- | --- | --- |
| `docmap` | banner | 0 |
| `docmap print` | banner | 0 |
| `docmap --version` | name and installed version | 0 |
| `docmap print PATH` | map on stdout | 0 |
| `docmap print` and flags, no PATH | usage error | 1 |
| `docmap print --force PATH` | usage error, PATH comes first | 1 |
| `docmap print A B` | usage error, nothing after PATH | 1 |
| `docmap print PATH`, PATH not a directory | error | 1 |
| `docmap print PATH --nope` | argparse rejects the flag | 2 |
| `docmap print --version` | argparse rejects the flag | 2 |
| `docmap --src-root .` | argparse rejects the command | 2 |

Positions are decided, not inferred. Argparse from Python 3.12 on
back-fills a trailing optional positional from a token after any
number of flags, so trusting it would let the accepted grammar drift
from the documented one. docmap reads the tokens ahead of the first
flag instead, and takes PATH from there.

Walking the current directory costs one explicit token, `docmap print
.`. That echoes the guardrail posture above: the harmless invocation is
the default, and the filesystem tree is asked for by name.

A bare word is a question and gets documentation. One command in one
file means one document, so bare `docmap` and bare `docmap print` both
print the module docstring, which is the usage banner. It already names
the command, the argument, and every flag, and a second copy beside it
would drift. A second command is what would split them. The test is
`len(sys.argv) == 2`, never "PATH is missing": once any other token is
present the user asked for something specific, and answering with help
would hide the mistake.

`docmap --version` prints the program name and the installed version
on one line, then exits 0. It is documentation, so it shares its exit
code with the banner. The number stays a literal in `pyproject.toml`
and reaches the CLI through the installed metadata, never as a second
copy in the source. An editable install records it once, so a
developer's tree can lag behind an edit; an end user's cannot. The
lookup is guarded, because the parser is built on every invocation
past a bare word. An unguarded `PackageNotFoundError` would take down
`print` too, not just this flag. Only a tree that has never been built
reaches that branch, and it answers `unknown (not installed)`.

The flag sits on the top-level parser alone, so `docmap print
--version` is an unknown flag and exits 2. A version is a fact about
the tool, not an option of a command, and keeping it off the
subparser is what says so.

`docmap` takes no piped input: its unit of work is a directory, not a
stream. That is documented, not enforced. `isatty()` answers "is a
human here", which is right for choosing how to present an answer and
wrong for deciding what the answer is. `/dev/null` arrives from cron,
from a subprocess, and from a test runner, and reads as a pipe under
that test, so one command line would print help from a shell and fail
under nohup. Bare `docmap` prints the banner and exits 0, whatever
stdin is.

Exit codes:

- `0`: success, and documentation. A map was emitted, a bare word
  printed the banner, or `--version` printed the number
- `1`: any error `docmap` raises itself (a usage slip, a root that is
  not a directory, or either guardrail refusing the walk)
- `2`: argparse's own errors (an unknown command, an unknown flag, or
  a bad value), left to argparse's convention

All self-raised errors go to stderr as `docmap: <message>`. Usage
errors additionally print the usage line; the sniff refusal prints the
exact `--force` re-run hint instead, since the fix there is a flag,
not a different grammar.

## Open Questions

- Module-level constants and assignments are not captured; undecided
  whether they belong on the map. Nothing forces the issue yet.

## Known Bugs

Confirmed defects, recorded here until fixed. This file is the bug
tracker, since a solo project doesn't need GitHub Issues.

None currently open.

## Use of AI

Both the use of AI and its disclosure are deliberate. Code and
documentation in this project are written in collaboration with
Artificial Intelligence (AI). The division of labour: the AI explores,
challenges assumptions and edge cases, and drafts; the human
initiates, drafts the designs, explores alongside the AI, reviews
every change, and decides what gets committed.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
