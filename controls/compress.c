#include <stdint.h>

#define Q 3329

// Kyber-style compression of a secret coefficient to 1 bit.
// In C this is "just a division". Whether it stays one depends on the compiler.
uint8_t ctl_compress1(uint16_t s) {
    return (uint8_t)(((((uint32_t)s << 1) + Q / 2) / Q) & 1);
}