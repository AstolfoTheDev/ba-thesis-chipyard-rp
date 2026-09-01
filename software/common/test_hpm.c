#include <stdio.h>
#include <stdint.h>

#define CSR_WRITE(csr, val) \
    __asm__ __volatile__ ("csrw " #csr ", %0" :: "rK"(val))

#define CSR_READ(csr, val) \
    __asm__ __volatile__ ("csrr %0, " #csr : "=r"(val))

int main(void) {
    uint64_t val;
    CSR_WRITE(mhpmevent3, 0x4000); // Branches
    CSR_WRITE(mhpmevent4, 0x2001); // Branch mispredictions
    CSR_WRITE(mhpmevent5, 0x0102); // I$ misses
    CSR_WRITE(mhpmevent6, 0x0E00); // D$ accesses
    CSR_WRITE(mhpmevent7, 0x0202); // D$ misses

    CSR_READ(mhpmcounter3, val);
    printf("Before: %lu\n", val);
    
    // Do some stuff
    int x = 0;
    for (int i=0; i<100; i++) { x += i; }

    CSR_READ(mhpmcounter3, val);
    printf("After branches: %lu\n", val);
    
    return x;
}
