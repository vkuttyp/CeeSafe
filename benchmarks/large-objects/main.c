#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { N = 400000, RING = 8, SIZE = 65536 };

int main(void) {
    uint8_t *ring[RING] = { 0 };
    uint64_t sum = 0;
    for (uint64_t i = 0; i < N; i++) {
        uint8_t *b = malloc(SIZE);
        if (!b) return 1;
        memset(b, 0, SIZE);
        b[0] = (uint8_t)(i % 256);
        b[SIZE - 1] = (uint8_t)(3 * i % 256);
        uint8_t **slot = &ring[i % RING];
        if (*slot) { sum += (*slot)[0] + (*slot)[SIZE - 1]; free(*slot); }
        *slot = b;
    }
    for (int s = 0; s < RING; s++)
        if (ring[s]) { sum += ring[s][0] + ring[s][SIZE - 1]; free(ring[s]); }
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
