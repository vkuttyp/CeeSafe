# P8 plan: CLI, packages and tools

Status: **in progress** (started 2026-10-31; pinned to novac 0.6.0).

P8 ports the rest of novac: every command `ceesafec` does not yet have, the package manager and the tools, then
makes the fork point (Decision 0003 §3) with the C prefix switch (Decision 0004). The reference is still novac 0.6.0
(`bootstrap/reference.md`); its C# is 8,863 lines in the P8 files of `docs/reference-inventory.md` §1, plus
`Program.cs`'s commands.

| Part | Reference | Commands and options |
|---|---|---|
| Embedded docs, explain, fixes | `Documentation/EmbeddedDocs.cs` (80), `Tooling/Fixer.cs` (51), `Program.cs` | `explain`, `fix [--dry-run]` |
| Doc generator | `Documentation/DocGenerator.cs` (337) | `doc [-o] [--title] [--missing]` |
| Formatter | `Formatting/Formatter.cs` (1,220) | `fmt [--check] [--stdout]` |
| Packages | `Packages/` (1,874: Toml, Manifest, Versions, Workspace, Registry, Publishing, AgentFiles) | `new`, `agents`, `fetch [--offline] [--update]`, `publish`, `index-check`; package mode for every command |
| Interpreter | `Interpreter/` (3,856) | `run --interp`, the sandbox |
| Editor protocols | `Tooling/SemanticIndex.cs` (297), `LanguageServer.cs` (476), `McpServer.cs` (824), `DiagnosticJson.cs` (102, done in P2) | `lsp`, `mcp` |
| Host parity | `editors/debug`, `editors/vscode`, `Backend.C/CCompilers.cs`'s MSVC path | — |

## How it is compared

What novac prints, ceesafec prints, byte for byte, but where the rename contract (ROADMAP §3.4) says otherwise:
`ceesafec` for `novac`, `ceesafe.toml`/`ceesafe.lock`/`.cee`/`$CEESAFE_HOME` for Nova's names, `ceesafe_*` MCP tools,
CeeSafe agent-file markers. ceesafec's output has CeeSafe's names mapped back (`tools/names.py`, one short table) before it is
compared.

- **explain, doc, fmt:** over every corpus file, `lib/`, the programs and benchmarks, and CeeSafe's own sources.
- **fix:** the reference's `FixTests`: every fix the corpus offers, applied, gives novac's files; `--dry-run` output identical.
- **Packages:** the reference's `PackageManagerTests` and `AgentFilesTests` as fixtures with local git repositories
  and a local index, no network; the files written (`ceesafe.lock`, `AGENTS.md`, …) compared after the mapping.
- **Interpreter:** run-pass and run-fail under `run --interp`, stdout, stderr and exit status identical to novac's
  interpreter; the deterministic thread schedule identical. Never on benchmark-sized programs (they need tens of GB).
