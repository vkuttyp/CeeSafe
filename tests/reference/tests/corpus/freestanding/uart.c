/* The environment for freestanding/uart.cee: register memory, ceesafe_panic, and a caller. */
#include <stdio.h>
#include <stdlib.h>

#include "ceesafe/rt.h"
#include "ceesafe_exports.h"

_Noreturn void ceesafe_panic(cee_panic_kind kind, cee_loc loc) {
    fprintf(stderr, "ceesafe panic: %d at %s:%u:%u\n", (int)kind, loc.file, (unsigned)loc.line, (unsigned)loc.column);
    exit(134);
}

int main(void) {
    static struct UartRegs regs; /* zero: status bit 0x20 clear, so the UART is never busy */
    const uint8_t text[] = { 'h', 'e', 'l', 'l', 'o' };
    uint32_t written = uart_write((size_t)(uintptr_t)&regs, text, sizeof text);
    printf("written %u, last '%c'\n", (unsigned)written, (char)regs.data.f_value);
    printf("selftest %d\n", _uart_selftest() ? 1 : 0);
    return 0;
}
