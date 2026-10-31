#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum { N = 1000000, STEPS = 100, W = 1000 };

static void move(int32_t *p, int32_t *v) {
    *p += *v;
    if (*p < 0) { *p = -*p; *v = -*v; }
    else if (*p >= W) { *p = 2 * (W - 1) - *p; *v = -*v; }
}

int main(void) {
    int32_t *x = malloc(N * 4), *y = malloc(N * 4), *vx = malloc(N * 4), *vy = malloc(N * 4);
    if (!x || !y || !vx || !vy) return 1;
    for (int32_t i = 0; i < N; i++) { x[i] = i % 1000; y[i] = 3 * i % 1000; vx[i] = i % 7 - 3; vy[i] = i % 5 - 2; }
    for (int s = 0; s < STEPS; s++)
        for (int i = 0; i < N; i++) { move(&x[i], &vx[i]); move(&y[i], &vy[i]); }
    uint64_t sum = 0;
    for (int i = 0; i < N; i++) sum += (uint64_t)(x[i] + y[i]);
    free(x); free(y); free(vx); free(vy);
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
