# P3 plan — names, types, generics, HIR

Status: **S1, S2, S3a and S3b done** (2026-10-30; pinned to novac 0.5.0 since S2b). S1: functions, statements, operators, casts, constants, char and float literals with exact parsing and folding, `--no-float`, function values, and the Console and Process builtins. S2a: structs, members, places and method calls. S2b: enums (`E.V`, `E.V(…)`), `match` statements and expressions, `if` expressions, simple and nested patterns with usefulness (`src/check/patterns.nova`, `usefulness.nova`). S2c: `T?` and `Result<T, E>`, `null`, `Some`, `Ok`/`Err`, `?`, `!`, null tests, `T` to `T?`, `defer` (`src/check/options.nova`). S2d: reference types and source lists, `borrow`, `move`, reference and `mut` arguments, return sources (`src/check/references.nova`). S2e: arrays, slices, indexing, `length`, `for` over arrays and slices, constant arrays (`src/check/arrays.nova`). Of S2's nine check-pass targets eight are identical; `moves-accepted` waits on `using` (S3). S3a: `Box<T, A>`, `Box.create`/`createIn`, the built-in allocators, `FailingAllocator.failAfter`/`reset`, the `borrow Box<T>` to `borrow T` reborrow (`src/check/boxes.nova`). S3b: `Vector<T, A>`, `String<A>`, their creation and methods, vector `length`/`capacity`/indexing/`for`, printing a `String`, `s.bytes()`, `StringView.fromUtf8`, slice `copyFrom`/`fill` (`src/check/vectors.nova`); the methods that call lib/core wait for S5/S6. Over the corpus, 160 of 320 check programs are identical. Of the differing files, the 13 without an N0216 differ only by the borrow checker's diagnostics (P4: N0240–N0245, N0250, N0212) or effects (S6); the rest need containers, strings and regions (S3), generics (S4) or later slices. Next: S3c. S3 is split like S2: S3a boxes and allocators; S3b vectors, strings and string views; S3c slot maps, stable vectors and pools; S3d regions, arenas, scratch and `using`; S3e I/O and the integer and float methods. This plan comes from a read of the reference at `v0.4.1`. File:line references below
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

