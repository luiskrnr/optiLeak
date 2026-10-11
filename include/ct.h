#ifndef CT_H
#define CT_H
#include <valgrind/memcheck.h>

#define CT_SECRET(p,n) VALGRIND_MAKE_MEM_UNDEFINED((p), n)
#define CT_PUBLIC(p,n) VALGRIND_MAKE_MEM_DEFINED((p), n)

#endif

// p is a pointer to the memory region, n is size of  memory in bytes 
//  CT_SECRET macro marks  specified memory region as undefined, indicating that it contains
// secret data, should not be accessed or modified. CT_PUBLIC macro marks the specified memory 
// region as defined, indicating that it is safe to access, modify. 