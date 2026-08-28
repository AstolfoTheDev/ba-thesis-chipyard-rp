#include <stdio.h>
#include <stdint.h>

#ifndef IMG_WIDTH
#define IMG_WIDTH  32
#endif

#ifndef IMG_HEIGHT
#define IMG_HEIGHT 32
#endif
#define NPIX       (IMG_WIDTH * IMG_HEIGHT)

static uint8_t input_image[NPIX];
static uint8_t output_edges[NPIX];

#define CSR_WRITE(csr, val) \
    __asm__ __volatile__ ("csrw " #csr ", %0" :: "rK"(val))

#define CSR_READ(csr, val) \
    __asm__ __volatile__ ("csrr %0, " #csr : "=r"(val))

// Read RISC-V machine cycle counter
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

// Read RISC-V instructions retired counter
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

static inline int iabs(int x) {
    return (x < 0) ? -x : x;
}

// Generate input test pattern with distinct edges
static void init_input_image(void) {
    for (int y = 0; y < IMG_HEIGHT; y++) {
        for (int x = 0; x < IMG_WIDTH; x++) {
            if (((x / 8) + (y / 8)) % 2 == 0) {
                input_image[y * IMG_WIDTH + x] = 255;
            } else {
                input_image[y * IMG_WIDTH + x] = (uint8_t)((x * 7 + y * 13) % 256);
            }
        }
    }
}

// Sobel Edge Detection kernel execution
static void run_sobel_edge_detection(void) {
    const int Gx[3][3] = {
        {-1, 0, 1},
        {-2, 0, 2},
        {-1, 0, 1}
    };
    const int Gy[3][3] = {
        {-1, -2, -1},
        { 0,  0,  0},
        { 1,  2,  1}
    };

    for (int y = 1; y < IMG_HEIGHT - 1; y++) {
        for (int x = 1; x < IMG_WIDTH - 1; x++) {
            int sumX = 0;
            int sumY = 0;

            for (int ky = -1; ky <= 1; ky++) {
                for (int kx = -1; kx <= 1; kx++) {
                    int pixel = input_image[(y + ky) * IMG_WIDTH + (x + kx)];
                    sumX += pixel * Gx[ky + 1][kx + 1];
                    sumY += pixel * Gy[ky + 1][kx + 1];
                }
            }

            int mag = iabs(sumX) + iabs(sumY);
            if (mag > 255) mag = 255;
            output_edges[y * IMG_WIDTH + x] = (uint8_t)mag;
        }
    }
}

int main(void) {
    printf("[INFO] Starting Sobel Edge Detection Benchmark (%dx%d)...\n", IMG_WIDTH, IMG_HEIGHT);

    init_input_image();

    // Clear mcountinhibit to ensure counters are enabled (it may be uninitialized or disabled by default)
    CSR_WRITE(mcountinhibit, 0);

    // Setup HPM counters for Rocket Chip
    // mhpmevent3: Branches (EventSet 0, bit 6)
    CSR_WRITE(mhpmevent3, 0x4000);
    // mhpmevent4: Branch Mispredictions (EventSet 1, bit 5)
    CSR_WRITE(mhpmevent4, 0x2001);
    // mhpmevent5: I$ misses (EventSet 2, bit 0)
    CSR_WRITE(mhpmevent5, 0x0102);
    // mhpmevent6: D$ accesses (load/store/amo) (EventSet 0, bits 1,2,3)
    CSR_WRITE(mhpmevent6, 0x0E00);
    // mhpmevent7: D$ misses (EventSet 2, bit 1)
    CSR_WRITE(mhpmevent7, 0x0202);

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

    run_sobel_edge_detection();

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

    // Calculate checksum for output verification
    uint64_t checksum = 0;
    for (int i = 0; i < NPIX; i++) {
        checksum += output_edges[i];
    }

    printf("[INFO] Edge Detection completed successfully.\n");
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

    return 0;
}
