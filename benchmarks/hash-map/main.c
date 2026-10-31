#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { BITS = 22, N = 2000000 };
#define MASK ((1ull << BITS) - 1)

static uint64_t slot_of(uint64_t key) { return (key * 2654435761ull >> 10) & MASK; }

int main(void) {
    uint64_t *keys = calloc(1ull << BITS, sizeof *keys), *values = calloc(1ull << BITS, sizeof *values);
    if (!keys || !values) return 1;
    for (uint64_t i = 0; i < N; i++) {
        uint64_t key = 7 * i + 1, s = slot_of(key);
        while (keys[s] != 0 && keys[s] != key) s = (s + 1) & MASK;
        keys[s] = key;
        values[s] = i;
    }
    uint64_t sum = 0, misses = 0;
    for (int round = 0; round < 8; round++)
        for (uint64_t i = 0; i < N; i++) {
            for (int kind = 0; kind < 2; kind++) {
                uint64_t key = kind == 0 ? 7 * i + 1 : 7 * i + 3, s = slot_of(key);
                while (keys[s] != 0 && keys[s] != key) s = (s + 1) & MASK;
                if (keys[s] == key) sum += values[s];
                else misses++;
            }
        }
    free(keys);
    free(values);
    printf("%llu\n", (unsigned long long)(sum + misses));
    return 0;
}
