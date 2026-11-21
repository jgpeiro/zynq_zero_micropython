#!/usr/bin/env bash
# ZYNQ ZERO MicroPython: build the hardware (Vivado) and/or the firmware.
#
#   ./build.sh          hw + fw
#   ./build.sh hw       hw/build/system.bit, hw/build/ps7_init.tcl
#   ./build.sh fw       ports/zynq/build/firmware.elf (clones MicroPython, LVGL and the
#                       LVGL binding on first run; LVGL=0 ./build.sh fw builds without LVGL)
#   ./build.sh qemu     firmware for QEMU's xilinx-zynq-a9 and start its REPL (Ctrl-A x quits)
#   ./build.sh sim      simulate the two PL FFT engines with iverilog, check against numpy
#   ./build.sh clean    remove firmware build output
set -eo pipefail

VIVADO_ROOT="${VIVADO_ROOT:-/tools/Xilinx/Vivado/2021.1}"
VITIS_ROOT="${VITIS_ROOT:-/tools/Xilinx/Vitis/2021.1}"
MICROPY_VERSION="${MICROPY_VERSION:-v1.29.0}"
LVGL_VERSION="${LVGL_VERSION:-v9.6.0}"
LV_BINDING_COMMIT="${LV_BINDING_COMMIT:-032dda4b7e8419702a4b9c4c8748a4d85d51be61}"
export LVGL="${LVGL:-1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MICROPY_DIR="${MICROPY_DIR:-$ROOT/micropython}"
PORT="$ROOT/ports/zynq"
WHAT="${1:-all}"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"

build_hw() {
    mkdir -p "$ROOT/hw/build" && cd "$ROOT/hw/build"
    # Call vivado directly (settings64.sh on this install has stale paths)
    JOBS="$JOBS" "$VIVADO_ROOT/bin/vivado" -mode batch -nojournal -log build.log \
        -source "$ROOT/hw/scripts/build.tcl"
}

get_micropython() {
    if [[ ! -f "$MICROPY_DIR/py/mkenv.mk" ]]; then
        echo "Cloning MicroPython $MICROPY_VERSION into $MICROPY_DIR"
        git clone --depth 1 --branch "$MICROPY_VERSION" \
            https://github.com/micropython/micropython.git "$MICROPY_DIR"
    fi
    # Needed for frozen modules (asyncio)
    if [[ ! -f "$MICROPY_DIR/lib/micropython-lib/README.md" ]]; then
        git -C "$MICROPY_DIR" submodule update --init --depth 1 lib/micropython-lib
    fi
}

# LVGL + lv_binding_micropython in usermods/ (user C modules of the port)
get_lvgl() {
    local b="$ROOT/usermods/lv_binding_micropython"
    if [[ ! -f "$b/gen/gen_mpy.py" ]]; then
        echo "Fetching lv_binding_micropython @ $LV_BINDING_COMMIT"
        rm -rf "$b" && mkdir -p "$b"
        git -C "$b" init -q
        git -C "$b" remote add origin https://github.com/lvgl/lv_binding_micropython.git
        git -C "$b" fetch -q --depth 1 origin "$LV_BINDING_COMMIT"
        git -C "$b" checkout -q FETCH_HEAD
    fi
    if [[ ! -f "$b/pycparser/pycparser/__init__.py" ]]; then
        git -C "$b" submodule update --init --depth 1 pycparser   # used by the generator
    fi
    if [[ ! -f "$b/lvgl/lvgl.h" ]]; then
        echo "Fetching LVGL $LVGL_VERSION"
        rm -rf "$b/lvgl"
        git clone -q --depth 1 --branch "$LVGL_VERSION" https://github.com/lvgl/lvgl.git "$b/lvgl"
    fi
    # MicroPython 1.29 removed mp_obj_int_to_bytes_impl (idempotent)
    sed -i 's/mp_obj_int_to_bytes_impl(obj, big_endian, sizeof(val), (byte\*)&val);/mp_obj_int_to_bytes(obj, sizeof(val), (byte*)\&val, big_endian, false, false);/' \
        "$b/gen/gen_mpy.py"
}

# arm-none-eabi toolchain: $CROSS_COMPILE, then PATH, then Vitis's copy
find_cross() {
    if [[ -n "$CROSS_COMPILE" ]]; then echo "$CROSS_COMPILE"; return; fi
    if command -v arm-none-eabi-gcc >/dev/null 2>&1; then echo "arm-none-eabi-"; return; fi
    local vitis_gcc="$VITIS_ROOT/gnu/aarch32/lin/gcc-arm-none-eabi/bin/arm-none-eabi-gcc"
    if [[ -x "$vitis_gcc" ]]; then echo "${vitis_gcc%gcc}"; return; fi
    echo "ERROR: no arm-none-eabi-gcc found. Install one (sudo apt install gcc-arm-none-eabi)" >&2
    echo "       or set CROSS_COMPILE=/path/to/arm-none-eabi-" >&2
    exit 1
}

build_fw() {
    get_micropython
    if [[ "$LVGL" == 1 ]]; then
        get_lvgl
    fi
    # mpy-cross is a host tool: build it first with the host compiler, so the
    # CROSS_COMPILE passed to the port build below can't leak into it.
    if [[ ! -x "$MICROPY_DIR/mpy-cross/build/mpy-cross" ]]; then
        make -C "$MICROPY_DIR/mpy-cross" -j"$JOBS"
    fi
    local cross; cross="$(find_cross)"
    echo "Using toolchain: ${cross}gcc"
    make -C "$PORT" -j"$JOBS" MICROPY_DIR="$MICROPY_DIR" CROSS_COMPILE="$cross" "$@"
}

case "$WHAT" in
    hw)    build_hw ;;
    fw)    build_fw ;;
    all)   build_hw; build_fw ;;
    qemu)  build_fw QEMU=1 && build_fw QEMU=1 run ;;
    sim)   python3 "$ROOT/hw/sim/run_sim.py" ;;
    clean) rm -rf "$PORT/build" "$PORT/build-qemu" ;;
    *)     echo "usage: $0 [all|hw|fw|qemu|sim|clean]" >&2; exit 2 ;;
esac
