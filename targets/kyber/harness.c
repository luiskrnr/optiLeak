#include <stdint.h>
#include <string.h>
#include "kem.h"
#include "params.h"
#include "ct.h"   /* include/ct.h */

int main(void) {
    uint8_t pk[CRYPTO_PUBLICKEYBYTES], sk[CRYPTO_SECRETKEYBYTES];
    uint8_t ct[CRYPTO_CIPHERTEXTBYTES], ss1[CRYPTO_BYTES], ss2[CRYPTO_BYTES];
    crypto_kem_keypair(pk, sk);
    crypto_kem_enc(ct, ss1, pk);
    CT_SECRET(sk, KYBER_INDCPA_SECRETKEYBYTES);              /* dk_PKE */
    CT_SECRET(sk + CRYPTO_SECRETKEYBYTES - KYBER_SYMBYTES, KYBER_SYMBYTES);  /* z */
    crypto_kem_dec(ss2, ct, sk);
    CT_PUBLIC(ss2, sizeof ss2);
    return memcmp(ss1, ss2, sizeof ss1) != 0;
}