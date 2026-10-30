# CeeSafe roadmap: port the Nova compiler to Nova, as CeeSafe

Date: 2026-10-30 (revises the 2026-10-29 draft). Status: **P0 in progress**. The package scaffold, the stage-0 pin and
decision 0001 exist. No compiler code has been ported.
Repository: `~/dev/CeeSafe`. Reference: `vkuttyp/Nova` (C#/.NET 10), pinned in `bootstrap/reference.md`.

**Identity** (decision 0001):
- The public language is **CeeSafe**. The compiler is `ceesafec`.
- Sources use `.cee`. Packages use `ceesafe.toml` and `ceesafe.lock`, and `$CEESAFE_HOME`.
- Nova remains a living language. It is CeeSafe's stage-0 compiler and its behaviour oracle.
- **Until `ceesafec` compiles itself, CeeSafe's own sources are `.nova` files with a `nova.toml`**, because novac reads
  only those. P6R renames them in one commit.

**The work resolves Nova's OD-33.** That is "a Nova compiler written in Nova", recorded by Nova ADR 0023 as option C.
Nova ADR 0001 chose C# and expected self-hosting only "for a long time".

## 1. Scope and completion criteria

There are three deliverables:

1. **Compiler parity.** This covers:
   - lexing, parsing and package names;
   - types, generic checking and instantiation;
   - HIR and NIR;
   - ownership, borrowing, effects and destruction;
   - every optimisation;
   - portable C emission.
2. **Verified self-hosting.** novac builds `ceesafec` (generation 1). Generation 1 builds generation 2, and generation 2
   builds generation 3. Generations 2 and 3 must emit byte-identical C and pass the compiler tests.
3. **Product parity and handover.** The complete CLI, interpreter, package manager, formatter and doc generator, the
   LSP and MCP servers, fixes and JSON diagnostics, debugger scripts, runtime bundling and release/install all work
   without .NET.

Self-compilation alone does not complete the port. Accepting the compiler's own sources says nothing about whether the
borrow checker is correct. No reduced language subset will be presented as a replacement.

The C runtime (`runtime/`, 2,898 lines) and the Nova libraries (`lib/core`, `lib/std`, `lib/kernel`) are carried over
with their provenance and licence (GPLv2). The compiler's algorithms stay in Nova. Invoking the C# compiler to parse,
check, emit or run tooling does not count as a port. The C compiler, linker, debugger and git remain external tools,
used by the commands that need them.

## 2. Reference audit (2026-10-30)

The audit read Nova `main` at `07d561f` (0.4.0-dev, clean tree) and the released novac 0.3.1 (`v0.3.1` = `4481e12`).
Paths below are relative to `~/Nova`.

### 2.1 Size

Physical lines of `.cs`, excluding `bin/` and `obj/`. These measure scope, not effort.

| Component | Files | Lines | Notes |
|---|---:|---:|---|
| `src/Nova.Compiler` | 58 | 36,559 | |
| `src/Nova.Cli` | 1 | 1,211 | 18 commands |
| `tests/Nova.Compiler.Tests` | 41 | 6,673 | 39 test classes |
| `tests/Nova.Fuzz` | 3 | 1,919 | random program generator |
| `tests/corpus` | 573 files | — | 13 families |

Compiler size by directory:

| Directory | Lines | Notes |
|---|---:|---|
| `Semantics/` | 11,419 | `TypeChecker.cs` alone is 9,100 |
| `Backend.C/` | 4,975 | `CEmitter.cs` 3,840; `CStructurer.cs` 636 |
| `Analysis/` | 3,728 | Borrow, Move, InPlace, Drop, Effect, CheckElimination, Placement |
| `Syntax/` | 3,717 | `Parser.cs` 1,789 |
| `Interpreter/` | 3,640 | |
| `Nir/` | 2,361 | |
| `Packages/` | 1,874 | |
| `Tooling/` | 1,750 | LSP, MCP, SemanticIndex |
| `Formatting/` | 1,220 | |
| `Hir/` | 1,011 | |
| `Documentation/` | 417 | |
| `Diagnostics/` | 242 | |
| root | 205 | |

Corpus `.nova` counts:

| Family | Count |
|---|---:|
| run-pass | 153 |
| check-fail | 128 |
| parse-pass | 40 |
| run-fail | 40 |
| check-pass | 27 |
| parse-fail | 27 |
| emit-c | 24 |
| ffi | 6 |
| bounds-checks | 3 |
| placement | 3 |
| freestanding | 3 |
| overflow-checks | 2 |
| closure-calls | 1 |

### 2.2 Can Nova host a compiler today? Not yet

The 2026-10-29 draft assumed CeeSafe could be written "within the pinned stage-0 language". The audit shows the
language core is adequate, but its library and host support are not.

| Area | Present | Missing | Evidence |
|---|---|---|---|
| Core language | enums with payloads and `match`, recursive `Box`, generics with interface bounds, `dyn`, closures, `T?`/`Result` with `?`, statics, threads, multi-file packages | `From` conversion for `?`; `impl<T> I for G<T>` and `Self`; `i128` | `docs/type-system.md` §15, §17.4, §20–§21.1, §36–§39 |
| Collections | `Vector`, `String`, `SlotMap`/`Handle`, `StableVector`; `sortBy` | **hash map, set and ordered map**; slice search | §23–§24, §16.5; `lib/core/slices.nova` |
| Strings | `append`, `appendNumber`, boundary-checked slicing, `==` | hashing, ordering, clone, char/UTF-8 iteration, integer and float parsing, `find`/`startsWith`; growing only from a `StringView` | §22.2, §23.2 |
| Host services | read/write/remove files, stdin bytes, stdout/stderr, argv, `Process.run` (status only), TCP | environment, cwd, directories, stat, mkdir/rename, temp files, clock, **captured child output**, stdin to a child | §26; `runtime/hosted/nova_rt_io.c` |
| Borrowing | IDs and handles, field-precise and constant-index disjointness, `splitAtMut` | any non-constant index aliases every element, so table-heavy code must copy out or use handles | `docs/lifetimes.md` §4, §8 |
| FFI | `extern "C"`, `.c` files linked by `build`, `@repr(C)` structs | `run --interp` runs no C | §28; `docs/unsafe.md` |
| Scale | novac checks a 202k-line package in 13.1 s | the largest Nova program in the repository is ~360 lines; no parser has been written in Nova | ADR 0022; `lib/core/atomics.nova` |

This is the port's largest risk, and the reason for the **N track** (§4) before and alongside P1–P3.

### 2.3 C# surfaces that need a native design

| Finding | Evidence |
|---|---|
| The pipeline order is fixed | `src/Nova.Compiler/Compilation.cs:76-129`. The order: core libraries, parse, `PackageNames.Rewrite`, `TypeChecker`, `NirBuilder`, then per function `InPlaceChecker`, `MoveChecker`, `BorrowChecker`, then `DropElaborator`, then `EffectChecker` |
| Spans are UTF-16 code units over UTF-8 input | `Syntax/SourceText.cs:3`; `docs/grammar.md` §1.1 |
| Interned names get deterministic first-seen IDs | `Syntax/SymbolTable.cs:3` |
| Layout comes from the target, not the host | `Semantics/Types.cs:22` (`TargetInfo`); `docs/c-backend.md` |
| Exact integers through `BigInteger` | 6 files: `IntegerSemantics`, `FloatSemantics`, `Types`, `TypeChecker`, `CEmitter`, `CheckElimination` |
| Width-specific float evaluation and formatting | `Semantics/FloatSemantics.cs:16`; type-system §35 |
| Reflection walks the trees | `Tooling/SemanticIndex.cs:177-280`; `Semantics/TypeChecker.cs:3981`, `:6833` |
| JSON through `System.Text.Json` | `McpServer.cs`, `LanguageServer.cs`, `DiagnosticJson.cs` |
| Hash collections whose order may reach output | `TypeChecker.cs` (58 `Dictionary`, 40 `HashSet`), `CEmitter.cs` (12, 17), `CheckElimination.cs`, `BorrowChecker.cs`; explicit sorts at `Fixer.cs:35`, `CheckElimination.cs:156` |
| Embedded resources: libraries, runtime, docs, templates | `CoreLibrary.cs`, `Backend.C/CBackend.cs:54-63`, `Documentation/EmbeddedDocs.cs`, `Packages/AgentFiles.cs` |
| The CLI is broad | `src/Nova.Cli/Program.cs:225-335`. Commands: `parse check build run fmt doc new agents fetch publish index-check fix explain mcp lsp` |
| Tests cover mutations, allocation failures and several C configurations | `docs/testing.md` §3–§5; `MutationTests.cs`, `FaultInjectionTests.cs`, `MsvcTests.cs` |

### 2.4 Nova changes since the 2026-10-29 draft

The draft's baseline was `06fd7cd`. The current ADR range is **0001–0027**. Both of these are new:
- **0026**, inline atomics: the atomic types moved to `lib/core`, in every profile.
- **0027**: `here` in static initialisers, `Mutex.constant`, `layoutOf<T>()`, raw `read`/`write` for any `T`, and
  `ObjectCache<T>`.

novac 0.3.0 and 0.3.1 are released. M14 is still in progress: K2 (typed calls across units) and K6 are open.

## 3. Architecture and porting rules

### 3.1 Preserve semantics, change storage

- Follow the current grammar, ownership invariants and accepted ADRs. A needed language addition goes through Nova
  (the N track), never into compiler-only syntax or intrinsics.
- Replace C# class hierarchies with tagged enums and typed IDs into owned tables: AST, HIR, types, definitions,
  functions, blocks, locals. Parent and cross-reference edges are IDs. Lists are ranges into contiguous tables.
- Keep mutable borrows short: read IDs or `Copy` data, end the borrow, then mutate. The borrow checker's
  index-aliasing rule (§2.2) makes this mandatory. P1 must prove the pattern before bulk translation.
- The compilation owns its inputs. Tokens keep source IDs and spans, and decoded literals own their bytes. Server
  requests release everything from the previous compilation.
- Maps, sets, interners and worklists must iterate deterministically. Hash order never reaches output; output paths
  and declaration order are sorted or follow the specified order.
- Allocation failure ends compilation with a diagnostic and no partial output. Fault injection tests this.
- `unsafe` and raw pointers stay at documented FFI boundaries. There is no tracing GC and no implicit reference counting.

### 3.2 Text, numbers and the host boundary

- Keep source bytes plus a tested conversion to the reference's UTF-16 offsets and columns. Diagnostics, fixes, dumps
  and LSP all depend on it. Test BOMs, line endings, supplementary characters, invalid UTF-8 and EOF.
- Exact integers: a small signed-magnitude limb integer in Nova, sized to the audited `BigInteger` uses. Never use
  unchecked `i64` where the reference is exact.
- Floats: binary32/64 parsing, rounding, NaN, ±0, infinities and decimal formatting must match `FloatSemantics.cs` and
  `runtime/hosted/nova_rt_float.c`. Locale-dependent libc is not an oracle.
- Host services (files, paths, environment, processes, clocks, temp files, tool discovery) sit behind one small layer.
  Ideally it is N-track library API. A C adapter is allowed only with a written contract covering ownership, lengths,
  encoding, errors and cleanup. Processes take argument arrays and never shell strings.

### 3.3 Repository layout

```text
CeeSafe/
  ROADMAP.md AGENTS.md CLAUDE.md .mcp.json   (agent files from novac new --agent claude)
  nova.toml                                  -> ceesafe.toml at P6R
  src/                                        compiler, in Nova (one package; files share one scope)
    support/ syntax/ diagnostics/ semantics/ hir/ nir/ analysis/
    backend_c/ interpreter/ packages/ formatting/ documentation/ tooling/ host/  (planned)
  runtime/ lib/ resources/                    carried over at P5 with provenance
  bootstrap/reference.md                      stage-0 pin
  docs/decisions/                             CeeSafe decisions
  tests/ tools/ benchmarks/                   (planned)
  out/                                        ignored
```

The package compiles as one whole program, as novac does today; Nova has no separate compilation (ADR 0013 D4).
Subdirectories under `src/` are only for organisation, since every `.nova` file under `src/` shares one scope.

### 3.4 Rename contract

| Surface | Nova today | CeeSafe | When |
|---|---|---|---|
| Compiler | `novac` | `ceesafec` | skeleton now; parity P8 |
| Source extension | `.nova` (`Packages/Manifest.cs:271`, `Program.cs:697`) | `.cee` | P6R |
| Manifest and lock | `nova.toml`, `nova.lock` (`Manifest.cs:32`, `Workspace.cs:28`) | `ceesafe.toml`, `ceesafe.lock` | P6R; conversion in P8 |
| Home | `$NOVA_HOME`, `~/.nova` (`Workspace.cs:111`) | `$CEESAFE_HOME`, `~/.ceesafe` | P8 |
| Generated C | `nv_`, `nvMk_`, `NOVA_PROGRAM_*_H`, `nova_exports.h` | versioned prefix (open) | P7, after parity |
| Runtime | `nova_*` (~374), `nv*` (~424), `NOVA_*` (10), `runtime/include/nova/rt.h` | versioned prefix (open) | P7 |
| Diagnostics | 126 `N####` codes (`Diagnostics/Diagnostic.cs:14`), used by 159 corpus files | letter open, with a mapping | P6R |
| MCP/LSP | server `novac`, tools `nova_*` | `ceesafec`, `ceesafe_*` | P8 |
| Agent files | `<!--NOVA START/END-->`, `nova.mdc` | CeeSafe markers | P8 |
| Editor | `nova-language`, language id `nova` | CeeSafe extension | P8 |
| CosmoOS | `.nova`, pinned novac | `.cee`, pinned `ceesafec` | P9, reviewed PRs |

Nova's generated-C ABI is kept through the first fixed point. Renaming never changes ownership, lifetime, drop or
safety semantics, and it is never done by text substitution.

## 4. Phases and gates

Every phase delivers working code, positive and negative tests, an updated parity ledger and risk table, and a dated
entry in §10. An unchecked item is planned, not done.

### P0 — Foundation: pin, identity, inventory and runner

Dependencies: none. **In progress.**

- [x] Scaffold the package with the pinned novac (`novac new ceesafe --agent claude`), and write a `ceesafec` skeleton
  that handles `--version` and `--help` (2026-10-30).
- [x] Decision 0001 covers identity, the bootstrap route, the upstream N track and Nova continuing. Pin novac 0.3.1 and
  the Nova reference in `bootstrap/reference.md` (2026-10-30).
- [x] Inventory and ledger (2026-10-30). `tools/inventory.py` generates `docs/reference-inventory.md`
  deterministically. It lists 59 C# files, 15 commands, 26 options and 126 diagnostic codes (with their emitting files
  and corpus coverage), plus runtime, library and resource files and the 39 test classes, each with a phase.
  `docs/parity.md` is the hand-kept ledger: evidence per phase, the corpus baseline and known gaps.
