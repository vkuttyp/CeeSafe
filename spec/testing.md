# Testing

Status: describes CeeSafe's tests at the fork (CeeSafe's Decision 0006). Tests that were run are recorded, with dates
and results, in the repository's `ROADMAP.md` §10 and the plans under `docs/`; they are never mixed with proposals.
Nova's own test history up to the fork is in [Nova's testing.md](https://github.com/vkuttyp/Nova/blob/v0.6.0/docs/testing.md).

Sanitizer results are supporting evidence, never proof of the language's safety.

## 1. Test kinds

| Kind | Where | Oracle |
|---|---|---|
| Corpus (§2) | `tests/reference/tests/corpus/*`, `tools/run_corpus.py` | the files' own annotations and snapshots |
| Regression against the fork (§3) | `tools/compare_*.py`, `tools/run_corpus.py --reference` | novac 0.6.0's output, with ceesafec's names mapped back (`tools/names.py`) |
| Fixed point | `tools/fixed_point.py`, `bootstrap/fixed-point/` | ceesafec built by itself emits byte-identical C, generation after generation |
| Mutation suite (Nova M2) | `tools/mutation_suite.py` | mutants of seed programs; the expected (code, line) diagnostics come from an independent oracle, not from the checker |
| Fault-injection sweep (Nova M3) | `tools/fault_injection.py` | every run-pass program that allocates, built with ASan+UBSan, run once per allocation attempt *k* with attempt *k* failing; each run returns from `main` with `live=0` or panics with "unwrapped an Err value", with no sanitizer report |
| Collection properties (Nova M6) | `tools/collection_properties.py` | a model of each built-in collection predicts the exact output of random operation programs (values, lengths, the growth rule of `type-system.md` §23.1, stale handles, drop order), also under the fault sweep |
| Freestanding | `tools/freestanding_check.py` | the freestanding programs build with `-ffreestanding -nostdinc` for `x86_64-` and `aarch64-unknown-none-elf` and run against their C harnesses |
| Debugging | `tools/debugger_check.py` | a `-g` build under lldb or gdb with `editors/debug`'s commands (`tooling.md` §3) |
| Linking with Nova | `tools/link_collision.py` | a novac-built and a ceesafec-built library link into one program; two novac-built ones do not |
| Same C on another host | `tools/host_c_check.py` | ceesafec built on Windows (MSVC, clang) emits the same C as on macOS and Linux |
| Specification (§4) | `tools/spec_check.py`, `tools/guide_check.py` | every diagnostic code is explained; the guide's examples do what the pages say; links resolve |

`tools/contract_tests.py` runs all of these but the fixed point and the host check, against one ceesafec.

## 2. Corpus format

Runner: `tools/run_corpus.py --compiler out/ceesafec --corpus tests/reference/tests/corpus`.

- `parse-pass/*.cee`: must parse with **no** diagnostics. The AST dump (`ceesafec parse --dump-ast`) must equal the
  sibling `.ast` snapshot. **Every new or changed snapshot is reviewed by hand before it is committed.** A snapshot is
  an expected value, not a recording.
- `parse-fail/*.cee`: annotate each expected diagnostic on the line where it is reported, as `// error[N0100]`, or
  `// error[N0100]@14` to also pin the column. A missing **or extra** diagnostic fails the test, so it also checks
  error recovery.
- `check-pass/*.cee`: must type-check with no diagnostics. The HIR dump (`ceesafec check --dump-hir`) must equal the
  sibling `.hir` snapshot.
- `check-fail/*.cee`: must **parse** cleanly and produce exactly the annotated semantic diagnostics.
- A file with a line `// profile: freestanding` is checked in the freestanding profile (`profiles.md` §4), and one with
  `// option: no-float` as if built with `--no-float` (`type-system.md` §35.9).
- `run-pass/*.cee` and `run-fail/*.cee` are compiled to C, built with strict warnings and `-Werror`, and run.
  Directives:
  - `// expect-stdout: text`: one per output line, in order; `// expect-stdout:` alone is an empty line.
  - `// expect-exit: N`: the exit status (default 0).
  - `// expect-panic: reason`: placed on the line where the panic must be reported. The test requires exit status
    134 (SIGABRT) and `ceesafe panic: <reason> at <file>:<line>:` on standard error.
- `ffi/` programs are linked with their C harness (`NAME.c`, and `NAME.types.h` for imported C types,
  `type-system.md` §31); `freestanding/` programs with their environment.
- `emit-c/*.cee` have reviewed snapshots of the generated `main.c`; `placement/`, `bounds-checks/`,
  `overflow-checks/` and `closure-calls/` have snapshots of the `--explain-…` reports (`optimisations.md`).
- The C configurations: the contract suite builds the run families under the host's `cc` with `-Werror`, and under
  clang `-O1` with ASan+UBSan, `-fno-sanitize-recover=all` and the runtime's allocation report (`--check-leaks`: a
  program that exits normally with live allocations fails). Every configuration must meet the expectations, so the
  run corpus is also a differential test.

