# Stage-0 pin and Nova reference

Recorded 2026-10-30. Updated only by an explicit rebaseline (below), never silently.

## Stage-0 compiler (builds CeeSafe until it builds itself)

| Item | Value |
|---|---|
| Compiler | `novac 0.3.1` (released NativeAOT binary) |
| Path on the owner's Mac | `~/.nova/bin/novac` (darwin arm64, 10,905,936 bytes) |
| sha256 | `81c5b5013473f9e5358560fc24c062b293ee272c7b28944ce87696c2749d0a0b` |
| Source | Nova tag `v0.3.1` = `4481e12e3b5fa5cbe53e7b333e13afd3695989b2` (branch `release-0.3`, 2026-10-29) |
| C compiler | Apple clang 21.0.0 (clang-2100.3.34.2) |
| Linux x64 binary (Ryzen box) | `novac-linux-x64.tar.gz` sha256 `bbeb82c5617123556b403ab2a5e3bdf22a530fe8ed51371ed0673bacbabcbff7` (matches the release's `SHA256SUMS`); `novac` inside, sha256 `8bd8d81b9a0355453f68fe7c338a5478cf3c142c90526fffaaf1bd6b309ad973`; kept in `/root/ceesafe-p0/novac-0.3.1` |

The `novac` on `PATH` (`~/.local/bin/novac`) wraps the Release build of `~/Nova`'s working tree and reports a `-dev`
version: it is **not** the stage-0 compiler. Other hosts download the same release from
`https://github.com/vkuttyp/Nova/releases/tag/v0.3.1` and record their binary's hash here.

## Reference implementation (what the port must match)

| Item | Value |
|---|---|
| Nova commit audited | `07d561f35bc731140ba3e3ea0343bdb36ed04dfc` (`main`, 0.4.0-dev, 2026-10-30), clean tree |
| .NET SDK | 10.0.401 |
| Specs and ADRs | `~/Nova/docs` at that commit (ADRs 0001–0027) |

The behaviour oracle is the stage-0 release (`v0.3.1`) unless a phase says otherwise. `07d561f` adds M14 K1 negative
tests and docs on top of 0.3.x; differences between the two are listed by the P0 inventory, not assumed.

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
