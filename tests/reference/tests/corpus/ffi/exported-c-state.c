/* The C half of ffi/exported-c-state.cee: embeds CeeSafe's xs_table by value and uses it through the exports. */
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include "ceesafe_exports.h"

#define XS_MAGIC 0x10c4u

void xs_lock_init(xs_lock_t *l) {
    l->locked = 0;
    l->magic = XS_MAGIC;
}

void xs_list_init(struct xs_list *l) {
    l->next = l;
    l->prev = l;
}

bool xs_list_valid(const struct xs_list *l) {
    return l->next == l && l->prev == l;
}

/* A C object that embeds the CeeSafe-defined table, as CosmoOS's struct process embeds its handle table. */
struct xs_proc {
    int pid;
    struct xs_table handles;
    int tail;
};

int32_t c_main(void);

static struct xs_table table_static;
static int objects[8];

static int ok(const struct xs_table *t) {
    return t->lock.magic == XS_MAGIC && xs_list_valid(&t->head);
}

int32_t c_main(void) {
    xs_table_init(&table_static, 3);
    int a = xs_install(&table_static, &objects[0], 1);
    int b = xs_install(&table_static, &objects[1], 2);
    int c = xs_install(&table_static, &objects[2], 4);
    int d = xs_install(&table_static, &objects[3], 8);
    printf("static %d %d %d %d %u %u %d\n", a, b, c, d, table_static.count, table_static.entries[1].rights + table_static.entries[2].rights + 1,
           ok(&table_static));

    struct xs_proc p;
    memset(&p, 0xAB, sizeof p);
    p.pid = 1;
    p.tail = 2;
    xs_table_init(&p.handles, 4);
    p.handles.limit = 1; /* C writes a field of the CeeSafe-defined struct */
    int e = xs_install(&p.handles, &objects[4], 1);
    int f = xs_install(&p.handles, &objects[5], 1);
    printf("embedded %d %d %d %d %d\n", e, f, p.pid, p.tail, ok(&p.handles));

    struct xs_table s;
    xs_table_init(&s, 4);
    int r[5];
    for (int i = 0; i < 5; i++) {
        r[i] = xs_install(&s, &objects[i], 1);
    }
    printf("stack %d %d %d %d %d %d\n", r[0], r[1], r[2], r[3], r[4], ok(&s) && s.entries[3].obj == &objects[3]);

    size_t off[4];
    xs_offsets(off);
    printf("offsets %d %d %d %d\n", off[0] == offsetof(struct xs_entry, rights), off[1] == offsetof(struct xs_table, entries),
           off[2] == offsetof(struct xs_list, prev), off[3] == offsetof(struct xs_table, count));
    return 0;
}
