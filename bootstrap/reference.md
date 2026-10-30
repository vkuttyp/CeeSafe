# Stage-0 pin and Nova reference

Recorded 2026-10-30. Updated only by an explicit rebaseline (below), never silently.

## Stage-0 compiler (builds CeeSafe until it builds itself)

| Item | Value |
|---|---|
| Compiler | `novac 0.6.0` (released NativeAOT binary) |
| Path on the owner's Mac | `~/.nova/0.6.0/bin/novac` (darwin arm64, 11,070,352 bytes, signed; the same binary as `~/.nova/bin/novac` today, but CeeSafe uses the versioned path) |
| sha256 | `1d8b8f1f7eaea16f831bdf98014d5f51a65673cd50497e754cae218659d78374` (inside `novac-osx-arm64.tar.gz`, which matches the release's `SHA256SUMS`) |
| Source | Nova tag `v0.6.0` = `93e0a4671eb89354d42f9b47755ea21f8ff9ad1d` (main, 2026-10-30) |
| C compiler | Apple clang 21.0.0 (clang-2100.3.34.2) |
| Linux x64 binary (Ryzen box) | `novac-linux-x64.tar.gz` sha256 `977472da73d96eea4a43230aa083820da6c85872690960960cf8eaf9882c193c` (the release's `SHA256SUMS`); not yet installed on the box: the 0.4.1 binary stays in `/root/ceesafe-p0/r041/novac` until the next Ryzen gate run |

The `novac` on `PATH` (`~/.local/bin/novac`) wraps the Release build of `~/Nova`'s working tree and reports a `-dev`
version: it is **not** the stage-0 compiler. Other hosts download the same release from
`https://github.com/vkuttyp/Nova/releases/tag/v0.6.0` and record their binary's hash here.

## Reference implementation (what the port must match)

| Item | Value |
|---|---|
| Nova commit audited | `93e0a4671eb89354d42f9b47755ea21f8ff9ad1d` (tag `v0.6.0`, 2026-10-30), clean tree |
| .NET SDK | 10.0.401 |
| Specs and ADRs | Nova's `docs/` at that commit (ADRs 0001–0030) |

The behaviour oracle is the stage-0 release (`v0.6.0`), whose source is the audited commit, so the two cannot differ.
Oracles built from the reference's source (`tools/oracles/token-dump`) are built from a checkout at this tag.

## Rebaselining

Nova keeps evolving (decision 0001 §4). A rebaseline is its own change:

1. Pick a released novac (normally one that ships N-track items CeeSafe needs).
2. Record its version, tag commit and per-host hashes above; keep the old row in the history below.
3. Rebuild CeeSafe and rerun the gates of every completed phase with the new pin; rerun the reference fixture export
   (P0) and review every changed expectation against Nova's changelog and specs.
4. Note the result in ROADMAP §10.

## History

| Date | Pin | Reason |
|---|---|---|
| 2026-10-30 | novac 0.3.1 (`4481e12`) | initial pin |
| 2026-10-30 | novac 0.4.0 (`66b6bda`) | M15: fixes for #1–#5, N0110/N0222, `StringView.fromUtf8`, host services (ADR 0028); the P1 workarounds removed |
| 2026-10-30 | novac 0.4.1 (`80d8d8c`) | the point release for N7: 0.4.0's lib/std reserved the names of its helpers (`pathIn`, `fromAlloc`, …), so the probes had to avoid them |
| 2026-10-30 | novac 0.5.0 (`af071d4`) | ADR 0029 (`@repr(C)` structs holding C state and arrays); taken at P3 S2b, before any S2b code, as planned after S1. lib/ is unchanged from 0.4.1 and the checker change is 9 lines in `IsFfiSafe` (S7) |
| 2026-10-30 | novac 0.6.0 (`93e0a46`) | ADR 0030 (`offsetOf<T>(field)`, `callerAddress()`, lib/kernel's `List`, one definition per C name); taken after P3. The checker change is two builtins (`TypeChecker.cs` +78 lines), which shift the reference's Builtin numbering; lib/ gains `lib/kernel/list.nova`; two diagnostics (N0339, N0340). One reference bug found: `offsetOf` reads a field's offset before the struct is laid out, so it is 0 unless the layout was computed earlier; ceesafec gives the true offset (`docs/p3-plan.md`). Gates rerun: P1 probes 16/16, support 8/8 and the type table 1/1 with no leaks, fault sweep 573/573; parse 487/487; check 266/322 (the rest P4, novac's printer crashes, and `offset-of`), the other families 84/84, check-pass and HIR snapshots 27/27, package fixtures 7/7, CeeSafe's own check identical; ASan+UBSan clean |

## Fixed points

Each verified fixed point (ROADMAP P6) archives its manifest in `bootstrap/fixed-point/`: the commit, the stage-0
binary's hash, the C compiler, every output's sha256 and the subprocess audit. Rerun with
`python3 tools/fixed_point.py --novac <stage 0> --commit <commit> --work <dir> --manifest <file>`; the C hashes must
equal the archived ones.

- 2026-10-30, `1b1aae4`, novac 0.6.0: macOS arm64 (Apple clang 21) and Linux x86-64 (GCC 12), same C
  (`main.c` `40374dbf…`).