- [x] Compare 0.3.1 with `07d561f` (2026-10-30). The only source difference in `src/`, `lib/` and `runtime/` is the
  version string. Across all 457 corpus files the runner found no observable difference (`docs/parity.md` §2).
- [x] Write the black-box runner (2026-10-30). `tools/run_corpus.py` takes any compiler path and covers all 13 corpus
  families. It checks annotations, snapshots, expected output and panics, and in `--reference` mode compares status,
  stdout, stderr and emitted files. It applies two named normalisations: the generated-by banner and the program name.
  It was tested against a deliberately wrong compiler.
- [ ] Close the runner's gaps (`docs/parity.md` §3):
  - a C configuration matrix (clang -O0/-O2, the overflow fallback, ASan+UBSan, `--split`, TSan, GCC);
  - freestanding symbol checks;
  - CLI fixtures for the 20 codes the corpus does not annotate.

  Most are needed by P5. The N0310–N0315 package fixtures are needed by P3.
- [x] Reference dumps (2026-10-30). The corpus's AST (40) and HIR (27) snapshots are the reference, and the runner
  reproduces them with 0.3.1. Exporting token and NIR dumps is deferred to P2 and P4, which decide how to compare them.
- [x] Run the reference suite (2026-10-30). `dotnet test Nova.slnx` at `07d561f` on macOS arm64 passed 3,589 of 3,589
  tests, with 0 skipped, in 12 min 24 s. No real GCC was available (`gcc` is Apple clang), and no MSVC (that needs the
  Windows VM). Whether TSan ran is not shown at default verbosity. A configuration Nova's suite cannot find counts as
  missing, not as passed.
