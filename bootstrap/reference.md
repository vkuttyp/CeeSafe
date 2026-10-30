# Stage-0 pin and Nova reference

Recorded 2026-10-30. Updated only by an explicit rebaseline (below), never silently.

## Stage-0 compiler (builds CeeSafe until it builds itself)

| Item | Value |
|---|---|
| Compiler | `novac 0.5.0` (released NativeAOT binary) |
| Path on the owner's Mac | `~/.nova/0.5.0/bin/novac` (darwin arm64, 11,037,504 bytes, signed; the same binary as `~/.nova/bin/novac` today, but CeeSafe uses the versioned path) |
| sha256 | `418272819e368829171978fb166bc38aecbd87d7f2ead14a319ea82f2d6f9c3d` (inside `novac-osx-arm64.tar.gz`, which matches the release's `SHA256SUMS`) |
| Source | Nova tag `v0.5.0` = `af071d447756a7d67fe9e20a559c4741c54b5e1b` (main, 2026-10-30) |
| C compiler | Apple clang 21.0.0 (clang-2100.3.34.2) |
| Linux x64 binary (Ryzen box) | `novac-linux-x64.tar.gz` sha256 `173bf7393e11d12de80bb53a48449388b6f5de8197f695005c4b156a7f04fc7b` (the release's `SHA256SUMS`); not yet installed on the box: the 0.4.1 binary stays in `/root/ceesafe-p0/r041/novac` until the next Ryzen gate run |

The `novac` on `PATH` (`~/.local/bin/novac`) wraps the Release build of `~/Nova`'s working tree and reports a `-dev`
version: it is **not** the stage-0 compiler. Other hosts download the same release from
`https://github.com/vkuttyp/Nova/releases/tag/v0.5.0` and record their binary's hash here.

## Reference implementation (what the port must match)

| Item | Value |
|---|---|
| Nova commit audited | `af071d447756a7d67fe9e20a559c4741c54b5e1b` (tag `v0.5.0`, 2026-10-30), clean tree |
| .NET SDK | 10.0.401 |
| Specs and ADRs | Nova's `docs/` at that commit (ADRs 0001–0029) |

The behaviour oracle is the stage-0 release (`v0.5.0`), whose source is the audited commit, so the two cannot differ.
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
