/* The C half of ffi/includes-exports.cee. */
#include <stdio.h>

#include "includes-exports.types.h"

int32_t c_main(void);

#if defined(_MSC_VER)
#define IE_NOINLINE __declspec(noinline)
#else
#define IE_NOINLINE __attribute__((noinline))
#endif

static volatile unsigned g_sink;

/* Each calls ie_where at its own site, and does more after it, so the call is not a tail call. */
static IE_NOINLINE size_t caller_a(void) {
    size_t r = ie_where();
    g_sink++;
    return r;
}

static IE_NOINLINE size_t caller_b(void) {
    g_sink++;
    size_t r = ie_where();
    g_sink += 2;
    return r;
}

/* An address inside `f`'s code: past its start, and well within a small function. */
static int inside(size_t address, uintptr_t f) {
    return address > f && address - f < 512;
}

uint32_t ie_sum(const struct ie_box *b) {
    return b->lock.taken + b->values[0] + b->values[1] + b->values[2];
}

int32_t c_main(void) {
    struct ie_box box;
    ie_fill(&box, 10);
    printf("%u %u\n", ie_sum(&box), ie_total(&box));
    size_t a = caller_a(), b = caller_b();
    printf("callers %d %d %d\n", inside(a, (uintptr_t)caller_a), inside(b, (uintptr_t)caller_b), a != b);
    return 0;
}