- [ ] Gate check from a second checkout or host (the Ryzen box): reconstruct the pin, run the runner, get identical
  results.

Gate: another checkout reconstructs the pin and runs a representative fixture set with identical results, and the
ledger has no unmapped items (inventory: 0 unmapped, 2026-10-30).

### N — Upstream Nova: self-hosting prerequisites (proposed Nova milestone M15)

Dependencies: P1's probes decide the final list and its order. Each item is a Nova change approved by the owner and
made under Nova's rules: spec and ADR first, then tests, docs, `roadmap.md` and `risks.md`. It ships in a novac
release, and CeeSafe re-pins (`bootstrap/reference.md`). Candidates from §2.2, roughly in the order the port needs them:

- [ ] N1. Strings:
  - `clone` (copying a `String`);
  - ordering comparison;
  - hashing;
  - `find`, `startsWith`, `endsWith`;
  - appending a byte or a Unicode scalar;
  - UTF-8 char iteration and decoding;
  - integer parsing, then float parsing (must agree with `FloatSemantics`).
- [ ] N2. Collections: `HashMap<K, V>` and `HashSet<T>` with deterministic iteration (insertion order, or a specified
  order) in `lib/core` or `lib/std`; binary search on slices.
- [ ] N3. Language ergonomics: generic interface implementations (`impl<T> I for G<T>`) and `Self` (§21.1 lists them as
  future work); `From` conversion for `?` (§17.4).
