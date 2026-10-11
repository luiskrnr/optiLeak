#ifndef CT_H
#define CT_H
#include <valgrind/memcheck.h>

#define CT_SECRET(p,n) VALGRIND_MAKE_MEM_UNDEFINED((p), n)
#define CT_PUBLIC(p,n) VALGRIND_MAKE_MEM_DEFINED((p), n)

#endif

// p: pointer to the memory, n: size in bytes
// CT_SECRET: mark bytes as "uninitialised". Valgrind tracks everything computed
//   from them and reports when they decide a branch or a memory address
//   -> that is a timing leak
// CT_PUBLIC: declassify, these bytes may now become public (like final output)