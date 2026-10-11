#include <stdint.h>

static const uint8_t table[256] = {1, 2, 3, 4, 5, 6, 7, 8};
// secret value lookup table 

uint8_t ctl_leaky(uint8_t secret) {
    uint8_t r = table[secret];

    if (secret & 1) { // odd or even of lowest bit
        r ^= 0x5a; // just some op, branch has some task
    }