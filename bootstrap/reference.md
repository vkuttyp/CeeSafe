# Stage-0 pin and Nova reference

Recorded 2026-10-30. Updated only by an explicit rebaseline (below), never silently.

## Stage-0 compiler (builds CeeSafe until it builds itself)

| Item | Value |
|---|---|
| Compiler | `novac 0.4.1` (released NativeAOT binary) |
| Path on the owner's Mac | `~/.nova/0.4.1/bin/novac` (darwin arm64, 11,021,056 bytes, signed; `~/.nova/bin/novac` stays 0.3.1, CosmoOS's pin) |
| sha256 | `3a6cebf5c588063a2e504bfd01ccff11a2d43238891ad748c764009178cd0d92` (inside `novac-osx-arm64.tar.gz`, which matches the release's `SHA256SUMS`) |
| Source | Nova tag `v0.4.1` = `80d8d8c0a8c9845dd0c522dd7738c424d1dc4b0d` (branch `release-0.4`, 2026-10-30) |
| C compiler | Apple clang 21.0.0 (clang-2100.3.34.2) |
| Linux x64 binary (Ryzen box) | `novac-linux-x64.tar.gz` sha256 `57a2903a5b0dbab93226deb7330b4596055c58f33a7ebb11d842100daf6a8fa6` (matches the release's `SHA256SUMS`); `novac` inside, sha256 `a0727974c95ed9e53909978a7837ddfa910c57e1ca39319d0bc3040840bd48fc`; kept in `/root/ceesafe-p0/r041/novac` |

The `novac` on `PATH` (`~/.local/bin/novac`) wraps the Release build of `~/Nova`'s working tree and reports a `-dev`
version: it is **not** the stage-0 compiler. Other hosts download the same release from
`https://github.com/vkuttyp/Nova/releases/tag/v0.4.1` and record their binary's hash here.

## Reference implementation (what the port must match)

| Item | Value |
|---|---|
| Nova commit audited | `80d8d8c0a8c9845dd0c522dd7738c424d1dc4b0d` (tag `v0.4.1`, 2026-10-30), clean tree |
| .NET SDK | 10.0.401 |
| Specs and ADRs | Nova's `docs/` at that commit (ADRs 0001–0028) |

The behaviour oracle is the stage-0 release (`v0.4.1`), whose source is the audited commit, so the two cannot differ.
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
