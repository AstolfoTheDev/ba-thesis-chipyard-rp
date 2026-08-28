# baremetal_src

This folder contains standalone bare-metal C sources used for running and debugging FFTW-based benchmarks on Chipyard-generated RISC-V systems (simulation or FPGA), without relying on a Linux runtime.

## What this folder is for

- Providing a minimal runtime environment for bare-metal execution (UART output and heap support).
- Hosting the FFT benchmark entrypoints used to validate FFTW integration and hardware behavior.
- Keeping helper sources together so they can be copied/integrated into `chipyard/tests/` build flows.

## Files

- `fft_benchmark.c`  
  Main benchmark source with UART-backed output, FFTW plan/execute flow, and result printing.

- `fft_benchmark_results.c`  
  Verbose/checkpoint-oriented variant of the benchmark for bring-up and debugging.

- `syscalls.c`  
  Bare-metal `_sbrk` implementation used by Newlib `malloc` to allocate from free DDR memory.

- `printf.c`, `printf.h`  
  Lightweight embedded `printf` implementation (UART-targeted via `_putchar`) for systems without full libc I/O.

## Notes

- UART is mapped to the SiFive peripheral base `0x10020000`.
- These sources are intended for bare-metal targets and may require adaptation when moved into Chipyard test Makefiles.
