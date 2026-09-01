#include <sys/types.h>
#include <stdint.h>

// This is a magic variable provided by the RISC-V bare-metal Linker Script.
// It points to the exact memory address where your C program's variables end, 
// meaning everything after this address is free, unused DDR3 RAM!
extern char _end; 

// The pointer that tracks the top of the heap
static char *heap_ptr = 0;

// The function Newlib's malloc calls when it needs raw memory
void *_sbrk(ptrdiff_t incr) {
    char *prev_heap_ptr;

    // If this is the very first time malloc is called, 
    // initialize the heap pointer to the end of the program's data.
    if (heap_ptr == 0) {
        heap_ptr = &_end;
    }

    prev_heap_ptr = heap_ptr;

    // Move the pointer forward by the amount of bytes malloc requested
    heap_ptr += incr;

    // Return the starting address of the newly allocated continuous chunk
    return (void *)prev_heap_ptr;
}
