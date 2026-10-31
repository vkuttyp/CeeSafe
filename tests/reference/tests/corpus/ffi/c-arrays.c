/* The C half of ffi/c-arrays.cee: owns the parts and the table that CeeSafe sees through c-arrays.types.h. */
#include <stdio.h>
#include <string.h>

#include "ceesafe_exports.h"

int32_t c_main(void);

int32_t c_main(void) {
    struct ca_part src[5];
    memset(src, 0, sizeof src);
    for (unsigned i = 0; i < 5; i++) {
        src[i].index = i + 1;
        src[i].first = 100 * i;
        memset(src[i].type, (int)i + 3, 16);
        memset(src[i].uuid, 0x10 + (int)i, 16);
        src[i].attrs = 1;
    }
    memset(src[3].uuid, 0x11, 16); /* the same as part 1's */
    struct ca_table t;
    memset(&t, 0xEE, sizeof t);
    unsigned sum = ca_fill(&t, src, 5);
    printf("%u %u %u %u\n", sum, t.nparts, t.guid[0], t.guid[15]);
    printf("%llu %u %u %u %llu\n", (unsigned long long)t.parts[3].first, t.parts[3].index, t.parts[2].type[5], t.parts[1].uuid[15],
           (unsigned long long)(t.parts[2].attrs & 0xFF) /* untouched: 0xEE */ - 0x8B);
    printf("%d %d\n", ca_same_uuid(&t, 0, 1), ca_same_uuid(&t, 1, 3));
    char hex[3] = { 0 };
    ca_guid_hex(&t, (uint8_t *)hex);
    printf("%s %.8s %u %u\n", hex, (const char *)ca_signature, ca_zeros[2], ca_limit);
    return 0;
}