- [ ] N4. Host services in `lib/std`:
  - environment variables;
  - the working directory;
  - directory listing, `mkdir`, `rename`, stat and exists;
  - temporary files;
  - a monotonic clock;
  - `Process` with captured stdout/stderr and stdin input;
  - buffered stdin by line or by length (needed for LSP and MCP framing).
- [ ] N5. Only if P1 proves it necessary: borrow precision for table-heavy code, such as disjoint borrows of two
  elements by non-constant index, checked at run time like `splitAtMut`. This is a safety-relevant change and needs
  its own ADR and mutation tests.
- [ ] N6. A first draft of `~/Nova/docs/milestone-15.md`, citing OD-33. This is the **next Nova-side task**, after P1's
  probes.

Gate per item: the novac release passes Nova's full suite, and CeeSafe's affected probes pass after the re-pin.

### P1 — Probes and the support library

Dependencies: P0. Runs alongside the N track.

- [ ] Capability probes compiled with the pinned novac:
  - recursive nodes through IDs;
  - vectors of owning enums;
  - lookup in one table then mutation of another;
  - a generic map key;
  - worklists and bitsets;
  - error propagation;
  - deterministic drops.

  Every probe that fails becomes an N-track item or a reduced bug report against novac.
- [ ] Probe host services: reading a source file, stdout and stderr, spawning `cc` with arguments, exit status. Record
  the gaps as N4 entries.
