#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { uint64_t a, b; } Pair;

int main(void) {
    enum { N = 32000000, RING = 1024 };
    Pair *ring[RING] = { 0 };
    uint64_t sum = 0;
    for (uint64_t i = 0; i < N; i++) {
        Pair *p = malloc(sizeof *p);
        if (!p) return 1;
        p->a = i;
        p->b = i % 7;
        Pair **slot = &ring[i % RING];
        if (*slot) { sum += (*slot)->a + (*slot)->b; free(*slot); }
        *slot = p;
    }
    for (int s = 0; s < RING; s++)
        if (ring[s]) { sum += ring[s]->a + ring[s]->b; free(ring[s]); }
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
