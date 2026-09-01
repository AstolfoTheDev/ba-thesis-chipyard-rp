cmake_minimum_required(VERSION 3.10)
project(ba_thesis_benchmarks LANGUAGES C CXX)

set(CMAKE_SYSTEM_NAME         "Generic" CACHE STRING "")
set(CMAKE_SYSTEM_PROCESSOR    "riscv"   CACHE STRING "")
set(TOOLCHAIN_PREFIX          "riscv64-unknown-elf-")

set(CMAKE_AR            "${TOOLCHAIN_PREFIX}ar")
set(CMAKE_ASM_COMPILER  "${TOOLCHAIN_PREFIX}gcc")
set(CMAKE_C_COMPILER    "${TOOLCHAIN_PREFIX}gcc")
set(CMAKE_CXX_COMPILER  "${TOOLCHAIN_PREFIX}g++")
set(CMAKE_LINKER        "${TOOLCHAIN_PREFIX}ld")
set(CMAKE_OBJCOPY       "${TOOLCHAIN_PREFIX}objcopy")
set(CMAKE_OBJDUMP       "${TOOLCHAIN_PREFIX}objdump")
set(CMAKE_SIZE          "${TOOLCHAIN_PREFIX}size")

set(CMAKE_EXECUTABLE_SUFFIX ".riscv")

set(ARCH_FLAGS -march=rv64imafd -mabi=lp64d -mcmodel=medany)
set(SPEC_FLAGS -specs=htif_nano.specs)
set(LINKER_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/common/htif.ld")

add_compile_options(-std=gnu99 -O2 -Wall -Wextra -fno-common -fno-builtin-printf)
add_compile_options(${ARCH_FLAGS} ${SPEC_FLAGS})

add_link_options(-static ${SPEC_FLAGS} -T ${LINKER_SCRIPT})

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/common
    ${CMAKE_CURRENT_SOURCE_DIR}/edge_detection
    ${CMAKE_CURRENT_SOURCE_DIR}/fft
)

# Edge Detection Baremetal
add_executable(edgeBare edge_detection/edgeBare.c common/printf.c common/syscalls.c)
target_link_libraries(edgeBare PRIVATE m)

# Optical Flow Benchmark
add_executable(optical_flow_benchmark edge_detection/optical_flow_benchmark.c common/printf.c common/syscalls.c)
target_link_libraries(optical_flow_benchmark PRIVATE m)

# FFT Benchmark
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/fft/libfftw3.a")
    add_executable(fft_benchmark fft/fft_benchmark.c common/printf.c common/syscalls.c)
    target_link_libraries(fft_benchmark PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/fft/libfftw3.a m)
endif()

# HPM Test
add_executable(test_hpm common/test_hpm.c common/printf.c common/syscalls.c)

# Embench 1.0 Suite
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/embench-iot/chipyard_boardsupport.c")
    add_compile_definitions(WARMUP_HEAT=0 CPU_MHZ=1)
    set(EMBENCH_SUPPORT
        embench-iot/support/main.c
        embench-iot/support/beebsc.c
        embench-iot/chipyard_boardsupport.c
        common/printf.c
        common/syscalls.c
    )
    include_directories(embench-iot/support)

    macro(add_embench name)
        add_executable(embench_${name} ${EMBENCH_SUPPORT} ${ARGN})
        target_include_directories(embench_${name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/embench-iot/src/${name})
        target_link_libraries(embench_${name} PRIVATE m)
    endmacro()

    add_embench(aha-mont64 embench-iot/src/aha-mont64/mont64.c)
    add_embench(crc32 embench-iot/src/crc32/crc_32.c)
    add_embench(cubic embench-iot/src/cubic/libcubic.c embench-iot/src/cubic/basicmath_small.c)
    add_embench(edn embench-iot/src/edn/libedn.c)
    add_embench(huffbench embench-iot/src/huffbench/libhuffbench.c)
    add_embench(matmult-int embench-iot/src/matmult-int/matmult-int.c)
    add_embench(minver embench-iot/src/minver/libminver.c)
    add_embench(nbody embench-iot/src/nbody/nbody.c)
    add_embench(nettle-aes embench-iot/src/nettle-aes/nettle-aes.c)
    add_embench(nettle-sha256 embench-iot/src/nettle-sha256/nettle-sha256.c)
    add_embench(nsichneu embench-iot/src/nsichneu/libnsichneu.c)
    add_embench(picojpeg embench-iot/src/picojpeg/picojpeg_test.c embench-iot/src/picojpeg/libpicojpeg.c)
    add_embench(qrduino embench-iot/src/qrduino/qrtest.c embench-iot/src/qrduino/qrframe.c embench-iot/src/qrduino/qrencode.c)
    add_embench(sglib-combined embench-iot/src/sglib-combined/combined.c)
    add_embench(slre embench-iot/src/slre/libslre.c)
    add_embench(st embench-iot/src/st/libst.c)
    add_embench(statemate embench-iot/src/statemate/libstatemate.c)
    add_embench(ud embench-iot/src/ud/libud.c)
    add_embench(wikisort embench-iot/src/wikisort/libwikisort.c)
endif()

