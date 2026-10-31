# CeeSafe's reference corpus

Written by `tools/fork_corpus.py` from Nova v0.6.0 at the fork point (`docs/fork-point.md`): Nova's corpus, benchmarks,
programs and libraries as `.cee` files, with CeeSafe's names in the C harnesses; the snapshots stay Nova's, the frozen
baseline, and ceesafec's output is mapped back before it is compared with them. The comparison tools
run ceesafec here and novac in the Nova checkout. Do not edit by hand before the fork's first CeeSafe-only change.

Since Decision 0007 (CeeSafe's runtime; the first C that differs from novac's), the `emit-c` snapshots are CeeSafe's
own: an intended change of the C updates them by a reviewed edit, recorded in the decision. Changed so far:
`tests/corpus/emit-c/arena.c` (region helpers call `nova_region_alloc_fast`, i.e. `ceesafe_region_alloc_fast`).
