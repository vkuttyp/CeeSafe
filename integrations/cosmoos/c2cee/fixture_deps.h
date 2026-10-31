/* What the self-test port calls: one of each kind c2cee.py tells apart. */
#ifndef FIXTURE_DEPS_H
#define FIXTURE_DEPS_H

#include <stdint.h>

void fx_plain(int x);
void fx_panic(const char *fmt, ...);

static inline int fx_inline(int x)
{
    return x + 1;
}

/* A function in a debug build and a static inline no-op in a release one, as lockdep's hooks are. */
#if CONFIG_DEBUG
void fx_hook(uintptr_t ip);
#else
static inline void fx_hook(uintptr_t ip)
{
    (void)ip;
}
#endif

struct fx_entry {
    struct fx_entry *next;
    union {   /* an anonymous member: no name in the AST */
        uint32_t word;
        uint8_t bytes[4];
    };
};

#define KASSERT(c)              \
    do {                        \
        if (!(c))               \
            fx_panic("%s", #c); \
    } while (0)

#define EXPORT_SYMBOL(sym) extern int fx_exported_##sym

#endif
