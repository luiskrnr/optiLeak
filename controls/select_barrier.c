#include <stdint.h>

uint32_t ctl_select_barrier(uint32_t a, uint32_t b, uint32_t x, uint32_t y) {
    uint32_t mask = -(uint32_t)(x == y);
    __asm__("" : "+r"(mask));          // compiler barrier: "mask could be anything now"
    return (mask & a) | (~mask & b);
}