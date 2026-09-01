#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "fftw3.h"

#define CSR_WRITE(csr, val) \
    __asm__ __volatile__ ("csrw " #csr ", %0" :: "rK"(val))

#define CSR_READ(csr, val) \
    __asm__ __volatile__ ("csrr %0, " #csr : "=r"(val))

static inline uint64_t read_mcycle(void) {
    uint64_t cycles;
#if __riscv_xlen == 32
    uint32_t lo, hi, tmp;
    __asm__ __volatile__ (
        "1:\n"
        "csrr %0, mcycleh\n"
        "csrr %1, mcycle\n"
        "csrr %2, mcycleh\n"
        "bne %0, %2, 1b\n"
        : "=&r" (hi), "=&r" (lo), "=&r" (tmp)
    );
    cycles = ((uint64_t)hi << 32) | lo;
#else
    __asm__ __volatile__ ("csrr %0, mcycle" : "=r"(cycles));
#endif
    return cycles;
}

static inline uint64_t read_minstret(void) {
    uint64_t instret;
#if __riscv_xlen == 32
    uint32_t lo, hi, tmp;
    __asm__ __volatile__ (
        "1:\n"
        "csrr %0, minstreth\n"
        "csrr %1, minstret\n"
        "csrr %2, minstreth\n"
        "bne %0, %2, 1b\n"
        : "=&r" (hi), "=&r" (lo), "=&r" (tmp)
    );
    instret = ((uint64_t)hi << 32) | lo;
#else
    __asm__ __volatile__ ("csrr %0, minstret" : "=r"(instret));
#endif
    return instret;
}

int main(void) {
    printf("[INFO] Starting FFTW Bare-Metal Benchmark...\n");

    int N = 16;
    fftw_complex *in, *out;
    fftw_plan p;

    in = (fftw_complex*) fftw_malloc(sizeof(fftw_complex) * N);
    out = (fftw_complex*) fftw_malloc(sizeof(fftw_complex) * N);

    if (!in || !out) {
        printf("[ERROR] Out of memory!\n");
        return 1;
    }

    for (int i = 0; i < N; i++) {
        in[i][0] = (double)i;
        in[i][1] = 0.0;
    }

    p = fftw_plan_dft_1d(N, in, out, FFTW_FORWARD, FFTW_ESTIMATE);

    // Clear mcountinhibit to ensure counters are enabled
    CSR_WRITE(mcountinhibit, 0);

    // Setup HPM counters for Rocket Chip
    CSR_WRITE(mhpmevent3, 0x4000);  // Branches
    CSR_WRITE(mhpmevent4, 0x2001);  // Branch mispredictions
    CSR_WRITE(mhpmevent5, 0x0102);  // I$ misses
    CSR_WRITE(mhpmevent6, 0x0E00);  // D$ accesses
    CSR_WRITE(mhpmevent7, 0x0202);  // D$ misses

    // Start counter measurement
    uint64_t start_cycles  = read_mcycle();
    uint64_t start_instret = read_minstret();
    uint64_t start_br = 0, start_br_miss = 0, start_ic_miss = 0, start_dc_acc = 0, start_dc_miss = 0;
#if __riscv_xlen == 64
    CSR_READ(mhpmcounter3, start_br);
    CSR_READ(mhpmcounter4, start_br_miss);
    CSR_READ(mhpmcounter5, start_ic_miss);
    CSR_READ(mhpmcounter6, start_dc_acc);
    CSR_READ(mhpmcounter7, start_dc_miss);
#endif

    fftw_execute(p);

    // End counter measurement
    uint64_t end_cycles  = read_mcycle();
    uint64_t end_instret = read_minstret();
    uint64_t end_br = 0, end_br_miss = 0, end_ic_miss = 0, end_dc_acc = 0, end_dc_miss = 0;
#if __riscv_xlen == 64
    CSR_READ(mhpmcounter3, end_br);
    CSR_READ(mhpmcounter4, end_br_miss);
    CSR_READ(mhpmcounter5, end_ic_miss);
    CSR_READ(mhpmcounter6, end_dc_acc);
    CSR_READ(mhpmcounter7, end_dc_miss);
#endif

    uint64_t delta_cycles  = end_cycles - start_cycles;
    uint64_t delta_instret = end_instret - start_instret;
    uint64_t delta_br = end_br - start_br;
    uint64_t delta_br_miss = end_br_miss - start_br_miss;
    uint64_t delta_ic_miss = end_ic_miss - start_ic_miss;
    uint64_t delta_dc_acc = end_dc_acc - start_dc_acc;
    uint64_t delta_dc_miss = end_dc_miss - start_dc_miss;

    // Checksum calculation over FFT outputs
    uint64_t checksum = 0;
    for (int i = 0; i < N; i++) {
        int r = (int)out[i][0];
        int im = (int)out[i][1];
        checksum += (r < 0 ? -r : r) + (im < 0 ? -im : im);
    }

    printf("[INFO] FFT Execution completed successfully.\n");
    printf("[INFO] Cycles: %lu, Instructions: %lu, Checksum: %lu\n",
           (unsigned long)delta_cycles,
           (unsigned long)delta_instret,
           (unsigned long)checksum);

    // Standardized machine-readable benchmark result tag
    printf("BENCHMARK_RESULT: cycles=%lu instret=%lu checksum=%lu branches=%lu br_misses=%lu ic_misses=%lu dc_accesses=%lu dc_misses=%lu\n",
           (unsigned long)delta_cycles,
           (unsigned long)delta_instret,
           (unsigned long)checksum,
           (unsigned long)delta_br,
           (unsigned long)delta_br_miss,
           (unsigned long)delta_ic_miss,
           (unsigned long)delta_dc_acc,
           (unsigned long)delta_dc_miss);

    fftw_destroy_plan(p);
    fftw_free(in);
    fftw_free(out);

    return 0;
}