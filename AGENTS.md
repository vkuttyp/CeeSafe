<!--NOVA START-->

# Using Nova

This package is written in Nova, a memory-safe systems programming language with C#/TypeScript-style syntax that
`novac` compiles ahead of time to C. Ownership and borrowing are checked at compile time; there is no garbage
collector. Nova is new: code that looks right from C#, TypeScript or Rust often is not Nova. Check every edit with the
compiler, and read the guide for agents: https://vkuttyp.github.io/Nova/guide/for-agents (the whole guide and
specification for a model's context: https://vkuttyp.github.io/Nova/llms-full.txt).

## The package

- `nova.toml` names the package, its kind (`executable` or `library`) and its dependencies; `nova.lock` pins them.
- The sources are the `.nova` files under `src/`. A program starts at `fn main()`.
- `novac build` writes to `out/`, which is not committed.

## Commands

Run them in the package's directory; without file arguments they use the package.

| Command | What it does |
|---|---|
| `novac check` | parse, type-check and borrow-check; the fastest way to find errors |
| `novac fix` | apply the fixes the compiler is sure of, then check again |
| `novac explain N0249` | what a diagnostic code means |
| `novac run --interp` | run the program in the interpreter |
| `novac build` | compile through C to `out/<name>` |
| `novac fmt` | format in the one canonical style; `novac fmt --check` lists files that would change |
| `novac fetch` | resolve the dependencies and write `nova.lock` |

Add `--diagnostics-format=json` to `check`, `build`, `run` or `fix` for one JSON document with every diagnostic, its
position and its fixes.

## The MCP server

If you have the `nova` MCP server (`novac mcp`), use its tools: `nova_check` after every edit, `nova_fix` for the
fixes it offers, `nova_explain` for a code, `nova_spec_search` and `nova_spec_section` for the rules, `nova_run` to
run code in a sandbox. The specification is embedded in `novac`, so its answers match the compiler.

## Before you finish

- [ ] `novac check` reports no errors (run `novac fix` first).
- [ ] `novac fmt --check` lists no file.
- [ ] The program does what was asked: `novac run --interp`, or `novac build` and run it.

## Common mistakes

- There is no `~`: complement with `x ^ 0xFFFFFFFF`. There are no type aliases, tuples or `==` on arrays.
- Indexes are `usize`; `0..4` is a range of `i32`. Loop with `for (i in 0..values.length)`.
- `if` and `match` expressions take expressions, not blocks: `let s = if (x < 0) -1 else 1;`.
- A variable that changes is `var`; a `let` cannot be assigned. A `borrow mut` argument is written `mut x`.
- `as` converts only without loss; `truncate<u8>(x)` wraps.
- Bind a constant or a temporary to a local before slicing it or asking its `.length`.
- Pass a function or closure as a parameter and call the parameter; a field holding one cannot be called.
- A `StringView` inside an enum or struct needs a region parameter; for fixed messages, use an enum of reasons.
- A method cannot have the name of a field.

<!--NOVA END-->

# CeeSafe project rules

CeeSafe is the port of Nova's C# compiler (`novac`, `~/Nova`) to Nova itself, under the new name CeeSafe. The section
above, between the `NOVA` markers, is written by `novac agents` and is refreshed by it: put project rules here, below
the markers, and never edit between them.

## Governing documents (in order of authority)

1. `ROADMAP.md`: scope, phases P0–P9, the N track (upstream Nova M15), gates and the execution record.
2. `docs/decisions/*.md`: CeeSafe's accepted decisions (0001: identity and bootstrap; 0002: the rename cut-over).
3. Nova's specifications in `~/Nova/docs/` (type system, ownership, C backend) and its ADRs: the port preserves their
   semantics. Nova's `AGENTS.md` rules (spec before code, safety first, determinism, target layout from `TargetInfo`
   only) apply here too.
4. `bootstrap/reference.md`: the pinned stage-0 compiler and the Nova reference commit.

## Bootstrap rules

- Since P6R (Decision 0002) CeeSafe's sources are `.cee` files and its manifest is `ceesafe.toml`; ceesafec builds
  them (`out/ceesafec check`, `out/ceesafec build -o out/ceesafec`). novac cannot read these names.
- Get a ceesafec from a fresh checkout with `tools/bootstrap.sh`: the pinned novac named in `bootstrap/reference.md`
  (today `~/.nova/0.6.0/bin/novac`) builds the last legacy-named commit, whose ceesafec builds the tree. Keep a known
  good `out/ceesafec` before changing the compiler, so a broken build can be rebuilt by the previous one.
  `~/.nova/bin/novac` is 0.3.1, which CosmoOS's `make nova` still pins: leave it there. The `novac` on `PATH` may be a
  development wrapper around `~/Nova`'s working tree and is not reproducible.
