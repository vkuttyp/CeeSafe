# Decision 0003 — Nova and CeeSafe in parallel; no Nova packages

- Status: **Accepted** by the owner, 2026-10-30 ("Go with your recommendation: option 1, track Nova until P8").
- Supersedes: Decision 0002 §1 (the legacy mode). Decision 0002 §2–§4 stand.

## Context

Decision 0002 kept Nova's names as a legacy mode so that CosmoOS could migrate from novac to ceesafec. The owner now
intends Nova and CeeSafe to exist in parallel, each a language with its own command-line compiler: CosmoOS need not
migrate, and CeeSafe need not read Nova's packages.

## Decisions

1. **CeeSafe does not read Nova packages.** Package mode finds only `ceesafe.toml`; its sources are `*.cee` and its lock
   `ceesafe.lock`. A directory (or a path dependency) holding only `nova.toml` is reported as a Nova package that
   CeeSafe does not read.
2. **Files named on the command line are still read whatever their extension** (`.c` files go to the C compiler). This
   is not a Nova mode: it keeps Nova's corpus, which is CeeSafe's reference, usable as it is by every comparison tool.
   Whether ceesafec later accepts only `.cee` files is P8's to decide, with the command line.
3. **CeeSafe tracks Nova until P8.** Until CeeSafe's tools reach parity (P8), the two are one language with two
   implementations: CeeSafe follows Nova's specifications, re-pins novac releases and keeps Nova's corpus as its
   reference, and gaps still go upstream (the N track). At P8's gate the owner decides the fork point; from then on
   CeeSafe has its own specifications and corpus, and the comparisons with novac become regression tests against the
   fork point's output.
4. **Package tests** rename Nova's package fixtures to CeeSafe's names and map the names back
   (`tools/compare_packages.py`), so ceesafec's output is still compared with novac's.
5. **CosmoOS** stays on Nova and novac. ROADMAP P9's migration item is optional and is the owner's to take up.