- [ ] `src/support/`:
  - typed ID tables;
  - an interner with first-seen IDs (`SymbolTable.cs:3`);
  - bitsets and worklists;
  - an exact integer;
  - UTF-8↔UTF-16 offsets and line index;
  - a JSON reader and writer.

  Each one is tested against an independent model.
- [ ] Specify the maximum supported sizes and IDs, and the allocation-failure behaviour.
- [ ] Grow the skeleton: input loading, structured errors, clean teardown.

Gate: probes and the support library pass under ASan and UBSan with the pinned novac. Every compiler bug found has a
reduced reproducer filed upstream. Missing features block; they are never worked around by weakening checks.

### P2 — Source frontend

Dependencies: P1's text and storage, N1.

- [ ] Port `SourceText`, the line index, interning, token kinds, the keyword table (`Keywords.Table`), literals,
  trivia and doc comments, and the lexer.
- [ ] Port the AST and the recursive-descent/Pratt parser: imports, attributes, generics and regions, patterns,
  closures, FFI, recovery, and splitting adjacent `>`.
- [ ] Add `parse` and `--dump-ast` with byte-identical dumps.

Gate: all 40 parse-pass and 27 parse-fail fixtures match, including AST snapshots and exact diagnostics. Every `.nova`
file in Nova's repository and CeeSafe's own sources parse. Fuzzed malformed input ends with a controlled error.

### P3 — Names, types, generics, HIR

Dependencies: P2, N2–N3, P1's exact integers.

- [ ] Port `PackageNames` (ADR 0013, N0310–N0315), scopes and visibility, builtins, `TargetInfo`, type interning,
  layouts and type properties.
- [ ] Port declarations, expressions, coercions and reborrows, patterns and usefulness (`PatternUsefulness.cs`),
  constant evaluation, HIR construction and `--dump-hir`.
- [ ] Port the generics: body checking, bounds, regions, instantiation, closure captures, `dyn`, owning closures,
  `Send`/`Share`, `@effectsOf`.
- [ ] Port the M14 and K semantics: statics (ADR 0024), `here`, `layoutOf`, raw `read`/`write` (ADR 0027), inline
  atomics (ADR 0026), `lib/kernel` contracts (ADR 0025), profiles, `unsafe`/FFI, and embedded C state.
- [ ] Split `TypeChecker.cs` (9,100 lines) into reviewable files using a source-to-port checklist that preserves
  diagnostic order.

Gate: check-pass and type-focused check-fail fixtures and HIR snapshots match exactly. Ownership negatives are tracked
as pending P4. This is not yet a full `check`.

### P4 — NIR and every safety pass

Dependencies: P3.

- [ ] Port NIR (`Nir.cs`, `NirBuilder.cs`, `NirPrinter.cs`) and `--dump-nir`.
- [ ] Port `MovePaths`, `MoveChecker`, `InPlaceChecker`, `BorrowChecker`, `FlowAnalysis`, `DropElaborator`, and then
  `EffectChecker`, in the pipeline order of §2.3.
- [ ] Cover:
  - field and index precision;
  - optional references;
  - captures and `dyn`;
  - threads and `Thread.both`;
  - kernel guards;
  - the sticky shared-deref soundness fix (N0248, Nova `3a99b4a`).
- [ ] Port the mutation and fault-injection expectations (`MutationTests.cs`, `FaultInjectionTests.cs`).