At the fork the corpus is Nova's at `v0.6.0` with `.cee` names (`tools/fork_corpus.py`), and its snapshots are still
Nova's: `run_corpus.py` compares ceesafec's output with them after mapping CeeSafe's names back (§3). A CeeSafe-only
change to the language adds corpus files with CeeSafe's names and snapshots written by ceesafec.

## 3. Regression against the fork

novac 0.6.0's output, which equalled ceesafec's at the fork, is the frozen baseline (the repository's
`docs/fork-point.md`). The comparison tools run novac in a Nova checkout at `v0.6.0` and ceesafec on CeeSafe's copy of
the same files, and compare novac's output with ceesafec's mapped back by `tools/names.py`: diagnostics and JSON,
the AST, HIR and NIR dumps, the C in eight forms and the reports, CeeSafe's own C, packages, the command line, `fmt`,
`doc`, `run --interp`, and the `lsp` and `mcp` servers. A mapping could hide a name that was not renamed, so the C
comparisons also fail on any Nova C name left in ceesafec's output.

A deliberate difference from Nova is a change to this specification first, and then a recorded exception in the
comparisons (as `names.FORK_DIVERGENCES` is).

## 4. The specification's own checks

- `tools/spec_check.py`: every diagnostic code `ceesafec` reports has a row that `ceesafec explain` finds; every
  relative link in `spec/` and `guide/` resolves; `spec/api/core.md` is what `ceesafec doc` writes for `lib/core`; no
  Nova name is left outside the inherited ADRs and the places that name Nova on purpose.
- `tools/guide_check.py`: every `ceesafe` code block of `guide/` is compiled as a file named `main.cee`:
  - a block must type-check; with a `main`, it is also run in the interpreter, and a `text` block right after it must be
    exactly its output;
  - an HTML comment directly before the block changes that:
    - `<!-- ceesafe: fail N0241 -->`: the block must fail with exactly these codes, and a `text` block after it must be
      exactly the compiler's messages;
    - `<!-- ceesafe: freestanding -->`: checked with the freestanding profile, not run;
    - `<!-- ceesafe: check -->`: type-checked, not run (it calls C);
    - `<!-- ceesafe: panics -->`, `<!-- ceesafe: exits 1 -->`: the run's exit status;
    - `<!-- ceesafe: skip -->`: not checked, for a block that cannot stand alone (a second package's file, a fragment).
      Use it sparingly, and check the example some other way.
- The algorithms that find and rank sections for `explain` and the MCP server are compared with novac's on Nova's
  documents, through a ceesafec built with them (`tools/reference_docs.py`).

## 5. Not yet ported

Nova's random program generator (`tests/Nova.Fuzz`, Nova M7d and K7) and its 24-hour differential campaign are
ROADMAP P9 items; until then the fuzz evidence is Nova's, for the language as it was at the fork.
