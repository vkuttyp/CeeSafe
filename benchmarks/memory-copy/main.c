#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { SIZE = 16 << 20, BLOCK = 4096, PASSES = 320 };

int main(void) {
    uint8_t *src = malloc(SIZE), *dst = malloc(SIZE);
    if (!src || !dst) return 1;
    for (size_t i = 0; i < SIZE; i++) src[i] = (uint8_t)(i % 251);
    uint64_t sum = 0;
    for (int pass = 0; pass < PASSES; pass++) {
        /* The blocks in a fixed permuted order (2053 is odd, so each block once), so that no compiler can merge them into one copy. */
        for (size_t i = 0; i < SIZE / BLOCK; i++) {
            size_t at = i * 2053 % (SIZE / BLOCK) * BLOCK;
            memcpy(dst + at, src + at, BLOCK);
        }
        for (size_t at = 0; at < SIZE; at += BLOCK) sum += dst[at];
    }
    free(src);
    free(dst);
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
