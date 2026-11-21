#!/usr/bin/env bash
# Load the PL bitstream, initialise the PS and start MicroPython over JTAG.
# Volatile: lost on power-off.
#   ./program.sh [system.bit] [ps7_init.tcl] [firmware.elf]
set -eo pipefail

VIVADO_ROOT="${VIVADO_ROOT:-/tools/Xilinx/Vivado/2021.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIT="${1:-$ROOT/hw/build/system.bit}"
PS7="${2:-$ROOT/hw/build/ps7_init.tcl}"
ELF="${3:-$ROOT/ports/zynq/build/firmware.elf}"
for f in "$BIT" "$PS7" "$ELF"; do
    [[ -f "$f" ]] || { echo "ERROR: $f not found. Run ./build.sh first." >&2; exit 1; }
done

# Start from a fresh hw_server so it rescans USB
pkill -x hw_server 2>/dev/null || true

# Run xsdb via 'loader': the bin/xsdb wrapper's bundled rlwrap segfaults on WSL
"$VIVADO_ROOT/bin/loader" -exec rdi_xsdb "$ROOT/scripts/program.tcl" "$BIT" "$PS7" "$ELF"
