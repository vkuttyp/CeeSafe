#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { LIMIT = 40000000, M = 320 };

int main(void) {
    uint8_t *composite = calloc(LIMIT + 1, 1);
    if (!composite) return 1;
    uint64_t primes = 0;
    for (uint64_t i = 2; i <= LIMIT; i++) {
        if (composite[i]) continue;
        primes++;
        for (uint64_t j = i * i; j <= LIMIT; j += i) composite[j] = 1;
    }
    free(composite);
    static uint64_t a[M][M], b[M][M];
    for (uint64_t i = 0; i < M; i++)
        for (uint64_t j = 0; j < M; j++) { a[i][j] = i * j % 100; b[i][j] = (i + j) % 100; }
    uint64_t product = 0;
    for (uint64_t i = 0; i < M; i++)
        for (uint64_t j = 0; j < M; j++) {
            uint64_t c = 0;
            for (uint64_t k = 0; k < M; k++) c += a[i][k] * b[k][j];
            product += c;
        }
    printf("%llu\n", (unsigned long long)(primes * 1000000 + product % 1000000));
    return 0;
}
