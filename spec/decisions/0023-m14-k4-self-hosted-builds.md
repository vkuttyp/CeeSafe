# ADR 0023 — M14 K4: building a Nova kernel where novac does not run

> **Inherited from Nova.** This is Nova's ADR 0023, which CeeSafe inherited at the fork (Nova `v0.6.0`; CeeSafe's
> Decision 0006). Its text is Nova's record and is not changed: read Nova and `novac` as the language and compiler
> CeeSafe forked from, `.nova` as `.cee`, and Nova's C names as CeeSafe's (`spec/c-backend.md`). Links to documents
> CeeSafe did not fork go to Nova's repository.

- Status: **Accepted** (project owner, 2026-10-29, taking every recommendation in §5). The wording is the agent's.
- Scope: M14 K4, OD-31. CosmoOS's roadmap 2.0 makes two choices that conflict once its kernel is Nova. Its rule 7
  stops committing generated C, so every build runs novac. Its SW0 makes CosmoOS build itself. novac does not run on
  CosmoOS.

## 1. Context

- **novac** is a .NET program, distributed as NativeAOT binaries for Linux, macOS and Windows on x64 and arm64
  (`release.md`). NativeAOT needs a .NET runtime port for each operating system, and CosmoOS has none. It runs Linux
  programs through its personality, but not the .NET runtime's full use of Linux: threads, `mmap` and signal-based GC
  suspension (inferred; untested).
- **Today** CosmoOS commits the generated C beside each `.nova` file, so any machine with a C compiler builds the
  kernel. That is what makes a self-hosted build possible now.
- **Generated C is a pure function** of the sources and novac's version (c-backend §1; CosmoOS checks it in CI).

## 2. Options

| | A. Source releases carry the generated C (proposed) | B. novac on CosmoOS | C. A Nova compiler in Nova | D. Keep committing generated C |
|---|---|---|---|---|
| Self-hosted build | from a release tarball, no novac | yes | yes | yes |
| Changing a `.nova` file on CosmoOS | needs a host with novac | yes | yes | needs a host with novac |
| Cost | a `make dist` target and a CI check | a .NET runtime port, or the Linux personality running .NET | years | the tree doubles as the kernel becomes Nova |

## 3. Proposed decision: A

- The repository holds `.nova` sources only, as roadmap 2.0's rule 7 says. `make dist` (CosmoOS) writes a source
  tarball with the generated C beside each `.nova` file, made by the pinned novac. A build from the tarball runs no
  novac.
- CI checks that the tarball builds without novac on both architectures, and that its C matches a fresh generation
  (the reproducibility check rule 7 already plans).
- A self-hosted CosmoOS builds its kernel from a release tarball. Developing the kernel's Nova code on CosmoOS itself
  needs a machine with novac until B or C exists. Both stay open as later decisions; C is the long-term direction for a
  self-hosting Nova.
- Nova needs nothing new for A: `novac build --emit c` already writes the files, with ADR 0022's `--split` layout when
  the kernel uses it.

## 4. Consequences

- SW0's self-hosting acceptance builds the kernel from the release tarball.
- CosmoOS's roadmap 2.0 and `docs/build/nova.md` record the choice (a CosmoOS PR once this is accepted).

## 5. Questions for the owner

1. Option A? (Recommended.)
2. Record B (novac on CosmoOS) and C (a Nova compiler written in Nova) as open decisions for later? (Recommended.)
