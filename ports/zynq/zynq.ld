/*
 * zynq.ld - MicroPython in DDR on the ZYNQ ZERO (512 MB DDR3 at 0x0).
 *
 * The first 1 MB is left alone (low OCM shadows DDR at 0x0-0x2FFFF), as the
 * Xilinx tools do. xsdb loads the ELF segments directly, so .data has no
 * separate load address.
 *
 * SPDX-License-Identifier: MIT
 */
ENTRY(_vectors)

MEMORY
{
    DDR (rwx) : ORIGIN = 0x00100000, LENGTH = 511M
}

/* Overridable from the Makefile with --defsym */
STACK_SIZE = DEFINED(STACK_SIZE) ? STACK_SIZE : 256K;
HEAP_SIZE  = DEFINED(HEAP_SIZE)  ? HEAP_SIZE  : 16M;

SECTIONS
{
    .text : {
        KEEP(*(.vectors))
        *(.text .text.*)
        *(.rodata .rodata.*)
        . = ALIGN(4);
        *(.ARM.extab* .gnu.linkonce.armextab.*)
    } > DDR

    .ARM.exidx : {
        __exidx_start = .;
        *(.ARM.exidx* .gnu.linkonce.armexidx.*)
        __exidx_end = .;
    } > DDR

    .data : ALIGN(8) {
        *(.data .data.*)
    } > DDR

    /* LVGL's memory pool (LV_ATTRIBUTE_LARGE_RAM_ARRAY in usermods/lv_conf.h).
       Not zeroed; gc_collect() scans it for pointers into the GC heap. Empty
       when built without LVGL. */
    .lvgl_pool (NOLOAD) : ALIGN(16) {
        _lv_pool_start = .;
        *(.bss.lvgl_pool)
        . = ALIGN(16);
        _lv_pool_end = .;
    } > DDR

    .bss (NOLOAD) : ALIGN(16) {
        _sbss = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(16);
        _ebss = .;
    } > DDR

    .stack (NOLOAD) : ALIGN(16) {
        _sstack = .;
        . += STACK_SIZE;
        _estack = .;
        . += 4K;
        _abt_stack_top = .;
        . += 4K;
        _und_stack_top = .;
    } > DDR

    /* GC heap: not zeroed at boot, gc_init() does not need it */
    .heap (NOLOAD) : ALIGN(16) {
        _heap_start = .;
        . += HEAP_SIZE;
        _heap_end = .;
    } > DDR

    /* HDMI framebuffers: 2 x 1280 x 720 x RGB565, read by the VDMA over HP0 */
    .framebuffer (NOLOAD) : ALIGN(1M) {
        _fb_start = .;
        . += 2 * 1280 * 720 * 2;
        _fb_end = .;
    } > DDR
}
