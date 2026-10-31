/*
 * module.c - C7e's test module, ceesafe_c7: runs CeeSafe's concurrency stress (c7/stress.cee) from init, in CosmoOS's
 * debug build (lockdep on), and logs each result; built with -DC7_CONTROL=1 it runs the lock-order inversion control
 * instead, which lockdep must report. Built out of tree by integrations/cosmoos/c7.py with CosmoOS's own
 * MODULE_CFLAGS, joined and signed by its own tools; CosmoOS is not modified.
 */
#include <kernel/errno.h>
#include <kernel/log.h>
#include <kernel/module.h>
#include <kernel/percpu.h>

#include "ceesafe_exports.h"

#ifndef C7_CONTROL
#define C7_CONTROL 0
#endif

/* Threads and iterations of the stress: four workers on QEMU's four CPUs. */
#define C7_THREADS 4
#define C7_ITERATIONS 2000

void c7_report(const char *name, bool passed, int64_t detail);
void c7_racy_increment(void);
void c7_racy_burst(uint64_t n);
uint64_t c7_racy_value(void);
void c7_enter(void);
void c7_leave(void);
uint32_t c7_max_active(void);
uint32_t c7_cpus(void);

/* The control: a counter every worker increments with no lock. A plain read-modify-write with a pause between the
 * read and the write, so increments that overlap are lost; volatile keeps the compiler from merging them. */
static volatile uint64_t g_racy;

/* Evidence of concurrency, kept atomically: how many workers were inside their loops at once, at most, and on which
 * CPUs they ran. */
static uint32_t g_active, g_max_active;
static uint64_t g_cpu_mask;

void c7_report(const char *name, bool passed, int64_t detail)
{
    kinfo("ceesafe_c7: %s %s (%lld)", name, passed ? "PASS" : "FAIL", (long long)detail);
}

void c7_racy_increment(void)
{
    uint64_t value = g_racy;
    for (int i = 0; i < 64; i++)
        __asm__ volatile("" ::: "memory");
    g_racy = value + 1;
}

/* The control's own phase: `n` unlocked increments in a row, with nothing in between to keep workers apart. */
void c7_racy_burst(uint64_t n)
{
    for (uint64_t i = 0; i < n; i++)
        c7_racy_increment();
}

void c7_enter(void)
{
    uint32_t now = __atomic_add_fetch(&g_active, 1u, __ATOMIC_SEQ_CST);
    uint32_t seen = __atomic_load_n(&g_max_active, __ATOMIC_RELAXED);
    while (now > seen && !__atomic_compare_exchange_n(&g_max_active, &seen, now, false, __ATOMIC_RELAXED, __ATOMIC_RELAXED))
        ;
    __atomic_or_fetch(&g_cpu_mask, 1ull << (raw_cpu_id() & 63u), __ATOMIC_RELAXED);
}

void c7_leave(void)
{
    __atomic_or_fetch(&g_cpu_mask, 1ull << (raw_cpu_id() & 63u), __ATOMIC_RELAXED);
    __atomic_sub_fetch(&g_active, 1u, __ATOMIC_SEQ_CST);
}

uint32_t c7_max_active(void)
{
    return __atomic_load_n(&g_max_active, __ATOMIC_RELAXED);
}

uint32_t c7_cpus(void)
{
    return (uint32_t)__builtin_popcountll(__atomic_load_n(&g_cpu_mask, __ATOMIC_RELAXED));
}

uint64_t c7_racy_value(void)
{
    return g_racy;
}

static int c7_init(void)
{
    if (C7_CONTROL) {
        kinfo("ceesafe_c7: control: taking two spinlocks in both orders");
        uint32_t result = c7_inversion();
        kerror("ceesafe_c7: control: lockdep did not report the inversion (%u)", (unsigned)result);
        return -EINVAL;
    }
    kinfo("ceesafe_c7: stress: %d threads x %d iterations", C7_THREADS, C7_ITERATIONS);
    uint32_t failed = c7_stress(C7_THREADS, C7_ITERATIONS);
    if (failed != 0) {
        kerror("ceesafe_c7: %u check(s) failed", (unsigned)failed);
        return -EINVAL;
    }
    kinfo("ceesafe_c7: all checks passed");
    return 0;
}

static void c7_shutdown(void)
{
    kinfo("ceesafe_c7: shutdown");
}

COSMO_MODULE("ceesafe_c7", "1.0", c7_init, c7_shutdown, "", MODULE_CAP_NONE);
