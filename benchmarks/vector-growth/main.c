#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    uint64_t sum = 0;
    for (uint64_t round = 0; round < 10; round++) {
        uint64_t *v = NULL;
        size_t len = 0, cap = 0;
        for (uint64_t i = 0; i < 20000000; i++) {
            if (len == cap) {
                cap = cap ? cap * 2 : 4;
                v = realloc(v, cap * sizeof *v);
                if (!v) return 1;
            }
            v[len++] = (i + round) % 1000;
        }
        for (size_t i = 0; i < len; i++) sum += v[i];
        free(v);
    }
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
