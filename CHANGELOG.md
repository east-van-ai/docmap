# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.2.0] - 2026-08-18

### Changed

- **Breaking:** the walk target is now the named option `--src-root PATH`
  instead of the bare `ROOT` positional, and flag order is free. Walking
  the current directory is `docmap --src-root .`
- Dev dependencies live in a `[dependency-groups]` block in
  `pyproject.toml`, with `black` and `ruff` pinned. Install with
  `pip install -e . --group dev`
- Table-of-contents blocks dropped from `README.md`, `DESIGN.md`, and
  `CLAUDE.md`
- Install and homepage URLs point at `east-van-ai/docmap`. The install
  line no longer tracks a `stable` branch

### Removed

- `RELEASING.md`
- `requirements.txt` and `requirements-dev.txt`

## [0.1.0] - 2026-07-18

### Added

- Abstract Syntax Tree(AST)-based extraction of top-level and class-level
  functions/methods, with first-sentence docstrings and line numbers
- Hand-rolled minimal YAML writer (no external dependencies)
- Default noise filtering: VCS/cache/build dirs, hidden dirs, test files
- OS-root sniff test with `--force` override
- Mid-walk file count ceiling (5000) as a second safety net
- `--include-private`, `--include-tests`, `--out` flags
- pytest suite covering docstring extraction, arg formatting, YAML
  escaping, nested class/method qualnames, filtering, safety checks, and
  CLI end-to-end behavior
- Packaged for `pipx install`
- Nested classes have dotted qualnames (e.g. Foo.Inner.baz)
- `DESIGN.md` (architecture, CLI grammar, guardrail rationale) and
  `RELEASING.md` (stable-branch release model, folding in the former
  `PACKAGING.md`)

### Changed

- CLI grammar aligned with `mdmap`: bare `docmap` on a TTY prints the
  usage banner and exits 0 (walking the current directory is an explicit
  `docmap .`); bare `docmap` with piped stdin is a usage error (docmap
  takes no piped input); flags-first/root-last argument order is
  enforced; errors go to stderr as `docmap: ...` plus a usage line
- Exit codes normalized to `0` success, `1` for every docmap-raised
  error (usage, bad root, both guardrail refusals -- previously `3` for
  the root sniff and `2` for the file ceiling), `2` reserved for
  argparse's own errors
- Python floor widened from >=3.14 to >=3.9; CI now runs a 3.9-3.14
  matrix with `ruff check` and `black --check` on every push
- Tests split by layer into `test_extraction.py`, `test_walking.py`,
  and `test_cli_integration.py`, with a subprocess `run_cli` fixture
  invoking `python -m docmap.cli`
- README restructured to the mdmap shape (Why / Example output /
  Install / Usage / Notes / Use of AI); install now points at the
  `stable` branch

### Removed

- `PACKAGING.md` (content lives in `RELEASING.md` now)
- `requirements-pinned.txt`
