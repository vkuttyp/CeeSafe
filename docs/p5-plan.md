# P5 plan: the flat C backend and the native build

Status: **in progress** (started 2026-10-30; pinned to novac 0.6.0).

P5 ports what runs after the safety passes when novac builds (reference `v0.6.0`):

1. `CBackend.Generate` (`Backend.C/CBackend.cs`, 308 lines): N0300 for a missing `main`, the emitter, the exports
   header, and the runtime files the program needs (`rt.h`, the core, hosted, I/O, float and thread runtimes).
2. `CEmitter` (`Backend.C/CEmitter.cs`, 3,944 lines) in its flat form: one label per NIR block, no structuring.
3. The toolchain (`Toolchain`, `CCompilers.cs`, 191 lines): the strict warning set, the semantic flags, `-O2` or
   `-g -O0`, objects joined with `-r`, and the build command of `Nova.Cli/Program.cs`.

Not P5 (P7's): the structured form (`CStructurer.cs`), placement (`PlacementAnalysis`), bounds- and overflow-check
elimination (`CheckElimination`) and closure-call specialisation. `ceesafec` accepts the switches that turn them off
(`--flat-c`, `--no-placement`, `--no-bce`, `--no-oce`, `--no-closure-specialisation`) and always behaves as if they
were given. `--split` and `-g`/`--line-directives` are in P5 (the C matrix carried from P0, `docs/parity.md` §3).

## How it is compared

- **C:** `novac build --emit c -o DIR --flat-c --no-placement --no-bce --no-oce --no-closure-specialisation` against
  `ceesafec build --emit c -o DIR`: every file of the output directory byte-identical, except the generated-by
  banner's compiler name and version (`tools/compare_c.py`). Over every program novac builds, with the corpus's
  options.
- **Behaviour:** `tools/run_corpus.py --compiler ceesafec` over run-pass, run-fail, ffi and freestanding, under the C
  matrix (clang `-O0`/`-O2`, the overflow fallback, ASan+UBSan, GCC on the Ryzen box).
- **Fault sweep:** `FaultInjectionTests.cs` ported: every run-pass program that allocates, under ASan+UBSan, failing
  each allocation in turn; ceesafec's outcomes must equal novac's built with the same switches.

## Slices

| Slice | Content | Gate |
|---|---|---|
| **S0** | `src/backend/`: names, C types and mangling, the program skeleton, structs and enums, functions in flat form, statements, rvalues and terminators for the S0-level programs; `tools/gen_runtime.py` (the runtime embedded as `src/library/runtime.nova`); `build --emit c`; `tools/compare_c.py` | C identical for the programs whose types S0 emits |
| **S1** | The rest of CEmitter: drop glue, boxes and allocators, vectors, strings, containers, I/O, arenas, pools, `dyn`, closures, threads and forks, statics, FFI, imported structs, exports, callbacks, the exports header, `#line` | C identical over every program novac builds |
| **S2** | `--emit exe` and `--emit obj`: the toolchain, temporary directories, `Process.capture`; `-g`, `--cc`, `--cflag`, `--ld`; `--split` | run-pass, run-fail, ffi and freestanding pass with ceesafec |
| **S3** | The C matrix, the fault sweep, objects for both CosmoOS architectures, CeeSafe built by ceesafec's C | the P5 gate (`ROADMAP.md` §P5) |

## Execution record

| Date | Slice | Work | Result |
|---|---|---|---|
| 2026-10-30 | S0, S1 | `src/backend/` (the whole flat CEmitter: `c_names`, `c_emitter`, `c_program`, `c_skeleton`, `c_interop`, `c_helpers`, `c_dyn`, `c_body`, `c_backend`), `tools/gen_runtime.py` (`src/library/runtime.nova` from `v0.6.0`), `build --emit c [-o DIR] [--exports-header NAME]`, `tools/compare_c.py`. P3 gaps closed: built-in items' `Used` marks (`src/check/program_tables.nova`), HirProgram's Structs and DynSignatures computed where the reference does, and types made in library code not marked the program's (`Checker.setFile`, TypeTable.InHostedLibrary). Layouts are computed once before emitting, so the emitter reads the checker immutably | **C identical for all 284 programs novac builds** (every corpus family: run-pass, run-fail, emit-c, ffi, freestanding, placement, bounds-, overflow- and closure-check families), banner aside; CeeSafe's own C identical (394,094 lines; ceesafec 1.4 s, 143 MB, novac 4.1 s); that C, compiled by cc -O2, gives a ceesafec whose output is identical. Unchanged: check 318/322, other families 84/84, NIR 284/284, packages 7/7, self-check clean |
