#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/setup_fftw.sh" ]; then
  exec bash "$SCRIPT_DIR/setup_fftw.sh" "$@"
elif [ -f "$SCRIPT_DIR/software/fft/setup_fftw.sh" ]; then
  exec bash "$SCRIPT_DIR/software/fft/setup_fftw.sh" "$@"
elif [ -f "$SCRIPT_DIR/generators/ba-thesis-chipyard-rp/software/fft/setup_fftw.sh" ]; then
  exec bash "$SCRIPT_DIR/generators/ba-thesis-chipyard-rp/software/fft/setup_fftw.sh" "$@"
fi
