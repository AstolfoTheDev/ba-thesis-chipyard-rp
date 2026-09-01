#!/bin/bash
# setup_fftw.sh - Automates bare-metal FFTW cross-compilation and Makefile patching

set -e

echo "========================================"
echo " 1. Building Bare-Metal FFTW for RISC-V..."
echo "========================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Locate Chipyard root directory
if [ -f "$SCRIPT_DIR/env.sh" ]; then
  CHIPYARD_DIR="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/../env.sh" ]; then
  CHIPYARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -f "$SCRIPT_DIR/../chipyard/env.sh" ]; then
  CHIPYARD_DIR="$(cd "$SCRIPT_DIR/../chipyard" && pwd)"
else
  CHIPYARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

echo " -> Detected Chipyard directory: $CHIPYARD_DIR"

# Source Chipyard environment if env.sh exists
if [ -f "$CHIPYARD_DIR/env.sh" ]; then
  echo " -> Sourcing environment from $CHIPYARD_DIR/env.sh"
  source "$CHIPYARD_DIR/env.sh"
fi

# Ensure riscv64-unknown-elf-gcc is in PATH
if ! command -v riscv64-unknown-elf-gcc &> /dev/null; then
  if [ -d "$CHIPYARD_DIR/.conda-env/riscv-tools/bin" ]; then
    export PATH="$CHIPYARD_DIR/.conda-env/riscv-tools/bin:$CHIPYARD_DIR/.conda-env/bin:$PATH"
    export RISCV="$CHIPYARD_DIR/.conda-env/riscv-tools"
  fi
fi

if ! command -v riscv64-unknown-elf-gcc &> /dev/null; then
  echo "::ERROR:: riscv64-unknown-elf-gcc not found in PATH!"
  exit 1
fi

BUILD_DIR="$SCRIPT_DIR/fftw-3.3.10"
TAR_FILE="$SCRIPT_DIR/fftw-3.3.10.tar.gz"

# Download FFTW tarball if needed
if [ ! -f "$TAR_FILE" ] && [ ! -d "$BUILD_DIR" ]; then
  echo " -> Downloading FFTW 3.3.10..."
  wget -qnc http://www.fftw.org/fftw-3.3.10.tar.gz -O "$TAR_FILE"
fi

# Extract FFTW tarball if needed
if [ ! -d "$BUILD_DIR" ]; then
  echo " -> Extracting FFTW 3.3.10..."
  tar -xzf "$TAR_FILE" -C "$SCRIPT_DIR"
fi

cd "$BUILD_DIR"

# Configure FFTW if not configured yet
if [ ! -f "config.status" ]; then
  echo " -> Configuring FFTW for bare-metal RISC-V..."
  ./configure --host=riscv64-unknown-elf \
    CC=riscv64-unknown-elf-gcc \
    CFLAGS="-O2 -mcmodel=medany" \
    --disable-shared \
    --enable-static \
    --disable-threads \
    --disable-fortran
fi

echo " -> Compiling FFTW static library..."
make -j$(nproc)

echo "========================================"
echo " 2. Patching Chipyard Environment..."
echo "========================================"

TESTS_DIR="$CHIPYARD_DIR/tests"
mkdir -p "$TESTS_DIR"

echo " -> Copying FFTW static library and headers to $TESTS_DIR..."
cp -f .libs/libfftw3.a "$TESTS_DIR/"
cp -f api/fftw3.h "$TESTS_DIR/"

# Copy baremetal sources if present in baremetal_src
BAREMETAL_SRC="$SCRIPT_DIR/baremetal_src"
if [ -d "$BAREMETAL_SRC" ]; then
  echo " -> Copying baremetal sources to $TESTS_DIR..."
  cp -f "$BAREMETAL_SRC"/* "$TESTS_DIR/"
fi

MAKEFILE_PATH="$TESTS_DIR/Makefile"
CMAKELISTS_PATH="$TESTS_DIR/CMakeLists.txt"

# Patch CMakeLists.txt if present
if [ -f "$CMAKELISTS_PATH" ]; then
  if ! grep -q "fft_benchmark" "$CMAKELISTS_PATH"; then
    cat << 'EOF' >> "$CMAKELISTS_PATH"

# FFTW Bare-Metal Benchmark Target
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/fft_benchmark.c" AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/libfftw3.a")
    add_executable(fft_benchmark fft_benchmark.c)
    target_link_libraries(fft_benchmark PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/libfftw3.a m)
    add_dump_target(fft_benchmark)
endif()
EOF
    echo " -> Added fft_benchmark target to $CMAKELISTS_PATH"
  else
    # Update existing target in CMakeLists.txt to fft_benchmark.c
    sed -i 's/add_executable(fft_benchmark fft_benchmark.c printf.c syscalls.c)/add_executable(fft_benchmark fft_benchmark.c)/g' "$CMAKELISTS_PATH"
  fi

  if command -v cmake &> /dev/null; then
    echo " -> Regenerating CMake build files in $TESTS_DIR..."
    cmake -S "$TESTS_DIR" -B "$TESTS_DIR"
  fi
fi

# Patch Makefile if present
if [ -f "$MAKEFILE_PATH" ]; then
  if ! grep -q "\-mcmodel=medany" "$MAKEFILE_PATH"; then
    sed -i '/^CFLAGS  =/ s/$/ -mcmodel=medany/' "$MAKEFILE_PATH"
    echo " -> Injected -mcmodel=medany into CFLAGS"
  else
    echo " -> CFLAGS already patched, skipping."
  fi

  if ! grep -q "fft_benchmark.riscv:" "$MAKEFILE_PATH"; then
    printf "\n# Custom override to enforce strict Linker Order for FFTW\n" >> "$MAKEFILE_PATH"
    printf "fft_benchmark.riscv: fft_benchmark.o \$(libgloss)\n" >> "$MAKEFILE_PATH"
    printf "\t\$(GCC) \$(LDFLAGS) $< -o \$@ -L. -lfftw3 -lm\n" >> "$MAKEFILE_PATH"
    echo " -> Injected custom FFTW linker rule into Makefile"
  else
    echo " -> Linker rule already exists in Makefile, skipping."
  fi
fi

echo "========================================"
echo " SUCCESS: Environment completely automated!"
echo "========================================"