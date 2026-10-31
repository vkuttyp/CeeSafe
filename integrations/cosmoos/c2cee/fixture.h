/* The types c2cee.py's self-test port takes over (spec/tooling.md §9.3). */
#ifndef FIXTURE_H
#define FIXTURE_H

#include <stdbool.h>
#include <stdint.h>

struct fx_lock {
    uint32_t taken;
};

typedef void (*fx_callback)(int);

struct fx_thing {
    struct fx_lock lock;       /* C state, by value */
    const char *name;          /* a const pointer */
    uint16_t class;            /* a CeeSafe keyword */
    bool done;                 /* used atomically */
    uint64_t count;            /* used atomically */
    fx_callback fn;            /* a CeeSafe keyword, called through */
    uint8_t bytes[4];
};

#define FX_THING_INIT(n) { .lock = { 0 }, .name = (n), .class = 0, .done = false, .count = 0, .fn = 0 }

void fx_thing_init(struct fx_thing *t, const char *name);
uint64_t fx_thing_count(struct fx_thing *t);

#endif
