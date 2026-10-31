/* C types that ffi/exported-c-state.cee holds in its exported structs (ADR 0029). */
#ifndef EXPORTED_C_STATE_TYPES_H
#define EXPORTED_C_STATE_TYPES_H

#include <stdbool.h>
#include <stdint.h>

/* A list head: once initialised it points to itself, so it must never move. */
struct xs_list {
    struct xs_list *next, *prev;
};

/* A "lock" whose init marks it. */
typedef struct {
    uint32_t locked;
    uint32_t magic;
} xs_lock_t;

void xs_lock_init(xs_lock_t *l);
void xs_list_init(struct xs_list *l);
bool xs_list_valid(const struct xs_list *l);

#endif
