# Proposal for CosmoOS: a debug-build module load/unload cycle hook

Status: **merged into CosmoOS** as #457 (`118e47b7`, 2026-10-26: `kernel/module/modcycle.c`, CosmoOS roadmap 1.2 N1,
invariant M27), with the same interface. This page is the proposal as it was written (2026-10-25), when CosmoOS was
read-only from CeeSafe work and the change was for the CosmoOS owner to schedule as a CosmoOS unit, under CosmoOS's
`AGENTS.md`: its own branch, PR, docs and validation matrix. CeeSafe's
C8 (`docs/cosmoos/c8-report.md`) needs it for its acceptance criterion, ≥ 1000 load/unload cycles through CosmoOS's own
loader. The owner chose this approach over exporting the loader API.

## Why

`module_load` and `module_unload` (`kernel/include/kernel/module.h`) are called only by built-in code:
`module_load_boot`, once per boot, and the module selftests (`kernel/module/modtest.c`, `kernel/core/faulttest.c`),
on CosmoOS's own fixture `tests/cosmotest.ko`. Neither function is exported to modules, no syscall reaches them, and
no userland tool exists. So an out-of-tree module, CeeSafe's or anyone's, cannot be unloaded at all, and its `shutdown()`
never runs.

## What

`module-cycle.patch` (against CosmoOS `41368f9e`; four files):

- `kernel/module/modcycle.c` (new) defines `module_cycle_boot()`. With `module.cycle=<archive entry>:<count>` on the
  kernel command line, it loads and unloads that boot-archive entry `<count>` times through `module_load` and
  `module_unload`. It compares, after one warm-up cycle and at the end, `module_count()`, kmalloc's `live_objects`, the
  VM's `regions` and `anon_pages`, and lockdep's `classes`, which must be equal. Every load and every unload must
  return 0 (an unload of -EBUSY is a zombie). It logs one line:
  `modcycle: tests/ceesafe_c8.ko: 1000 cycles: PASS (load failures 0, unload failures 0, ...)`.
- It is compiled only into `CONFIG_DEBUG` builds; in release it is an empty function. That is CosmoOS's rule for test
  seams: it takes no lock when unarmed and does nothing without the parameter.
- `kernel/core/main.c` calls it right after `module_load_boot()`. `kernel/kernel.mk` adds the file, and
  `kernel/include/kernel/module.h` declares it.
- The loader API stays unexported.

## Validation so far (CeeSafe side)

`integrations/cosmoos/c8.py --cycles N` applies the patch to a **copy** of the CosmoOS tree (sources only, rsync
without `.git` and `out`), builds that copy's debug image, and boots it with the CeeSafe module as `tests/ceesafe_c8.ko`. The
results are in `docs/cosmoos/c8-report.md` (C8b). They show the hook works with a module that starts a thread and a
timer. The CosmoOS unit would add its own validation: the matrix in its `AGENTS.md`, a selftest or boot-test entry,
and docs (`docs/kernel/module/testing.md`, the backlog, history).
