#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { unsigned char *p; size_t len, cap; } Buf;

static void push(Buf *b, unsigned char c) {
    if (b->len == b->cap) {
        b->cap = b->cap ? b->cap * 2 : 64;
        b->p = realloc(b->p, b->cap);
        if (!b->p) exit(1);
    }
    b->p[b->len++] = c;
}

static void number(Buf *b, uint64_t v) {
    unsigned char digits[20];
    int n = 0;
    do { digits[n++] = (unsigned char)('0' + v % 10); v /= 10; } while (v);
    while (n) push(b, digits[--n]);
}

int main(void) {
    Buf b = { 0 };
    for (uint64_t i = 0; i < 2000000; i++) {
        push(&b, 'k');
        number(&b, i);
        push(&b, '=');
        number(&b, 7 * i % 100000);
        push(&b, '\n');
    }
    uint64_t sum = 0;
    for (int pass = 0; pass < 8; pass++) {
        size_t i = 0;
        while (i < b.len) {
            while (b.p[i] != '=') i++;
            i++;
            uint64_t v = 0;
            while (b.p[i] != '\n') { v = v * 10 + (b.p[i] - '0'); i++; }
            i++;
            sum += v;
        }
    }
    free(b.p);
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
