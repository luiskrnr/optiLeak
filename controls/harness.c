#include <stdint.h>
#include <stdio.h>
#include "ct.h"

uint8_t ctl_leaky(uint8_t secret);
// prototype, tells "function exists"
// defined in other file, linker joins
// if it would be in the same file as main,
// compiler could inline, optimize around its value

int main(void) {
    uint8_t k = 3;
    CT_SECRET(&k, sizeof k);     // k is now "secret" for valgrind

    uint8_t r = ctl_leaky(k);

    CT_PUBLIC(&r, sizeof r);     // declassify the result, otherwise printf gets reported
    printf("%u\n", r);
    return 0;
}