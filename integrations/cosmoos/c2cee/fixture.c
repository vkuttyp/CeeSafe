/* c2cee.py's self-test port (spec/tooling.md §9.3): one of each case of §9.1. */
#include "fixture.h"
#include "fixture_cycle.h"
#include "fixture_deps.h"

_Static_assert(sizeof(struct fx_lock) == 4, "a file-scope assertion: it stays in the floor");

static int helper(int x)
{
    return fx_inline(x);   /* the file's own function calls a header's inline one */
}

void fx_thing_init(struct fx_thing *t, const char *name)
{
    KASSERT(name != 0);
    t->name = name;
    t->class = 0;
    __atomic_store_n(&t->done, false, __ATOMIC_RELEASE);
    __atomic_store_n(&t->count, 0, __ATOMIC_RELAXED);
    fx_plain(helper(1));
    fx_hook((uintptr_t)__builtin_return_address(0));
    fx_cycle_note(t);
}

uint64_t fx_thing_count(struct fx_thing *t)
{
    struct fx_entry local;     /* a local of struct type */
    local.next = 0;
    if (t->fn)
        t->fn(1);              /* through a function pointer member */
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
    if (__atomic_load_n(&t->done, __ATOMIC_ACQUIRE))
        fx_panic("done %s", t->name);
    return __atomic_load_n(&t->count, __ATOMIC_ACQUIRE) + (local.next != 0);
}

EXPORT_SYMBOL(fx_thing_init);
