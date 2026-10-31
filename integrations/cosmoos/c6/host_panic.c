/* ceesafe_panic for the host builds of C6 (CosmoOS's host test, fuzz target, differential test, benchmark): a CeeSafe
 * panic aborts with the hosted runtime's message (profiles.md §4.2). */
#include <stdio.h>
#include <stdlib.h>

#include "ceesafe/rt.h"

_Noreturn void ceesafe_panic(cee_panic_kind kind, cee_loc loc) {
    fprintf(stderr, "ceesafe panic: %s at %s:%u:%u\n", ceesafe_panic_reason(kind), loc.file, (unsigned)loc.line, (unsigned)loc.column);
    abort();
}
