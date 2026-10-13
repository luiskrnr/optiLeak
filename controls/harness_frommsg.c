#include <stdint.h>
#include "ct.h"

void ctl_frommsg(int16_t r[256], const uint8_t msg[32]);

int main(void) {
    uint8_t msg[32];
    int16_t r[256];
    for (int i = 0; i < 32; i++) msg[i] = (uint8_t)(37 * i + 11);  // arbitrary test msg
    CT_SECRET(msg, sizeof msg);
    ctl_frommsg(r, msg);
    return 0;
}