# P4 plan: NIR and the safety passes

Status: **in progress**: S0–S4 done (2026-10-30; pinned to novac 0.6.0); next S5.

P4 ports what runs after the type checker in `Compilation.CreateOnCompilerStack` (reference `v0.6.0`, `Compilation.cs`):

1. `NirBuilder.Build(hir, types)`: the HIR lowered to NIR, a control-flow graph per function (`Nir/Nir.cs`, 348
   lines; `Nir/NirBuilder.cs`, 1,630).
2. For every function that is not an instantiation, in order: `InPlaceChecker` (143), `MoveChecker` (213, with
   `MovePaths`, 383), `BorrowChecker` (705).
3. If nothing failed: N0222 for each instance whose body did not check (the `InstanceError` P3 records).
4. If nothing failed: `DropElaborator` (201) on every function that is not a generic version, then `EffectChecker`
   (654) over the program.

Not P4: closure-call specialisation, placement and check elimination (`ClosureSpecialisation.cs`,
`PlacementAnalysis.cs`, `CheckElimination.cs`) are P7's; the C backend is P5's.

## How it is compared

- **Diagnostics:** `ceesafec check` against `novac check`, as in P3 (`tools/compare_parse.py --command check`): the
  55 check programs that differ today differ only by these passes' diagnostics (N0212, N0222, N0240–N0245,
  N0250–N0253, N0272, N0294's in-place cases, N0295) or by novac's three printer crashes.
- **NIR:** `novac build --emit c -o DIR --dump-nir --no-closure-specialisation --no-placement --no-bce --no-oce` prints
  the compilation's NIR after drop elaboration (`NirPrinter`; lib/core's functions left out). `ceesafec build
  --dump-nir` prints the same and stops: the C backend is P5. A new `tools/compare_nir.py` compares them over every
  program novac builds (run-pass, check-pass, emit-c, ffi, freestanding, the probes), with the corpus's options.
- **Expectations:** `MutationTests.cs` and `FaultInjectionTests.cs` (the M2 mutation suite and the M3 fault sweep)
  are ported as fixtures in the last slice.

The reference's NIR is records with object identity (blocks, locals); CeeSafe keeps arenas with indices, as the HIR
does (`src/hir/hir.nova`). The printer's text is the contract.

## Slices

| Slice | Content | Gate |
|---|---|---|
| **S0** | `src/nir/nir.nova` (the model), `src/nir/nir_printer.nova`, `ceesafec build --dump-nir`, `tools/compare_nir.py`; NirBuilder's skeleton: functions, locals, blocks, statements, operators, calls, constants, returns, `if`/`while`/`loop`/`for`, StorageDead | NIR identical for the S1-level run-pass programs (no drops yet: types without drop) |
| **S1** | MovePaths and DropElaborator (drop flags, partial moves, box frees) | NIR identical for every program whose constructs S0 lowers, drops included |
| **S2** | NirBuilder for the rest of the HIR, in P3's order: structs, enums and `match`, optionals and results (`?`, `!`), references, arrays and slices, boxes, vectors, strings, containers, regions, generics, interfaces, `dyn`, closures, threads, statics, `unsafe` and FFI (split like P3's slices as it goes) | NIR identical over every program novac builds |
| **S3** | InPlaceChecker and MoveChecker (N0250–N0253, N0294's in-place cases, N0212 if it is theirs) | the move families of check-fail identical |
| **S4** | BorrowChecker (N0240–N0245, N0272; the sticky shared deref, N0248) and N0222 for failed instances | check-fail identical except novac's printer crashes and `offset-of` |
| **S5** | EffectChecker (N0295) | every check program identical but those three and `offset-of`; `check` is the full pipeline |
| **S6** | The mutation and fault-injection expectations; every invariant of `docs/ownership.md` mapped to positive and negative evidence | the P4 gate (`ROADMAP.md` §P4) |

## Execution record

| Date | Slice | Work | Result |
|---|---|---|---|
| 2026-10-30 | S0, S2 | `src/nir/nir.nova` (arenas), `nir_printer.nova`, `nir_builder.nova` (the whole of NirBuilder, so S2 came with S0), `build --dump-nir`, `tools/compare_nir.py`; `gen_builtins.py` emits `builtinFunctionName` | before drops: 174 of 270 built programs identical, every difference a drop |
| 2026-10-30 | S1 | `src/nir/move_paths.nova` (MovePath, InitState as bitsets, MoveData's FIFO dataflow), `src/nir/drops.nova` (DropElaborator; flags kept in creation order, as the reference's dictionary); HIR's never-set `isGeneric`/`isInstantiation` fields removed for `functionIsGeneric` (statics' constant-function loop too) | `compare_nir.py` over every corpus family: 474 files, 284 built by novac, **284 identical**; CeeSafe's own NIR (package mode) identical, 429,006 lines, ceesafec 0.30 s, 79 MB. Unchanged: check 266/322 and 84/84, parse 487/487, packages 7/7, `fmt --check` clean |
| 2026-10-30 | S3 | `src/nir/move_check.nova` (InPlaceChecker, MoveChecker), `src/nir/passes.nova` (the pipeline after the checker: NIR, in-place and move checks on functions that are not instantiations, N0222, drops); `check` now runs it | check-pass/check-fail/run-pass **275**/322 (was 266); no N0212, N0222, N0250–N0253 or N0294 line differs in the 47 left (borrow checking, effects, novac's printer crashes, `offset-of`); other families 84/84; NIR 284/284; packages 7/7 |
| 2026-10-30 | S4 | `src/nir/borrow.nova` (BorrowChecker: loans, points-to, through-writes and N0272, liveness, conflicts N0240–N0243 with notes, returns N0244/N0245; live sets enumerate as .NET's HashSet, free slots reused LIFO, since the reference's report order follows them); diagnostics gained notes (text `= note:` lines and JSON); P3 gap fixed: flow names for type parameters (`t:`, the function's and the receiver struct's), so generic functions' return sources and mutable flows match | check-pass/check-fail/run-pass **308**/322: the 14 left are N0295 (S5: 11), novac's printer crashes (enums, optionals, results) and `offset-of`; other families 84/84; NIR 284/284; packages 7/7; `ceesafec check` of CeeSafe itself clean, as with novac (0.88 s, 71 MB), HIR identical |
