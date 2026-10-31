/* The C types ffi/c-arrays.cee imports (type-system.md §31, C9): array members, a member named by a CeeSafe
 * keyword, and an array of structs. */
#ifndef C_ARRAYS_TYPES_H
#define C_ARRAYS_TYPES_H

#include <stdint.h>

struct ca_part {
    uint32_t index;
    uint64_t first;
    uint8_t type[16];    /* `type` is a CeeSafe keyword: @cname */
    uint8_t uuid[16];
    uint64_t attrs;      /* not declared in CeeSafe: its writes must leave it alone */
};

struct ca_table {
    uint8_t guid[16];
    unsigned nparts;
    struct ca_part parts[4];
};

#endif
