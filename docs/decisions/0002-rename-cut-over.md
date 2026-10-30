# Decision 0002 — The rename cut-over: legacy names and diagnostic codes

- Status: **Accepted** by the owner, 2026-10-30. The owner chose to keep the legacy mode and left the code letter to
  the agent ("keep 'N' or replace it with 'C'"); the agent chose N, for the reasons below.
- Implements: ROADMAP P6R, Decision 0001 §2–§3.

## Decisions

1. **Nova's names stay as a legacy mode, for now.** CosmoOS's Nova sources (`kernel/**/*.nova`, built by its pinned
   novac) have yet to migrate (ROADMAP P9), and Nova's corpus is CeeSafe's reference.
   - A package's manifest is `ceesafe.toml`, or, in legacy mode, `nova.toml`. A directory with both is an error,
     so a package is never read two ways.
   - The manifest decides the rest: a `ceesafe.toml` package's sources are the `*.cee` files under its `sources`
     directories and its lock is `ceesafe.lock`; a `nova.toml` package's are `*.nova` and `nova.lock`. A dependency
     may be of either kind.
   - Files named on the command line are read whatever their extension (`.c` files go to the C compiler, as in Nova).
   - Messages about a legacy package keep novac's wording (`nova.toml`, `nova.lock`, `novac fetch`), so the package
     fixtures stay comparable with novac; a CeeSafe package's messages name `ceesafe.toml`, `ceesafe.lock` and
     `ceesafec fetch`.
   - `$CEESAFE_HOME` (default `~/.ceesafe`) is where fetched packages will live. Nothing reads a home directory yet:
     git and registry dependencies are P8's, which decides whether `$NOVA_HOME` is read too.
   - The legacy mode is removed by a later decision, after CosmoOS has migrated.
2. **Diagnostic codes keep the letter N** (`N0100`, …).
   - *C* would collide with MSVC's own diagnostic codes (`C1083`, `C4100`, …), which CeeSafe meets when it drives cl
     on Windows (P9) and which users already search for.
   - The codes are the language's, and the numbers would not change; keeping the letter keeps every corpus annotation,
     `explain` page and fix test valid, and the byte-for-byte comparisons with novac direct, with no mapping table.
   - A later change of letter needs only a mechanical mapping, since the numbers are stable.
3. **CeeSafe's own sources are renamed in one commit** (`src/**/*.nova` → `.cee`, `nova.toml` → `ceesafe.toml`).
   From then on novac cannot build CeeSafe directly. A fresh checkout bootstraps through the last legacy-named commit,
   recorded in `bootstrap/reference.md`: novac builds that commit, and the ceesafec it makes builds the current tree
   (`tools/bootstrap.sh`).
4. **Not renamed in P6R** (ROADMAP §3.4): the generated C's names and the runtime's (`nv_`, `nova_*`, `nova/rt.h`,
   `NOVA_PROGRAM_*_H`, `nova_exports.h`), the library files' paths (`lib/core/*.nova`, which messages show), the
   reference's diagnostic messages (the `@threadSafe` N0251 message names `nova.toml`), the `novac:` prefix of the command line's own
   messages (kept so that the runner's comparisons with novac stay byte-for-byte), MCP and editor names. The C and
   runtime names wait for P7, after parity; the command line's and the tools' for P8.
