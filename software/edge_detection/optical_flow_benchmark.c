#include <stdio.h>
#include <stdint.h>
#include <math.h>

#ifndef IMG_WIDTH
#define IMG_WIDTH  32
#endif

#ifndef IMG_HEIGHT
#define IMG_HEIGHT 32
#endif
#define NPIX       (IMG_WIDTH * IMG_HEIGHT)

static uint8_t frame1[NPIX];
static uint8_t frame2[NPIX];

static float flow_x[NPIX];
static float flow_y[NPIX];
static float smooth_flow_x[NPIX];
static float smooth_flow_y[NPIX];

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

static inline int idx(int x, int y) {
    return y * IMG_WIDTH + x;
}

// Generate two video test frames with motion between them
static void init_input_frames(void) {
    int shift_x = 1;
    int shift_y = 1;

    for (int y = 0; y < IMG_HEIGHT; y++) {
        for (int x = 0; x < IMG_WIDTH; x++) {
            // Base pattern: checkerboard with gradient
            uint8_t val1 = (((x / 4) + (y / 4)) % 2 == 0) ? 200 : (uint8_t)((x * 11 + y * 17) % 256);
            frame1[idx(x, y)] = val1;

            // Shifted pattern for frame2 to simulate horizontal & vertical optical motion
            int src_x = (x >= shift_x) ? (x - shift_x) : x;
            int src_y = (y >= shift_y) ? (y - shift_y) : y;
            uint8_t val2 = (((src_x / 4) + (src_y / 4)) % 2 == 0) ? 200 : (uint8_t)((src_x * 11 + src_y * 17) % 256);
            frame2[idx(x, y)] = val2;
        }
    }
}

// Lucas-Kanade / Gradient Optical Flow calculation algorithm from nonFunc_assistance
static void run_optical_flow(void) {
    // 1. Calculate raw optical flow velocity components
    for (int y = 1; y < IMG_HEIGHT - 1; y++) {
        for (int x = 1; x < IMG_WIDTH - 1; x++) {
            int i = idx(x, y);

            float Ix = (float)frame1[idx(x + 1, y)] - (float)frame1[idx(x - 1, y)];
            float Iy = (float)frame1[idx(x, y + 1)] - (float)frame1[idx(x, y - 1)];
            float It = (float)frame2[i] - (float)frame1[i];

            float denom = Ix * Ix + Iy * Iy + 1e-4f;

            float vx = -Ix * It / denom;
            float vy = -Iy * It / denom;

            flow_x[i] = vx;
            flow_y[i] = vy;
        }
    }

    // 2. 3x3 Flow Smoothing Filter (from nonFunc_assistance)
    for (int y = 1; y < IMG_HEIGHT - 1; y++) {
        for (int x = 1; x < IMG_WIDTH - 1; x++) {
            float sum_x = 0.0f;
            float sum_y = 0.0f;

            for (int dy = -1; dy <= 1; dy++) {
                for (int dx = -1; dx <= 1; dx++) {
                    int j = idx(x + dx, y + dy);
                    sum_x += flow_x[j];
                    sum_y += flow_y[j];
                }
            }

            int i = idx(x, y);
            smooth_flow_x[i] = sum_x / 9.0f;
            smooth_flow_y[i] = sum_y / 9.0f;
        }
    }
}

int main(void) {
    printf("[INFO] Starting Optical Flow Benchmark (%dx%d)...\n", IMG_WIDTH, IMG_HEIGHT);

    init_input_frames();

    // Clear mcountinhibit to ensure performance counters are active
    CSR_WRITE(mcountinhibit, 0);

    // Setup RISC-V HPM counters
    CSR_WRITE(mhpmevent3, 0x4000);  // Branches
    CSR_WRITE(mhpmevent4, 0x2001);  // Branch Mispredictions
    CSR_WRITE(mhpmevent5, 0x0102);  // I$ misses
    CSR_WRITE(mhpmevent6, 0x0E00);  // D$ accesses
    CSR_WRITE(mhpmevent7, 0x0202);  // D$ misses

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

    run_optical_flow();

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
    double sum_mag = 0.0;
    for (int i = 0; i < NPIX; i++) {
        float vx = smooth_flow_x[i];
        float vy = smooth_flow_y[i];
        float mag = sqrtf(vx * vx + vy * vy);
        sum_mag += mag;
        checksum += (uint64_t)(fabsf(vx) * 100.0f) + (uint64_t)(fabsf(vy) * 100.0f);
    }

    printf("[INFO] Optical Flow completed successfully. Average flow magnitude: %.4f\n", sum_mag / NPIX);
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