Gate: all 128 check-fail and 27 check-pass fixtures and the mutation expectations pass. NIR before and after drops
agrees with the reference. Every invariant in `docs/ownership.md` has mapped positive and negative evidence. `check`
now means the full pipeline.

### P5 — Flat C backend and the native build

Dependencies: P4, N4 (process capture).

- [ ] Port naming, type ordering and layout, declarations, aggregates, function/closure/vtable lowering, the runtime
  helpers, constants, drops, source maps, panic sites, FFI and imported structs, callbacks, exports and object mode.
- [ ] Bundle `runtime/` and `lib/` with deterministic tables. Construct `cc` and linker arguments, and publish output
  files.
- [ ] Add `build --emit c|exe|obj` with flat C. Flags not yet supported fail with an explicit error.

Gate: run-pass (153), run-fail (40), ffi and freestanding pass under clang -O0/-O2, the overflow fallback and
ASan+UBSan, with GCC where available. `emit-c` snapshots match, or each difference is reviewed. Objects for both
CosmoOS architectures pass.

### P6 — First verified fixed point

Dependencies: P5 and every feature CeeSafe uses.

- [ ] Gen 1 is built by the pinned novac from CeeSafe's `.nova` sources.
- [ ] Gen 1 builds gen 2, and gen 2 builds gen 3, with identical inputs, flags and toolchain.
- [ ] Gen 2 and gen 3 emitted C and resources are byte-equal. Both pass the compiler contract tests.
- [ ] Repeat from clean directories under different absolute paths. Check that no timestamp or path leaks into output.
- [ ] Gen 2 onward builds with no `dotnet` or novac on `PATH`, and the subprocess logs are audited.

Gate: a reproducible fixed point with archived manifests. This is a checkpoint, not release readiness.

### P6R — Rename cut-over

Dependencies: P6.

- [ ] `ceesafec` accepts `.cee`, `ceesafe.toml` and `$CEESAFE_HOME`. Decide, through a CeeSafe decision record,
  whether `.nova` and `nova.toml` are kept as an explicit legacy mode.
- [ ] Decide the diagnostic code letter and record the `N####` mapping. Corpus annotations get converted mechanically,
  with a reviewed diff.
- [ ] One commit renames CeeSafe's own sources and manifest. Rerun the P6 fixed point with `ceesafec` alone; novac is
  no longer needed for routine builds.

Gate: the fixed point holds on CeeSafe names, and the legacy mode (if kept) is tested.

### P7 — Optimisations and production C

Dependencies: P6R. Ownership and drop schedules do not change.

- [ ] Port placement and escape analysis, `Box.create` built in place, bounds and overflow check elimination, closure
  specialisation, and every `--explain-*` report.
- [ ] Port `CStructurer` (structured C), `--flat-c`, `--split` and `--program`, with deterministic unit names.
- [ ] Switch to the approved CeeSafe C prefix and ABI version, keeping a versioned legacy mode with link-collision tests.
- [ ] Run each switch on and off (`--no-placement`, `--no-bce`, `--no-oce`, `--no-closure-specialisation`) against the
  optimisation snapshots.
- [ ] Rerun the fixed point with production defaults and `--split`.

Gate: optimisation tests pass, the on and off runs agree, and production builds reach the fixed point. Any performance
claim needs a benchmark under `benchmarks/`, run on the Ryzen host.

### P8 — CLI, packages and tools

Dependencies: P7. Parser-only tools may start after P2, and semantic tools after P4.

- [ ] Packages:
  - manifest/TOML, path and git dependencies, the lock file and cache;
  - the registry index and version solving, `fetch`/`publish`/`index-check`;
  - `$CEESAFE_HOME`;
  - conversion from `nova.toml` and `nova.lock`.

  Local fixture repositories, no network.
- [ ] Interpreter: values, memory, numerics, builtins, deterministic threads (`Interpreter/Threads.cs`) and the sandbox.
- [ ] Formatter: trivia, recovery, `--check`/`--stdout`, idempotence. Format CeeSafe's own sources.
- [ ] Docs and resources: `doc`, `explain`, the embedded specs and guide, and `new`/`agents` with CeeSafe templates and
  markers.
- [ ] Fixes and JSON: the exact schema, `fix --dry-run`, and every corpus fix applied (`FixTests`).
- [ ] LSP: framing, UTF-16 edits, hover, definition, symbols, formatting, actions. Explicit walkers replace reflection.
- [ ] MCP: lifecycle, tools (`ceesafe_*`), resources and prompts, the sandbox.
- [ ] Host parity: Windows/MSVC, debugger scripts, the VS Code extension.
- [ ] The normal self-build uses package mode, and P6 is rerun through it.

Gate: every command and flag in the P0 ledger is implemented, or has an accepted decision. The contract suites pass.
No C# fallback.

