/*
 * CeeSafe's panic hook for CosmoOS kernel code (C4; spec/profiles.md §3.3 and §4.2): a CeeSafe panic
 * (overflow, bounds, unwrap, ...) is a kernel panic with CeeSafe's reason and source location. Compiled with
 * CosmoOS's own module flags; uses only `panic`, which the kernel exports (kernel/core/panic.c).
 */
#include <kernel/panic.h>

#include "ceesafe/rt.h"

_Noreturn void ceesafe_panic(cee_panic_kind kind, cee_loc loc) {
    panic("ceesafe panic: %s at %s:%u:%u", ceesafe_panic_reason(kind), loc.file, (unsigned)loc.line, (unsigned)loc.column);
}
