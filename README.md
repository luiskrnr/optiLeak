# optiLeak
Detects compiler-induced timing leaks in ML-KEM/ML-DSA across GCC/Clang, -O levels and x86/ARM/RISC-V via Valgrind taint. Hunting timing leaks that compilers put back into constant-time crypto. Valgrind taint tracking, disassembly diffing, lots of compiler flags.

write branchless crypto code. The compiler doesn't always keep it that way.

In 2026, Mbed TLS disclosed [CVE-2025-66442](https://mbed-tls.readthedocs.io/en/latest/security-advisories/mbedtls-security-advisory-2026-03-compiler-induced-constant-time-violations/):
Clang turned constant-time code into a secret-dependent branch on RISC-V. The advisory
says other compilers and architectures are "likely affected but not yet characterized".
[KyberSlash](https://eprint.iacr.org/2024/1049) showed something similar for Kyber:
a harmless-looking division turns into a variable-time `div` depending on how you compile it.

So I want to find out: **which compiler, flag and CPU combinations break the
constant-time guarantees of the new post-quantum standards (ML-KEM, ML-DSA)?**

## idea

Build every implementation across GCC/Clang versions, `-O0` to `-Os`, and
x86-64 / ARM64 / RISC-V. Then check each binary two ways:

- **Valgrind taint tracking**: mark secrets as "uninitialised" and let memcheck report every branch or memory access that depends on them ([ctgrind](https://www.imperialviolet.org/2010/04/01/ctgrind.html) trick)
- **Disassembly scan**: find `div` instructions and branches the compiler added

Every run starts with code that is known to leak. If the tool misses it, no result counts.

## rough plan

- [ ] Positive controls (secret branch, compiler-added branch, KyberSlash division)
- [ ] Matrix runner + report
- [ ] ML-KEM-768
- [ ] ML-DSA
- [ ] Root cause every finding down to the compiler pass
- [ ] Report anything new to maintainers before publishing
- [ ] GitHub Action that flags new leaks in CI, because [developers barely use these tools](https://eprint.iacr.org/2024/2060.pdf)

updates follow stay tuned
