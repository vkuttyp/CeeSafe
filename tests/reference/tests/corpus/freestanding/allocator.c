/* The environment for freestanding/allocator.cee: a bump allocator over a static buffer, with accounting. */
#include <stdio.h>
#include <stdlib.h>

#include "ceesafe/rt.h"
#include "ceesafe_exports.h"

void *env_alloc(size_t size, size_t align);
void env_free(void *p, size_t size);

static _Alignas(16) unsigned char arena[256];
static size_t used, live, allocations;
static int refuse;

void *env_alloc(size_t size, size_t align) {
    if (refuse) return NULL;
    size_t start = (used + align - 1) / align * align;
    if (start + size > sizeof arena) return NULL;
    used = start + size;
    live++;
    allocations++;
    return arena + start;
}

void env_free(void *p, size_t size) {
    (void)p;
    (void)size;
    live--;
}

_Noreturn void ceesafe_panic(cee_panic_kind kind, cee_loc loc) {
    fprintf(stderr, "ceesafe panic: %s at %s:%u:%u\n", ceesafe_panic_reason(kind), loc.file, (unsigned)loc.line, (unsigned)loc.column);
    exit(134);
}

int main(void) {
    unsigned long long r = alloc_demo(10);
    printf("demo %llu, live %zu, allocations %zu\n", r, live, allocations);
    refuse = 1;
    r = alloc_demo(10);
    printf("refused %llu, live %zu\n", r, live);
    return 0;
}
