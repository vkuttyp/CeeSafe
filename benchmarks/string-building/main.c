#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { char *p; size_t len, cap; } Str;

static void push(Str *s, char c) {
    if (s->len == s->cap) {
        s->cap = s->cap ? s->cap * 2 : 8;
        s->p = realloc(s->p, s->cap);
        if (!s->p) exit(1);
    }
    s->p[s->len++] = c;
}

int main(void) {
    uint64_t total = 0;
    for (uint64_t round = 0; round < 30; round++) {
        Str s = { 0 };
        for (uint64_t i = 0; i < 1000000; i++) {
            char digits[20];
            int n = 0;
            uint64_t v = i + round;
            do { digits[n++] = (char)('0' + v % 10); v /= 10; } while (v);
            while (n) push(&s, digits[--n]);
            push(&s, ',');
        }
        uint64_t bytes = 0;
        for (size_t i = 0; i < s.len; i++) bytes += (unsigned char)s.p[i];
        total += s.len * 1000 + bytes % 1000;
        free(s.p);
    }
    printf("%llu\n", (unsigned long long)total);
    return 0;
}