- Formatting is still novac's until ceesafec has `fmt` (P8): `~/.nova/0.6.0/bin/novac fmt $(git ls-files 'src/*.cee')`
  (`novac fmt` on a directory looks only for `.nova` files).
- Legacy mode: ceesafec still reads `nova.toml` packages and `.nova` files (CosmoOS has not migrated), and Nova's
  corpus and `tests/` stay `.nova`, compared with novac. Diagnostic codes keep the letter N.
- A missing language or library feature is an upstream Nova task (ROADMAP's N track: spec and ADR in `~/Nova`, then a
  novac release and a re-pin). Pure library code (tables, interner, bignum, JSON) is written here in Nova. Never
  work around a gap with `unsafe`, C, or a weaker check where a safe design exists.
- Small C adapters for host services are allowed only behind a documented contract (ownership, lengths, encoding,
  errors); compiler algorithms stay in Nova.

## Tools

```sh
python3 tools/run_corpus.py --compiler ~/.nova/0.6.0/bin/novac                 # Nova's corpus against a compiler
python3 tools/run_corpus.py --compiler out/ceesafec --reference ~/.nova/0.6.0/bin/novac --family parse-pass
python3 tools/run_corpus.py --compiler ~/.nova/0.6.0/bin/novac --corpus probes --family run-pass --family check-fail \
    --family parse-fail                                                  # the P1 probes
W=""; for f in src/support/*.cee; do W="$W --with $f"; done                # zsh: then ${=W}
python3 tools/run_corpus.py --compiler ~/.nova/0.6.0/bin/novac --corpus tests/support --family run-pass $W --check-leaks
python3 tools/fault_sweep.py --compiler ~/.nova/0.6.0/bin/novac tests/support/fault/alloc-sweep.nova src/support/*.cee
python3 tools/oracles/support_models.py                                  # oracle summaries for tests/support
python3 tools/inventory.py                                               # regenerate docs/reference-inventory.md
python3 tools/gen_catalog.py --nova <Nova at the pinned tag>            # regenerate src/diagnostics/catalog.cee
python3 tools/compare_tokens.py --ceesafec out/ceesafec --oracle <token-dump> --root <Nova> lib tests/corpus
                                                                        # the lexer against the reference (docs/p2-frontend.md §3)
python3 tools/compare_parse.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root <Nova> lib tests/corpus
                                                                        # trees and diagnostics against novac (§6)
python3 tools/parser_fuzz.py <dir> 3000 <seed> <files>                  # broken variants for compare_parse.py
python3 tools/contract_tests.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root <Nova at the tag>
                                                                        # every contract test (P2–P6R), one command
python3 tools/fixed_point.py --stage0 out/ceesafec --work <dir> --manifest <file>
                                                                        # the fixed point (docs/p6-fixed-point.md)
```

Generated files say so in their first line (`tools/oracles/gen_*.py` writes them); edit the generator, never the
output. Expected values in `tests/support` come from oracles outside the code under test (Python, .NET, novac).
Use `--check-leaks` for anything new: novac 0.3.1 skipped drops, and the probes keep a regression for it.

`run_corpus.py` checks the corpus's own expectations (annotations, snapshots, expected output); `--reference`
also requires identical observable outcomes. Its normalisations are listed in the script: never widen one to make a
comparison pass. `docs/parity.md` is the ledger; `docs/reference-inventory.md` is generated, never edited by hand.

## Evidence discipline

- Cite sources: `file:line` for code (`~/Nova/src/...` for the reference), sections for docs.
- Keep tests that were run (date, command, result) apart from tests that are only proposed. Record work in ROADMAP §10.
- Never regenerate expected results from CeeSafe to make a comparison pass.

## Layout

```text
ROADMAP.md  AGENTS.md  nova.toml       (ceesafe.toml after P6R)
src/                                    the compiler, in Nova
docs/decisions/                         CeeSafe decisions
bootstrap/                              stage-0 pin and reference manifest
tools/                                  run_corpus.py (corpus runner), inventory.py (reference inventory)
probes/                                 P1 capability probes in corpus format, and regression probes for fixed novac bugs
src/support/ src/host/                  the support library (P1) and host services
src/syntax/ src/diagnostics/            the frontend (P2): tokens, lexer, AST, parser, dumps; diagnostics and their JSON
tests/syntax/                           lexer edge cases (tools/lexer_fuzz.py --cases), and known differences
tests/support/                          support-library tests (run-pass, fault/)
tools/oracles/                          independent oracles and generators for tests
out/                                    build output, never committed
```

## Git

Commit only when asked, in small focused commits; never commit `out/`.
