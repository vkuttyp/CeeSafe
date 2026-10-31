/*
 * fixture_floor.c - DRAFT by c2cee (spec/tooling.md §9.4): the C under fixture.cee.
 *
 * What CeeSafe cannot express yet: the formatted messages of variadic calls, statics of C types, and the
 * module exports. Review it as C that stays.
 */

#include "fixture.h"
#include "fixture_cycle.h"
#include "fixture_deps.h"

_Static_assert(sizeof(struct fx_lock) == 4, "a file-scope assertion: it stays in the floor");

/* Declared for the CeeSafe port only. */
void fixture_floor_assert_1(void);
void fixture_floor_fence_5(void);
void fixture_floor_fx_panic_6(const char * a0);


void fixture_floor_assert_1(void)
{
    panic("assertion failed: %s at %s:%d (%s)", "name != 0", "fixture.c", 15, "fx_thing_init");
}

void fixture_floor_fence_5(void)
{
    __atomic_thread_fence(__ATOMIC_SEQ_CST);
}

void fixture_floor_fx_panic_6(const char * a0)
{
    fx_panic("done %s", a0);
}

/* Module exports (docs/kernel/module/api.md). */
EXPORT_SYMBOL(fx_thing_init);
