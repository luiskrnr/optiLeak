#include <stdint.h>

// const-time select: returns a if x == y, else b
// no if-statement:  choice is made with bit mask
uint32_t ctl_select(uint32_t a, uint32_t b, uint32_t x, uint32_t y) {
    uint32_t mask = -(uint32_t)(x == y);   // x == y → 0xFFFFFFFF, else 0
    return (mask & a) | (~mask & b);
}