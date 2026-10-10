# optiLeak
Detects compiler-induced timing leaks in ML-KEM/ML-DSA across GCC/Clang, -O levels and x86/ARM/RISC-V via Valgrind taint. Hunting timing leaks that compilers put back into constant-time crypto. Valgrind taint tracking, disassembly diffing, lots of compiler flags.
