# docmap CLI

## Grammar

`docmap print PATH [--include-private] [--include-tests] [--force]`.
The command word sits at `argv[1]` and the walk target at `argv[2]`.
Flags follow PATH, and their order among themselves is free.

| Command line | Result | Exit |
| --- | --- | --- |
| `docmap` | banner | 0 |
| `docmap print` | banner | 0 |
| `docmap print PATH` | map on stdout | 0 |
| `docmap print` and flags, no PATH | usage error | 1 |
| `docmap print --force PATH` | usage error, PATH comes first | 1 |
| `docmap print A B` | usage error, nothing after PATH | 1 |
| `docmap print PATH`, PATH not a directory | error | 1 |
| `docmap print PATH --nope` | argparse rejects the flag | 2 |
| `docmap --src-root .` | argparse rejects the command | 2 |

The map goes to stdout. docmap writes no files, so a shell redirect is
what puts a map on disk.

## Flags

- `--include-private` keeps single-underscore names in the map. Dunders
  are skipped either way.
- `--include-tests` keeps test files and test directories, which the
  walk drops by default.
- `--force` walks a root that failed the safety sniff. It does not lift
  the 5000-file ceiling, which no flag lifts.

## Bare words

Bare `docmap` and bare `docmap print` both print the usage banner and
exit 0, whatever stdin is. The banner is the module docstring, and it
names the command, the argument, and every flag.

The test is the token by itself. Once any other token is present the
command line is read as a specific request, so `docmap print --force`
with no PATH is a usage error rather than a page of help.

`docmap` reads no piped input: its unit of work is a directory, not a
stream. Nothing enforces that, and a pipe into `docmap` is neither read
nor refused.

## Exit codes

- `0`: success, and documentation. A map was emitted, or a bare word
  printed the banner
- `1`: any error `docmap` raises itself (a usage slip, a root that is
  not a directory, or either guardrail refusing the walk)
- `2`: argparse's own errors (an unknown command, an unknown flag, or
  a bad value), left to argparse's convention

All self-raised errors go to stderr as `docmap: <message>`. A usage
error prints the usage line of the command that failed after it. The
safety sniff prints the exact `--force` re-run hint instead.

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
