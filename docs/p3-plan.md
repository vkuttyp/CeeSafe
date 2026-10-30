# P3 plan — names, types, generics, HIR

Status: **S1 done** (2026-10-30). `ceesafec check` checks functions, statements, operators, casts, constants, char and float literals with exact parsing and folding, `--no-float`, function values, and the Console and Process builtins. All 11 S1 check-pass files are identical to novac 0.4.1. Of the 20 S1 check-fail files, 18 are identical, and `floats`/`no-float` differ only by a struct, an interface and float methods (S2, S4). Next: S2. This plan comes from a read of the reference at `v0.4.1`. File:line references below
are to `~/Nova/src/Nova.Compiler/`.

| File | Lines |
|---|---:|
| `Semantics/TypeChecker.cs` | 9,158 |
| `Semantics/Types.cs` | 1,479 |
| `Hir/Hir.cs` | 744 |
| `Hir/HirPrinter.cs` | 275 |
| `Semantics/PackageNames.cs` | 284 |
| `Semantics/FlowAnalysis.cs` | 144 |
| `Semantics/PatternUsefulness.cs` | 115 |
| Integer and float semantics | 297 |

## 1. What the reference does

**The pipeline** (`Compilation.cs:86-146`)
- The library units are parsed first, in this order:
  - lib/core;
  - lib/std when hosted;
  - lib/kernel when freestanding with `--kernel`.

  Each library is in ordinal resource-name order.
- Then the user units are parsed, with `PackageNames.Rewrite` applied to each.
- `TypeChecker.Check()` runs only if there are no errors so far.
- When it succeeds, `check` also runs NIR and the In-place, Move and Borrow checks, then N0222, drop elaboration and
  effects. Those later passes are P4.
- Diagnostics are printed in emission order, unsorted.
- `--dump-hir` prints whenever a HIR exists, errors or not.

