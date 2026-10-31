# CeeSafe's own specification

Decision 0006 (accepted 2026-10-31): CeeSafe's specification is a fork of Nova's text at `v0.6.0`, with Nova's ADRs
inherited and the guide forked with checked examples. This page records how it was made and checked.

## What was done

| Step | What | Where |
|---|---|---|
| Fork | `tools/fork_spec.py` (run once, refuses to overwrite) wrote 17 documents into `spec/`, 30 ADRs into `spec/decisions/`, 26 guide pages into `guide/` and the agent template into `templates/`, from a clean Nova `v0.6.0` checkout. Text renamed by `tools/names.py`'s forward map (URLs held out); links rewritten to the new places, or to Nova's repository at the tag for documents not forked; the guide's site links (`./basics`, `/reference/type-system`) made file links | `spec/`, `guide/`, `templates/AGENTS.md` |
| Fork-point changes | `c-backend.md` §1.2 (the ABI version and linking with Nova), the reserved C names (`cee` and a capital, in `c-backend.md` §2.1, `type-system.md` §28, `diagnostics.md` N0292), `.cee`/`.c` only (`spec/README.md` §3); `spec/README.md` written: the documents, the decisions, what the fork changed, how to read the text (milestone tags, Nova links, CosmoOS history, paths, test names) | `spec/` |
| Rewritten | `architecture.md` (Nova's C#/.NET M0 proposal → ceesafec's pipeline and modules), `testing.md` (Nova's C# test classes and execution log → the corpus format and CeeSafe's tools), the guide's installation page (no releases yet: build from source with `tools/bootstrap.sh`), the agent guide's site links | |
| Corrected | statements true only of Nova: C# source paths (→ `src/…`), the interpreter's .NET floats and math (→ CeeSafe's), the language server's UTF-16 columns, CosmoOS ports "written in CeeSafe" (→ in Nova), the README claim, `~/.cee` (→ `~/.ceesafe`), the registry URL, the guide page `novac.md` (→ `ceesafec.md`), the slice example whose output the rename changed; Nova's C# test classes named as Nova's, with CeeSafe's tool beside them | |
| Embedded | `tools/gen_docs.py` embeds `spec/`, `guide/` and `templates/AGENTS.md`, and writes the places the tools look for as functions (`specDirectory`, `diagnosticsDocument`, `agentGuideDocument`, `introductionDocument`, `agentTemplateDocument`); `explain`, the MCP server and `agents` use them. `tools/gen_catalog.py` takes the JSON summaries from `spec/`. The compiler's messages cite the new paths (`profiles.md` §4, `spec/tooling.md` §4.3, `guide/basics.md`), mapped back by three new rules in `tools/names.py` | `src/library/documents.cee`, `src/diagnostics/catalog.cee` |
| Checked | `tools/spec_check.py`, `tools/guide_check.py`, `tools/reference_docs.py` (a ceesafec with novac's documents, for the CLI and server comparisons); all three in the contract suite (36 steps) | |

## Evidence (run 2026-10-31, macOS, Apple clang 21)

- `tools/names.py` with the path rules: `map_back(map_forward(x)) == x` for all 651 runtime, library, corpus,
  benchmark, program, integration and template files of Nova `v0.6.0` and for Nova's C# compiler sources; the only
  files it does not invert are 16 of Nova's history documents, which no generator reads.
- `tools/fork_corpus.py` rerun with the new rules: `tests/reference/` changes in one harness comment only.
- `tools/reference_docs.py` build against novac 0.6.0: usage 17/17, `explain` 1,009/1,009, `fix` 177/177 identical;
  LSP 438/438 and MCP 433/433 sessions identical (441 at S5; three sessions are the fork divergences that
  `compare_servers.py` skips since S7).
- `tools/spec_check.py`: 75 documents, 132 codes explained, 100 links, `spec/api/core.md` equal to `ceesafec doc`'s
  page, no stray Nova names: 0 problems.
- `tools/guide_check.py`: 92 examples (4 skipped by their pages, as in Nova): 0 problems.
- The contract suite at `e401024`: 36 steps, all ok. The fixed point at `e401024` on macOS in both forms
  (`bootstrap/fixed-point/2026-10-31-spec-*`). Details in `ROADMAP.md` §10.
- The documentation site (`site/`, VitePress): `pnpm run build` passes its dead-link check over the copies of
  `spec/` and `guide/`.

## Not done

- `lib/` and `runtime/` are still generated from Nova `v0.6.0` (`tools/gen_library.py`, `tools/gen_runtime.py`); the
  specification names them by those paths. Moving their sources into CeeSafe's repository is a separate step.
- No site: the guide and the specification are read in the repository and through `ceesafec` (`explain`, MCP).
- The milestone tags and the history inside `ownership.md`, `memory-model.md`, `language-spec.md` and `type-system.md`
  are Nova's, kept as they are (`spec/README.md` §4).
