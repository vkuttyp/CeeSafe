/*
 * host_shims.c - C8's host stand-ins for threads, timers and the module glue's log, recording the order of the
 * teardown calls so host_test.c can check it. The other kernel functions are C7's shims (c7/host_kernel.c), CosmoOS's
 * spinlock shim and harness, and its own kernel/object/object.c.
 *
 * Threads are not run concurrently on the host (the spinlock shim is single-threaded): thread_create records the
 * entry, and thread_join runs it. A KThread is told to stop before it is joined, so its body returns at once, which
 * is what the teardown order needs.
 */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include <kernel/panic.h>
#include <kernel/thread.h>
#include <kernel/timer.h>

void thread_sleep_ns(uint64_t ns);
void c8_log(const char *event, uint64_t value);
void c8_host_fire_timers(void);
unsigned c8_host_armed(void);
unsigned c8_host_threads(void);
const char *c8_host_trace(void);
void c8_host_reset(void);

enum { MAX_TIMERS = 8, MAX_THREADS = 8 };
static struct timer *g_timers[MAX_TIMERS];
static unsigned g_ntimers;
static struct {
    void (*entry)(void *);
    void *arg;
    bool live;
} g_threads[MAX_THREADS];
static char g_trace[256];

static void trace(const char *what)
{
    if (strlen(g_trace) + strlen(what) + 2 < sizeof(g_trace)) {
        strcat(g_trace, what);
        strcat(g_trace, " ");
    }
}

struct thread *thread_create(void (*entry)(void *arg), void *arg, const char *name, int priority)
{
    (void)name;
    (void)priority;
    for (unsigned i = 0; i < MAX_THREADS; i++) {
        if (!g_threads[i].live) {
            g_threads[i].entry = entry;
            g_threads[i].arg = arg;
            g_threads[i].live = true;
            trace("thread_create");
            return (struct thread *)&g_threads[i];
        }
    }
    return NULL;
}

int thread_join(struct thread *t)
{
    unsigned i = (unsigned)(((char *)t - (char *)g_threads) / sizeof(g_threads[0]));
    if (i >= MAX_THREADS || !g_threads[i].live)
        panic("host thread_join: not a live thread");
    trace("thread_join");
    g_threads[i].entry(g_threads[i].arg); /* told to stop already: returns at once */
    g_threads[i].live = false;
    return 0;
}

void thread_sleep_ns(uint64_t ns)
{
    (void)ns;
}

void timer_setup(struct timer *t, timer_fn fn, void *arg)
{
    memset(t, 0, sizeof(*t));
    t->fn = fn;
    t->arg = arg;
    t->state = TIMER_IDLE;
}

void timer_start(struct timer *t, uint64_t delay_ns)
{
    t->expires_ns = delay_ns;
    if (t->state != TIMER_PENDING) {
        if (g_ntimers == MAX_TIMERS)
            panic("host timer_start: too many timers");
        g_timers[g_ntimers++] = t;
        t->state = TIMER_PENDING;
    }
}

bool timer_cancel_sync(struct timer *t)
{
    trace("timer_cancel_sync");
    for (unsigned i = 0; i < g_ntimers; i++) {
        if (g_timers[i] == t) {
            g_timers[i] = g_timers[--g_ntimers];
            t->state = TIMER_IDLE;
            return true;
        }
    }
    return false;
}

/* Every armed timer fires once (in "interrupt context"), oldest first; a callback may re-arm its timer. */
void c8_host_fire_timers(void)
{
    struct timer *due[MAX_TIMERS];
    unsigned n = g_ntimers;
    memcpy(due, g_timers, n * sizeof(due[0]));
    g_ntimers = 0;
    for (unsigned i = 0; i < n; i++) {
        due[i]->state = TIMER_IDLE;
        due[i]->fn(due[i], due[i]->arg);
    }
}

unsigned c8_host_armed(void)
{
    return g_ntimers;
}

unsigned c8_host_threads(void)
{
    unsigned live = 0;
    for (unsigned i = 0; i < MAX_THREADS; i++)
        live += g_threads[i].live;
    return live;
}

void c8_log(const char *event, uint64_t value)
{
    (void)value;
    if (strncmp(event, "shutdown: ticks", 15) == 0)
        trace("shutdown");
}

const char *c8_host_trace(void)
{
    return g_trace;
}

void c8_host_reset(void)
{
    g_trace[0] = '\0';
}

/* The generated glue's leak switch (c8.py): off on the host. */
bool c8_leak_requested(void);

bool c8_leak_requested(void)
{
    return false;
}