- **LSP and MCP:** recorded request transcripts (the reference's `LspTests`, `McpTests`), responses identical after the
  mapping.

## Slices

| Slice | Content | Gate |
|---|---|---|
| **S0** | The CLI shell: novac's usage text and option errors; `explain` over the embedded documents (`tools/gen_docs.py`: Nova's `docs/`, the guide and the agent template); `fix` and `--dry-run` | `explain` identical for every code; every corpus fix applied identical; `--dry-run` identical |
| **S1** | `fmt`: the formatter, `--check`, `--stdout`; CeeSafe's sources formatted by ceesafec | identical over the corpus, `lib/`, programs and benchmarks; idempotent; `novac fmt` dropped from CeeSafe's workflow |
| **S2** | `doc`: the doc generator (signatures cut from the formatter's output, so after S1), `-o`, `--title`, `--missing` | `docs/api/core.md` regenerated identical; every corpus file's page identical |
| **S3** | Packages: TOML, manifests, version solving, git dependencies and `$CEESAFE_HOME`'s cache, the lock file, the registry index, `new`, `agents` (CeeSafe templates and markers), `fetch`, `publish`, `index-check` | the package fixtures; files written identical after the mapping |
| **S4** | The interpreter: values, memory, numerics, builtins, host I/O, deterministic threads, the sandbox; `run --interp` | run-pass and run-fail identical to novac's interpreter; threads' traces identical |
| **S5** | `lsp` (the semantic index without reflection) and `mcp` (tools, resources, prompts, the sandbox) | the transcripts identical after the mapping |
| **S6** | Host parity: the MSVC path on the Windows VM, the debugger scripts, the VS Code extension under CeeSafe names; the self-build through package mode, P6's fixed point rerun through it; Decision 0003 §2's question (only `.cee` on the command line) | ceesafec built by MSVC emits the same C; fixed point through package mode on both hosts |
| **S7** | The fork point, when the owner names it: the C prefix and ABI version (Decision 0004), the link-collision test, the regression baseline of novac's output at the fork | the P8 gate (`ROADMAP.md` §P8) |

Slices S0–S6 keep ceesafec's C byte-identical to novac's, so every P5–P7 gate keeps running unchanged.

## Names (S3)

The rename contract (ROADMAP §3.4) applied to the package commands: `ceesafe.toml`, `ceesafe.lock`, `.cee`,
`$CEESAFE_HOME` (default `~/.ceesafe`), `$CEESAFE_INDEX`; the agent section between `<!--CEESAFE START-->` and
`<!--CEESAFE END-->`, `.cursor/rules/ceesafe.mdc`, and the MCP server `ceesafe` (`ceesafec mcp`) with tools
`ceesafe_*` in the agent template and configurations. Prose keeps "Nova" until the fork point (S7), and the default
index is CeeSafe's own, `github.com/vkuttyp/CeeSafe-index` (owner, 2026-10-31): a Nova index's packages are Nova
packages, which ceesafec does not read (Decision 0003).

## Upstream gaps (lib/std at v0.6.0)

- No way to set a child process's environment: git runs as `env GIT_TERMINAL_PROMPT=0 git …` (POSIX).
- No rename: a finished git checkout is moved into place by `mv` (POSIX).

Both are host-service items for Nova's N track (type-system.md §26); Windows needs them before S6's host parity.

## Known differences

- A file that cannot be read: novac's message is .NET's exception text, which names the absolute path
  ("Could not find file '/…'"); ceesafec's is the C library's. Neither the comparison tools nor the reference's tests
  depend on it.

## Execution record

| Date | Slice | Work | Result |
|---|---|---|---|
| 2026-10-31 | S0 | novac's usage text under CeeSafe's names, and usage errors that print it (`Program.Fail`); `--diagnostics-format` taken out before any other option, as `Program.Run` does; `explain` over the embedded documents (`tools/gen_docs.py` → `src/library/documents.cee`: Nova's `docs/`, the guide and the agent template at `v0.6.0`, 99 documents; `src/tooling/explain.cee`); `fix` and `fix --dry-run` (`src/tooling/fixes.cee`: Fixer's overlap rule, eight rounds, only the inputs edited); `tools/names.py` (the mapping back), `tools/compare_cli.py` | usage and usage errors 17/17 identical; `explain` 1,009/1,009 (every code N0000–N0999, lower case, malformed); `fix`, `fix --dry-run` and `fix --diagnostics-format=json --dry-run` over the 165 check-fail and parse-fail programs and the 16 FixTests programs: 180/180 identical, the files they leave too |
| 2026-10-31 | S1 | the formatter (`src/formatting/formatter.cee`: containers, continuations, glue, the line-breaking loop, trailing-comment alignment, widths in UTF-16 units; `fmt_command.cee`: the §6 self-check, `--check`, `--stdout`, package mode); CeeSafe's sources formatted by `out/ceesafec fmt`, and the generators format with it; `tools/compare_fmt.py` | `fmt --stdout` (text and JSON diagnostics) identical over the 545 `.nova` files of Nova `v0.6.0` and CeeSafe's 85 sources; idempotent on all; the 211 corpus files without inline comments squashed onto one line identical (the line breaker); `fmt --check` and in-place `fmt` over 45 copied files identical; ceesafec formats its own sources in 0.3 s (novac 0.7 s) |
| 2026-10-31 | S2 | the doc generator (`src/documentation/doc_generator.cee`: entries from the syntax, signatures cut from the formatted text, doc comments, `impl` lists, GitHub anchors, `--missing`, `-o`, `--title`, package mode); `tools/compare_doc.py` | `doc`, `doc --missing` and `doc -o … --title` identical for each of the 545 `.nova` files, lib/core, lib/std and lib/kernel as pages, and CeeSafe's sources as one page (549/549); lib/core's page equals Nova's `docs/api/core.md` |
| 2026-10-31 | S0–S2 | the contract suite with the `cli`, `fmt` and `doc` steps (`tools/contract_tests.py`) | every step ok on macOS (Apple clang 21): the P2–P7 steps unchanged (C 284/284 ×4 and 308/308 ×4, reports 308/308 ×4, CeeSafe's own C identical, 431,331 lines; 501,249 with `--split -g`), packages 7/7, cli, fmt, doc, run corpus under `-Werror` and ASan+UBSan, mutations, fault sweep 783 points, collections 30/30, freestanding |
| 2026-10-31 | S3 | packages (`src/packages/`): the TOML subset, versions and requirements, manifests, the workspace (path, git and registry dependencies, the lock, SHA-256 package hashes in `src/support/sha256.cee`, the git cache in `$CEESAFE_HOME/git`), the index and the backtracking version solver, `publish` and `index-check`, agent files; the commands `fetch`, `publish`, `index-check`, `new`, `agents`; package mode for `parse` too, and `check`/`build`/`fmt`/`doc`/`fix` through the new resolver; `tools/compare_package_commands.py` | 8 scenarios after PackageManagerTests and AgentFilesTests (31 bad manifests; path dependencies, lock out of date, conflicts, shared and cyclic graphs, missing and executable dependencies; git by tag, branch and rev, unknown tag, offline with an empty cache, a changed checkout; a local index with three versions, dependencies, `--update`, conflicts, a missing and an invalid entry, `index-check`; `publish` refusals and a published entry; agent files written, refreshed and left; `new`), each built with Nova's and CeeSafe's names: 382/382 runs identical after the mapping, the lock and agent files too; ceesafec's git package hashes equal the script's SHA-256 |
| 2026-10-31 | S3 | the contract suite with the `package cmds` step | all 30 steps ok on macOS (Apple clang 21); CeeSafe's own C identical (461,390 lines; 538,065 with `--split -g`) |
