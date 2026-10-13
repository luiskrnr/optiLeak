#include <stdint.h>

#define KYBER_N 256
#define KYBER_Q 3329

/* Kyber reference poly_frommsg BEFORE the 2024 fix (CVE-2024-37880, "Clangover").
 * Branch-free in C: mask = -bit, then AND. */
void ctl_frommsg(int16_t r[KYBER_N], const uint8_t msg[KYBER_N / 8]) {
    for (unsigned i = 0; i < KYBER_N / 8; i++) {
        for (unsigned j = 0; j < 8; j++) {
            int16_t mask = -(int16_t)((msg[i] >> j) & 1);
            r[8 * i + j] = mask & ((KYBER_Q + 1) / 2);
        }
    }
}