**`Check()`** (`TypeChecker.cs:315-456`) runs these steps in order:
1. the built-in items (`DeclareAllocError`);
2. qualified names;
3. interfaces;
4. structs, enums and imported C structs;
5. type attributes;
6. the other items (functions, including each generic's generic version; consts; statics; extern blocks);
7. function attributes;
8. impls, then the pending bound checks and allocators;
9. a fixpoint that resolves struct and enum members;
10. layout uses, recursion, Copy and Drop, foreign interfaces, public signatures;
11. constants, which are evaluated lazily;
12. static initialisers;
13. the body pass, which loops over `_functions` while the list grows with instances and closures;
14. `CheckMain`, then `FoldStatics`;
15. `@effectsOf` and effects;
16. building the `HirProgram`.

Every pass runs over the library first, and library bodies are checked fully.

**The HIR dump** (`HirPrinter.cs`) prints:
- every constant, library ones included;
- every function whose source is not a library file, in `_functions` order: user generic versions, instances,
  methods (`Owner.name`) and closures;
- not the library's functions or the library's instances.

Quirks the port must reproduce:
- Every builtin call except `Console.write` and `Console.writeLine` prints as `Process.exit`, with no type suffix
  (`:247-252`).
- Floats print with .NET's `"R"` format.
- Integers print as `Int128`.
- Strings escape only `\`, `"` and newline.

**Numbering that is printed**
- Local `#N` is the local's index in its function: `this` first, then the parameters, then the order of the
  `AddLocal` calls.
- Closure IDs are `_functions.Count` at creation (`effects-of.hir`'s closures are 156 and up). They depend on every
  library function, and on the side effects of library body checks and of the inference's trial checks (`Quietly`,
  `:3274`, `:6363`, `:8087`). A program with closures can match only once the whole library is declared and checked
  with the reference's side effects.

**Order hazards**
- Closure captures are ordered by a reflection walk over HIR properties (`FieldPrecise`, `:3902-4003`). The port uses
  an explicit child order: the record parameters' order, to be confirmed by the corpus.
- `Identifiers` (`:6839`) walks the syntax tree by reflection but sorts its result by position.
- Several dictionaries are iterated in insertion order (`:1031`, `:4469`, `:6757`, `:8477`, `:8521`, `_dynTables`). The
  port uses `src/support/map.nova`, which keeps insertion order.

**Found while planning and porting (reference defects, not filed):**
- novac's generated C is not warning-clean for a string literal longer than 4,095 bytes: clang's `-pedantic` warns
  (`-Woverlength-strings`, the C11 §5.2.4.1 limit). CeeSafe's embedded library hit this; `tools/gen_library.py` now
  splits it into chunks of at most 4,000 bytes.
- `check --dump-hir` throws `NullReferenceException` in `HirPrinter.Stmt` on check-fail `enums`, `optionals` and
  `results`. The corpus never dumps HIR for check-fail files.
- The `Process.exit` naming above is wrong, but it is the reference's format, and the snapshots depend on it.

## 2. How each slice is checked

- `run_corpus.py --reference ~/.nova/0.4.1/bin/novac --family check-pass` compares the HIR snapshot, the diagnostics,
  and novac's exact output.
- `compare_parse.py --command check` compares `check --dump-hir --diagnostics-format=json` and text `check` over any
  file set. The sets are:
  - the 159 run-pass programs (8,692 HIR lines);
  - the other families that check cleanly (about 290 programs in all);
  - the check-fail files, apart from the three that crash the reference;
  - later, programs from Nova's random program generator (`tests/Nova.Fuzz`).
- Check-fail files whose expected codes come from the post-checker passes (N0212, N0222, N0240-N0253, N0272: 63
  files) need only no checker diagnostics and matching HIR until P4.

Until P4, `ceesafec check` runs the type checker only. A difference that comes from a P4 pass is reported as "P4",
not as a failure.

## 3. Slices

Each slice ends with a run recorded in §4. Library bodies are skipped until S5, which is safe for programs without
closures: library HIR is never printed, and function IDs print only for closures. Library declarations are needed from
S1, since lib/std's names and Console/Process need `_core`.

| Slice | Content | Must match (corpus files) |
|---|---|---|
| **S0** | `TargetInfo`, `NovaType` and `TypeTable` (names fixed at creation, interning, layouts), HIR records, `HirPrinter` with its quirks, `IntegerSemantics`, `FloatSemantics` (`"R"` format), `ceesafec check` and `--dump-hir` | unit tests against the reference's printer through a .NET oracle, as for tokens |
| **S1** | Functions, constants (`Fold`), statements, operators, Console and Process builtins, `FlowAnalysis`, `CheckMain`, `--no-float`, profiles | check-pass: main-void, gcd, operators, integer-types, literal-typing, constants, items-can-be-shadowed, control-flow, calls, builtins, definite-assignment. check-fail: the type-only files listed in the survey |
| **S2** | Structs, enums, `match` and `PatternUsefulness`, Result and Option, `?`/`!`, references and places, arrays and slices | check-pass: structs, enums, references, results, borrows-accepted, moves-accepted, scoped-payload-liveness, arrays, slice-borrows-accepted |
| **S3** | Built-in containers, allocators, regions, String/StringView, I/O | check-pass: boxes, arena-accepted, regions-accepted, and most of run-pass |
| **S4** | Generics, interfaces, impls, bounds, `dyn`, instantiation, `CheckInstance` | check-pass: generics, interfaces |
| **S5** | lib/core and lib/std: full declarations and bodies, with the reference's order of side effects | every earlier slice still matches, with no library diagnostic |
| **S6** | Closures, function values, threads, effects, `@effectsOf`, `FieldPrecise` | check-pass: effects-of (sensitive to IDs) |
| **S7** | C interop, statics, `unsafe`, kernel library, `layoutOf`, `here` | check-pass: kernel-library, and the FFI and freestanding families |
| **S8** | Packages: `PackageNames`, qualified names, imports | new fixtures (no corpus file covers several packages) |

The gate (ROADMAP P3): check-pass and the type-focused check-fail fixtures match exactly, and run-pass HIR matches.
Ownership negatives wait for P4.

## 4. Execution record

| Date | Slice | Run | Result |
|---|---|---|---|
| 2026-10-30 | — | novac 0.4.1 `check --dump-hir` over the corpus: which files check cleanly | about 290 clean programs, 12,987 HIR lines; check-fail 128 with errors, 3 clean, 3 crash the printer |
| 2026-10-30 | S0 | `src/types/types.nova` (TypeTable: kinds, names, interning, layouts, Copy/drop/scoped/Send/region/niche, lossless casts) against the reference's `TypeTable` through `tools/oracles/type-table`; `tests/types/run-pass/type-table.nova` (generated by `gen_type_cases.py`) with `--check-leaks` | 64/64 expected lines: 50 types' names, layouts and properties, the 13×13 cast matrix, interning identity; no leaks |
| 2026-10-30 | S0 | `src/hir/hir.nova` and `hir_printer.nova` (a port of HirPrinter, quirks included); `src/support/dotnet_double.nova` against .NET 10's `double.ToString("R")` through `tools/oracles/double-format` (`tests/support/run-pass/dotnet-double.nova`, generated) | 733/733 patterns identical. .NET switches to `E±XX` at decimal exponents ≥ 17 or < -4. Its shortest search differs from the exact one at 2^-25 and 2^-958 only, out of all 2,098 powers of two: those two are spelled as .NET spells them. The printer is checked against reference dumps from S1 on |
| 2026-10-30 | S1a | `src/check/` (checker, declare, body, expr, consts), `src/library/sources.nova` (generated), `ceesafec check --dump-hir`; `compare_parse.py --command check` against novac 0.4.1 | the 11 S1 check-pass files identical (HIR, JSON and text); 16 of the 20 S1 check-fail files identical; over the corpus, 83 of 320 check programs identical (56 of the 159 run-pass). ASan+UBSan, `live=0` |
| 2026-10-30 | S1b | char and float literals; `src/support/decimal_float.nova` (exact decimal→f64/f32) against .NET's `double.Parse`/`float.Parse` through `tools/oracles/decimal-parse` (`tests/support/run-pass/decimal-float.nova`, generated: halfway cases, subnormals, range ends, random); float folding; `--no-float`; function values and calls through them; `round`/`checkedTruncate`/`saturatingTruncate`/`fromBits`; `compare_parse.py` passes each file's `// option:` lines | 680/680 parses bit-identical; S1 check-fail 18/20 identical (2 blocked on S2/S4 constructs, their HIR identical); 85 of 320 corpus check programs identical; ASan+UBSan clean, `live=0` |
| 2026-10-30 | S2a | structs: declaration, the built-in items as real types (AllocError, IoError, SystemHeap, FailingAllocator), members (fields, drop, methods), recursion (N0227), Copy and drop, struct literals, field access, `this`, method and static calls, assignment through places (`src/check/places.nova`, `structs.nova`, `members.nova`) | check-pass `structs` and check-fail `structs`, `no-float` identical; 99 of 320 corpus check programs |
