#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct Node { struct Node *left, *right; } Node;

static Node *make(int depth) {
    Node *n = malloc(sizeof *n);
    if (!n) exit(1);
    if (depth == 0) { n->left = n->right = NULL; }
    else { n->left = make(depth - 1); n->right = make(depth - 1); }
    return n;
}

static uint64_t check(const Node *n) { return n->left ? 1 + check(n->left) + check(n->right) : 1; }

static void release(Node *n) {
    if (n->left) { release(n->left); release(n->right); }
    free(n);
}

int main(void) {
    enum { MAX = 17, MIN = 4 };
    uint64_t total = 0;
    Node *stretch = make(MAX + 1);
    total += check(stretch);
    release(stretch);
    Node *lived = make(MAX);
    for (int d = MIN; d <= MAX; d += 2) {
        uint64_t iterations = 1ull << (MAX - d + MIN);
        for (uint64_t i = 0; i < iterations; i++) {
            Node *t = make(d);
            total += check(t);
            release(t);
        }
    }
    total += check(lived);
    release(lived);
    printf("%llu\n", (unsigned long long)total);
    return 0;
}
