/* A host-side environment for freestanding/demo.cee: it supplies ceesafe_panic and demo_log, and calls the exports. */
#include <stdio.h>
#include <stdlib.h>

#include "ceesafe/rt.h"
#include "ceesafe_exports.h"

void demo_log(uint64_t value);

void demo_log(uint64_t value) {
    printf("log %llu\n", (unsigned long long)value);
}

/* The environment's panic hook (profiles.md §4.2): report like the hosted runtime, then stop. */
_Noreturn void ceesafe_panic(cee_panic_kind kind, cee_loc loc) {
    fflush(stdout);
    fprintf(stderr, "ceesafe panic: %s at %s:%u:%u\n", kind == CEE_PANIC_OVERFLOW ? "integer overflow" : "other panic",
        loc.file, (unsigned)loc.line, (unsigned)loc.column);
    exit(134);
}

int main(void) {
    printf("fill %u\n", (unsigned)demo_fill(7));
    uint8_t bytes[4] = { 1, 2, 3, 4 };
    struct Stats s = demo_stats(bytes, 4);
    printf("stats %u %llu %u\n", (unsigned)s.count, (unsigned long long)s.sum, (unsigned)s.max);
    printf("find %d %d\n", (int)demo_find('e'), (int)demo_find('z'));
    printf("blocks %u %u\n", (unsigned)demo_blocks(3, 512), (unsigned)demo_blocks(3, 100));
    printf("add %u\n", (unsigned)demo_add(1, 2));
    fflush(stdout);
    printf("add %u\n", (unsigned)demo_add(UINT32_MAX, 1));
    return 0;
}
