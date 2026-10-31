#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct Node { uint64_t value; struct Node *next; } Node;

int main(void) {
    uint64_t sum = 0;
    for (uint64_t round = 0; round < 10; round++) {
        Node *head = NULL;
        for (uint64_t i = 0; i < 2000000; i++) {
            Node *n = malloc(sizeof *n);
            if (!n) return 1;
            n->value = (i + round) % 1000;
            n->next = head;
            head = n;
        }
        for (Node *n = head; n; n = n->next) sum += n->value;
        while (head) { Node *n = head->next; free(head); head = n; }
    }
    printf("%llu\n", (unsigned long long)sum);
    return 0;
}