### P9 — Harden, release, hand over

Dependencies: P8.

- [ ] Run the full acceptance matrix (§6) on both architectures, hosted and freestanding.
- [ ] Run a recorded 24-hour differential fuzz campaign against novac, with optimisations off and on, flat and
  structured C, closures, `dyn`, threads and numeric edges. Port the generator to Nova.
- [ ] Measure compiler throughput and peak memory against novac. Run it on the Ryzen host with `nice`.
- [ ] Release `ceesafec` for the six platforms, with checksums, licences, install scripts and macOS notarisation.
  Nothing is published until the owner asks.
- [ ] Ship a source-release C seed (in the spirit of ADR 0023 option A), verified to build with a C toolchain alone.
- [ ] Build and run `ceesafec` on CosmoOS userland, on both architectures, including self-compilation.
- [ ] Have the safety passes and `unsafe` adapters reviewed independently when a reviewer is available.
- [ ] Migrate CosmoOS (`.nova` to `.cee`, the pin to `ceesafec`) one component per reviewed, reversible PR.
- [ ] Document the point at which CeeSafe becomes the supported compiler, and the frozen C# reference.

Gate: parity, fixed point, CLI parity and release evidence are complete. Hosted CosmoOS support, an outside audit and
publication are reported separately.

## 5. Bootstrap protocol (planned interfaces; none exist yet)

```text
gen1: ~/.nova/bin/novac build                    (pinned stage-0, CeeSafe .nova sources)
gen2: out/gen1/ceesafec build -o out/gen2/ceesafec  --emit c kept in out/gen2/c/
gen3: out/gen2/ceesafec build -o out/gen3/ceesafec  --emit c kept in out/gen3/c/
tools/compare-stages out/gen2 out/gen3            (byte equality of C and resources)
tools/run-fixtures --compiler out/gen2/ceesafec --reference ~/.nova/bin/novac
```

The primary artefacts are the generated C and the bundled resources. Binary equality also needs controlled linker,
debug and signing metadata, and is reported separately. Generation equality shows a stable translation. It is not a
proof of correctness or of an uncompromised seed: keep the provenance, the independent safety tests and the C# oracle.

## 6. Acceptance matrix

| Area | Required evidence | First gate |
|---|---|---|
| Support library | independent models, collisions, determinism, OOM | P1 |
| Lexer and parser | AST snapshots, recovery, exact errors, UTF-16 positions | P2 |
| Types, generics, HIR | fixtures, constant edges, HIR snapshots, profiles | P3 |
| Ownership, borrows, effects | every negative, mutations, regions, captures, threads | P4 |
| Drops | post-drop NIR, early exits, partial moves, allocation failures | P4–P5 |
| Native semantics | stdout, stderr, status, panic sites against novac and the interpreter | P5 |
| C backend | snapshots, strict C11 warnings, determinism, FFI, source maps | P5–P7 |
| Self-hosting | gen2 equals gen3, no .NET on `PATH`, CeeSafe names | P6, P6R, P8 |
| Optimisations | each switch on and off, explanation reports, fuzz | P7 |
| Tools and protocols | CLI, packages, JSON and fixes, fmt, doc, LSP, MCP, editor | P8 |
| Portability | macOS, Linux, Windows; arm64 and x64; clang, GCC, MSVC | P9 |
| CosmoOS | C and object ABI checks, kernel integrations, both architectures, hosted compiler | P5–P9 |
| Robustness | sanitizers on the compiler and its programs, OOM sweeps, malformed input, fuzz campaign | ongoing |

Comparison policy:
- Byte equality where a contract promises it (dumps, JSON, protocol streams, gen2 against gen3), and novac-equal C
  where the backend is unchanged.
- Normalisation is narrow and versioned. It never hides a missing diagnostic, check, drop or panic location.
- A known reference bug gets a reproducer, a spec citation and a separate expected outcome. Expected results are never
  regenerated from CeeSafe to make a comparison pass.
- A skipped configuration is reported as skipped, not as a pass.

## 7. Risks

