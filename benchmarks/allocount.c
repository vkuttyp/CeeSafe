/* Counts a program's heap allocations, for run.py. Loaded into the benchmark (DYLD_INSERT_LIBRARIES on macOS,
 * LD_PRELOAD on Linux), it counts every malloc, calloc, realloc, posix_memalign and aligned_alloc call, the bytes they
 * asked for, and the peak of live usable bytes, and at exit writes one line to the file named by NVBENCH_ALLOC_OUT:
 *   allocations <count> bytes <requested> peak <live usable bytes>
 * The counts include what the C library and the language runtime allocate before main; run.py reports them as they
 * are. Every language's allocations go through these functions here, except Goose's data stacks, which are mmap'd. */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static _Atomic uint64_t count, requested, live, peak;

#if defined(__APPLE__)
#include <malloc/malloc.h>
#define REAL(f) f
#define USABLE(p) malloc_size(p)
#else
#include <malloc.h>
extern void *__libc_malloc(size_t);
extern void *__libc_calloc(size_t, size_t);
extern void *__libc_realloc(void *, size_t);
extern void *__libc_memalign(size_t, size_t);
extern void __libc_free(void *);
#define REAL(f) __libc_##f
#define USABLE(p) malloc_usable_size(p)
#endif

static void grew(size_t asked, void *p) {
    if (p == NULL) return;
    atomic_fetch_add_explicit(&count, 1, memory_order_relaxed);
    atomic_fetch_add_explicit(&requested, asked, memory_order_relaxed);
    uint64_t now = atomic_fetch_add_explicit(&live, USABLE(p), memory_order_relaxed) + USABLE(p);
    uint64_t was = atomic_load_explicit(&peak, memory_order_relaxed);
    while (now > was && !atomic_compare_exchange_weak_explicit(&peak, &was, now, memory_order_relaxed,
                                                                memory_order_relaxed)) {
    }
}

static void shrank(void *p) {
    if (p != NULL) atomic_fetch_sub_explicit(&live, USABLE(p), memory_order_relaxed);
}

static void *count_malloc(size_t n) {
    void *p = REAL(malloc)(n);
    grew(n, p);
    return p;
}

static void *count_calloc(size_t k, size_t n) {
    void *p = REAL(calloc)(k, n);
    grew(k * n, p);
    return p;
}

static void *count_realloc(void *old, size_t n) {
    shrank(old);
    void *p = REAL(realloc)(old, n);
    if (p == NULL && old != NULL && n != 0) {
        atomic_fetch_add_explicit(&live, USABLE(old), memory_order_relaxed);  /* the old block is still live */
        return NULL;
    }
    grew(n, p);
    return p;
}

static void count_free(void *p) {
    shrank(p);
    REAL(free)(p);
}

#if defined(__APPLE__)
static int count_posix_memalign(void **out, size_t align, size_t n) {
    int r = posix_memalign(out, align, n);
    if (r == 0) grew(n, *out);
    return r;
}

static void *count_aligned_alloc(size_t align, size_t n) {
    void *p = aligned_alloc(align, n);
    grew(n, p);
    return p;
}

#define INTERPOSE(mine, theirs)                                                                                       \
    __attribute__((used)) static const struct { const void *replacement, *replacee; } interpose_##theirs               \
        __attribute__((section("__DATA,__interpose"))) = {(const void *)(mine), (const void *)(theirs)}
INTERPOSE(count_malloc, malloc);
INTERPOSE(count_calloc, calloc);
INTERPOSE(count_realloc, realloc);
INTERPOSE(count_free, free);
INTERPOSE(count_posix_memalign, posix_memalign);
INTERPOSE(count_aligned_alloc, aligned_alloc);
#else
void *malloc(size_t n) { return count_malloc(n); }
void *calloc(size_t k, size_t n) { return count_calloc(k, n); }
void *realloc(void *p, size_t n) { return count_realloc(p, n); }
void free(void *p) { count_free(p); }

int posix_memalign(void **out, size_t align, size_t n) {
    void *p = __libc_memalign(align, n);
    if (p == NULL) return 12; /* ENOMEM */
    grew(n, p);
    *out = p;
    return 0;
}

void *aligned_alloc(size_t align, size_t n) {
    void *p = __libc_memalign(align, n);
    grew(n, p);
    return p;
}

void *memalign(size_t align, size_t n) { return aligned_alloc(align, n); }
#endif

static char *decimal(char *at, uint64_t v) {
    char digits[20];
    int n = 0;
    do {
        digits[n++] = (char)('0' + v % 10);
        v /= 10;
    } while (v != 0);
    while (n > 0) *at++ = digits[--n];
    return at;
}

static char *text(char *at, const char *s) {
    size_t n = strlen(s);
    memcpy(at, s, n);
    return at + n;
}

__attribute__((destructor)) static void report(void) {
    const char *path = getenv("NVBENCH_ALLOC_OUT");
    if (path == NULL) return;
    char line[128];
    char *at = text(line, "allocations ");
    at = decimal(at, atomic_load(&count));
    at = text(at, " bytes ");
    at = decimal(at, atomic_load(&requested));
    at = text(at, " peak ");
    at = decimal(at, atomic_load(&peak));
    *at++ = '\n';
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    ssize_t ignored = write(fd, line, (size_t)(at - line));
    (void)ignored;
    close(fd);
}
