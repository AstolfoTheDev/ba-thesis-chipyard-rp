#include <stdlib.h>
#include "fftw3.h"    // The FFTW API
#include "printf.h"
#include "printf.c"   
#include "syscalls.c" 

#define UART_BASE 0x10020000
#define UART_TXDATA (UART_BASE + 0x00)
#define UART_TXCTRL (UART_BASE + 0x08)

void uart_init() {
    volatile int *txctrl = (int*)UART_TXCTRL;
    *txctrl = 1; 
}

void _putchar(char c) {
    volatile int *txdata = (int*)UART_TXDATA;
    while ((*txdata) & (1 << 31)); // Wait for buffer
    *txdata = (int)c;
}

int main() {
    uart_init();
    
    // Checkpoint 1: Did we even boot?
    printf("1. BOOT\n");
    
    int N = 16; 
    fftw_complex *in, *out;
    fftw_plan p;

    // Checkpoint 2: Did malloc survive?
    printf("2. MALLOC\n");
    in = (fftw_complex*) fftw_malloc(sizeof(fftw_complex) * N);
    out = (fftw_complex*) fftw_malloc(sizeof(fftw_complex) * N);

    if (!in || !out) {
        printf("FATAL: Out of memory!\n");
        while(1){}
    }

    for (int i = 0; i < N; i++) {
        in[i][0] = i; 
        in[i][1] = 0; 
    }

    // Checkpoint 3: Does the Plan crash the Stack?
    printf("3. PLAN\n");
    p = fftw_plan_dft_1d(N, in, out, FFTW_FORWARD, FFTW_ESTIMATE);

    // Checkpoint 4: Does the Execution crash the FPU?
    printf("4. EXECUTE\n");
    fftw_execute(p);

    printf("5. SUCCESS!\n");

    // CRITICAL: DO NOT REMOVE THIS LOOP
    for (volatile int i = 0; i < 2000000; i++);
    
    return 0;
}