#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    uint64_t sum = 0;
    for (uint64_t i = 0; i < 10000000; i++) {
        uint64_t *a = malloc(32 * sizeof *a);
        if (!a) return 1;
        for (uint64_t j = 0; j < 32; j++) a[j] = (i + j) % 1000;
        for (uint64_t j = 0; j < 32; j++) sum += a[j];
        free(a);
    }
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