- `run_corpus.py --reference ~/.nova/0.5.0/bin/novac --family check-pass` compares the HIR snapshot, the diagnostics,
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
| 2026-10-30 | — | re-pinned to novac 0.5.0 (`bootstrap/reference.md`); the reference checkout and the `TypeChecker.cs` copy moved to `v0.5.0` | `check` over the corpus: 99/320 identical, the same as with 0.4.1 |
| 2026-10-30 | S2b | enums: `E.V` and `E.V(…)` (CheckEnumValue); `match` statements and expressions (CheckMatch, CheckNestedMatch, CheckPattern, DeclareBinding, ResolvePatternVariant); a port of `PatternUsefulness` (Maranget) for nested patterns, with witnesses; `if` and `match` expressions (CheckBranching, deferred flexible and `null` branches, N0235); `tests/check/{check-pass,check-fail}/enums-and-match.nova`, which cover what the corpus's nested-pattern files cannot reach before S2c (they need Result and optionals); `compare_parse.py --list` | the two `tests/check` files identical to novac 0.5.0 (check-pass: HIR, JSON and text; check-fail: JSON and text, 23 errors, since the reference's HIR printer throws on it); check-fail `enums` differs only by N0270 (a scoped payload, S3); corpus 101/320 identical, up from 99 (`payload-reads`, `temporaries-on-early-exit`), no file regressed (`--list` before and after); ASan+UBSan clean, `live=0` |
| 2026-10-30 | S2c | `T?` and `Result<T, E>` types (and the reference's messages for wrong or unknown generic arguments); `null`, `Some(…)`, `Ok(…)`/`Err(…)` against the expected type (CheckNull, CheckSomeValue, CheckResultValue); `?` and `!` (CheckResultOperand, CheckTry; N0261, N0262); `o == null` (SynthNullTest: borrow, reborrow or temporary borrow); a `T` where `T?` is expected, tried quietly as the reference does; `defer` with FindJump (N0254); `Process.argument` | `tests/check/{check-pass,check-fail}/results-and-optionals.nova` identical (HIR, JSON, text); check-fail `optionals` identical in JSON and text (the reference's HIR printer throws on it); corpus 107/320, up from 101 (`results`, `branch-expressions`, `defer`, `consuming-match`, `io-error-results`, `result-propagation`), no file regressed; check-fail `results` and `nested-patterns` differ only by references (S2d), generic enums (S4) and N0270 (S3); ASan+UBSan clean, `live=0` |
| 2026-10-30 | S2d | reference types, with a return type's source list `borrow(a, b) T` (N0246 elsewhere); `borrow e` (BorrowPlace), `move e`, a stray `mut e` (N0249); CheckArgument in full: implicit shared borrows of places and temporaries, `mut` arguments, box and vector contents, MutArgumentFix with its two-edit fix (diagnostics gained a second edit); ResolveFlows' return sources and ResolveReturnSources (N0245) for signatures without regions or type parameters, stored on `HirFunction.returnSources` for P4 | `tests/check/{check-pass,check-fail}/references.nova` identical (HIR, JSON with fixes, text; 23 errors); corpus 122/320, up from 107 (check-pass `references`, `borrows-accepted`, `enums`, `scoped-payload-liveness`; check-fail `borrow-expressions`, `optional-references`, `reference-types`; eight run-pass), no file regressed; ASan+UBSan clean, `live=0` |
| 2026-10-30 | S2e | `[T; N]`, `Slice<T>`, `SliceMut<T>` (and `Slice<static, T>`, `StringView<static>`, `borrow(static) T`; N0273 for another name); CheckElement with Copy-ness checked once known (pending elements, N0259) and the 2^31-byte limit; array literals and repeats, indexing, slicing (SynthSlice), `length`, `for` over arrays and slices (non-Copy elements borrowed); constant arrays (Fold, and the whole array where the name is used). `compare_parse.py --list` now writes a sorted list: the S2b–S2d regression checks were rerun on sorted lists and still show none | `tests/check/{check-pass,check-fail}/arrays-and-slices.nova` identical (HIR, JSON, text; 27 errors); corpus 132/320, up from 122 (check-pass `arrays`, `slice-borrows-accepted`; check-fail `arrays`, `array-of-broken-struct`, `scoped-types`, `slice-returns`; run-pass `arrays`, `slices`, `for-drops`, `ex11-errors`), no file regressed; S2's check-pass targets 8/9 (`moves-accepted` needs `using`, S3); ASan+UBSan clean, `live=0` |
| 2026-10-30 | S3a | `src/hir/builtins.nova`, generated from the reference's BuiltinFunction by `tools/gen_builtins.py` (the S1 numbering for function-value calls and `fromBits` was a placeholder); `Box<T>` and `Box<T, A>`; CheckBoxAllocator (N0263; a field-less struct is a user allocator, S4); `Box.create`/`createIn` with the expected result's hint (CheckBoxCreate); FailingAllocator's `failAfter`/`reset`; Coerce's `borrow Box<T>` → `borrow T` reborrow | `tests/check/{check-pass,check-fail}/boxes.nova` identical (HIR, JSON, text; 16 errors); corpus 143/320, up from 132 (check-pass `boxes`; run-pass `deep-structures`, `ex14-tree`, `ex4-account`, `ex5-allocator`, `heap-stress`, `optional-references`, `readme-ownership` and others), no file regressed; ASan+UBSan clean, `live=0` |
| 2026-10-30 | S3b | ResolveVectorType and VectorType (with the result and option types they create), a bare `String`, and N0204 for `Vector`, `SlotMap`, `StableVector`, `Handle` without type arguments; CheckVectorCreate (`Vector<T>.create()`, the expected type's hint, `withCapacity`); CheckVectorMethod (`push`, `pop`, `clear`, `truncate`, `view`, `viewMut`, `bytes`, `append`, `appendNumber` with NumberToFormat; two-phase argument order); CheckViewMethod; CheckSliceMethod's `copyFrom` and `fill` on slices and slice expressions; CheckStringViewFunction; PrintableView; vector `capacity`, `length`, indexing and `for` (over a view); CheckMethodCall now follows the reference's dispatch order for slices, vectors, boxes and views | `tests/check/{check-pass,check-fail}/vectors-and-strings.nova` identical (HIR, JSON, text; 25 errors); corpus 160/320, up from 143 (check-fail `append-number`, `string-view-from-utf8`, `string-views`, `vectors`; 13 run-pass), no file regressed; ASan+UBSan clean, `live=0` |