| Risk | Mitigation | Blocks |
|---|---|---|
| **Nova lacks library and host support for a compiler** (§2.2) | N track upstream; P1 probes decide the order | P1–P5 |
| N-track throughput: each item is spec, ADR, implementation and release in Nova | batch items per novac release; start with N1/N2, which the frontend needs first | P2–P3 |
| Index aliasing makes table-heavy code awkward | P1 ID/copy-out prototypes; N5 only with evidence | P2–P4 |
| No precedent for a large Nova program (~360 lines today) | P1 probes at scale; measure novac check and build time as `src/` grows | P1 on |
| Stage-0 drift as Nova evolves | pin a release; rebaseline only at gates (`bootstrap/reference.md`) | all |
| Stage-0 compiler bug exposed by CeeSafe | reduced reproducers, fixed upstream, re-pin | dependent phase |
| Numeric or text differences silently change acceptance | exact integers, UTF-16 tests, independent boundary oracles | P3 |
| Translation loses safety or drops | invariant-to-test map, mutations, NIR comparison, sanitizers | P4–P9 |
| Generated C differs without an explanation | deterministic tables and order, reviewed diffs, fixed point | P5–P9 |
| Incomplete rename breaks sources, packages or ABI | rename contract (§3.4), P6R legacy decision, reversible CosmoOS PRs | P6R–P9 |
| Host services drift into C | adapter contracts and a dependency inventory | P1, P8 |
| Servers leak compilations | ownership per request, repeated-edit tests | P8 |
| A hidden C# fallback | builds with `PATH` isolated, subprocess audit | P6, P8 |
| Scope grows past reviewable changes | port pass by pass; gate each phase | all |

A change to language semantics, memory architecture, public compatibility, supported targets or the bootstrap trust
policy needs a decision record: in Nova for the language, in CeeSafe for the compiler and its identity.

## 8. Order

```text
P0 foundation ──> P1 probes + support lib ──> P2 frontend ──> P3 types/HIR ──> P4 NIR + safety
                    │  ▲                         ▲               ▲
                    ▼  │                         │               │
                 N track (upstream Nova M15: N1 strings, N2 maps, N3 generics/From, N4 host, N5?)
P4 ──> P5 flat C ──> P6 fixed point ──> P6R rename ──> P7 optimisations ──> P8 tools ──> P9 release
```

## 9. Immediate work queue

1. P0: finish the gate by rerunning the runner from a second host (the Ryzen box, which also has GCC).
2. P0/P5: the runner's C configuration matrix and the package fixtures (`docs/parity.md` §3), alongside P1.
3. P1: the probes, starting with an ID-table AST built by a hand-written lexer over a real `.nova` file. Its results
   finalise the N list.
4. N6: draft Nova `docs/milestone-15.md` and the first ADR (strings and maps). This changes `~/Nova`, so it waits for the
   owner's go-ahead.
5. Only then start P2 with `SourceText`, the line index and the interner, followed by tokens and the lexer. Do not begin
   by translating `TypeChecker.cs`.

Progress is measured in completed contracts and gates. There is no calendar estimate before P1 produces evidence.

## 10. Execution record

| Date | Work actually performed | Result |
|---|---|---|
| 2026-10-29 | Read-only inspection of Nova and an empty CeeSafe; first roadmap draft; owner chose a full rename | planning only |
| 2026-10-30 | Cross-checked the draft against Nova `07d561f` and the `docs/` specs. Owner decisions recorded as decision 0001. Roadmap rewritten. | Draft found stale: baseline, ADRs to 0027, counts, pipeline citation, and Nova's missing self-hosting prerequisites (§2.2) |
| 2026-10-30 | `~/.nova/bin/novac new ceesafe --agent claude` (0.3.1) in a scratch directory, copied into `~/dev/CeeSafe`; `git init`; skeleton `src/main.nova`; `bootstrap/reference.md` | done |

**Tests run for the port** (2026-10-30, novac 0.3.1, Apple clang 21.0.0):
- `novac check` and `novac fmt --check`: clean.
- `novac build`, then `./out/ceesafe --version`: printed `ceesafec 0.0.0-dev`, exit 0.
- No arguments: exit 2. An unknown command: exit 2.
- `novac run --interp -- --version` printed the same version.

| 2026-10-30 | P0 inventory, ledger and runner: `tools/inventory.py`, `docs/reference-inventory.md`, `docs/parity.md`, `tools/run_corpus.py`; novac built from `07d561f` into a scratch directory for comparison | done; findings in `docs/parity.md` §3 |

**Tests run for P0** (2026-10-30, macOS arm64, Apple clang 21.0.0, Python 3.9.6):
- `tools/run_corpus.py --compiler ~/.nova/bin/novac` (0.3.1), all 457 files: 454 passed, 0 failed, 3 partial
  (freestanding: object builds only).
- The same run with novac `07d561f` against `--reference` 0.3.1: 0 differences.
- Against a deliberately wrong compiler: every affected file failed, as expected.
- `tools/inventory.py` run twice gave byte-identical output, with no host paths.
- Nova's `dotnet test Nova.slnx` at `07d561f`: 3,589 passed, 0 failed, 0 skipped.

Nothing in P1 or any later phase has been run.
