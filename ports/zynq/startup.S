/*
 * startup.S - Cortex-A9 CPU0 entry for the Zynq MicroPython port.
 *
 * Loaded into DDR by xsdb (after ps7_init) and entered at _vectors in SVC mode.
 * Sets up stacks, VFP, .bss, then calls zynq_start() in main.c, which turns
 * on the MMU and caches and runs MicroPython. CPU1 stays parked in the BootROM.
 *
 * SPDX-License-Identifier: MIT
 */
    .syntax unified
    .arm

    .section .vectors, "ax"
    .global _vectors
_vectors:
    b       reset_handler           /* 0x00 reset              */
    b       undef_handler           /* 0x04 undefined          */
    b       svc_handler             /* 0x08 SVC                */
    b       pabort_handler          /* 0x0C prefetch abort     */
    b       dabort_handler          /* 0x10 data abort         */
    b       .                       /* 0x14 reserved           */
    b       irq_handler             /* 0x18 IRQ (unused)       */
    b       fiq_handler             /* 0x1C FIQ (unused)       */

    .text
    .type   reset_handler, %function
reset_handler:
    cpsid   if, #0x13               /* SVC mode, IRQ/FIQ masked */

    /* MMU, caches, branch prediction and alignment checks off */
    mrc     p15, 0, r0, c1, c0, 0
    bic     r0, r0, #0x0007         /* M, A, C */
    bic     r0, r0, #0x1800         /* Z, I    */
    bic     r0, r0, #0x2000         /* V: vectors at VBAR */
    mcr     p15, 0, r0, c1, c0, 0
    isb

    ldr     r0, =_vectors           /* vector base */
    mcr     p15, 0, r0, c12, c0, 0

    /* Small stacks for the abort/undef modes, so faults can be reported */
    cps     #0x17                   /* ABT */
    ldr     sp, =_abt_stack_top
    cps     #0x1B                   /* UND */
    ldr     sp, =_und_stack_top
    cps     #0x13                   /* SVC */
    ldr     sp, =_estack

    /* VFP/NEON: full access to CP10/CP11, then FPEXC.EN */
    mrc     p15, 0, r0, c1, c0, 2
    orr     r0, r0, #(0xF << 20)
    mcr     p15, 0, r0, c1, c0, 2
    isb
    mov     r0, #0x40000000
    vmsr    fpexc, r0

    /* Zero .bss */
    ldr     r0, =_sbss
    ldr     r1, =_ebss
    mov     r2, #0
1:  cmp     r0, r1
    strlo   r2, [r0], #4
    blo     1b

    bl      zynq_start
2:  wfe
    b       2b

/* ---- Exceptions: report and stop (see zynq_fault in main.c) ---------------- */
undef_handler:
    mov     r0, #1
    sub     r1, lr, #4
    b       fault_common
svc_handler:
    mov     r0, #2
    sub     r1, lr, #4
    b       fault_common
pabort_handler:
    mov     r0, #3
    sub     r1, lr, #4
    b       fault_common
dabort_handler:
    mov     r0, #4
    sub     r1, lr, #8
    b       fault_common
irq_handler:
    mov     r0, #6
    sub     r1, lr, #4
    b       fault_common
fiq_handler:
    mov     r0, #7
    sub     r1, lr, #4
fault_common:
    /* SVC and the other modes share _und_stack if needed; good enough to print */
    cps     #0x1B
    ldr     sp, =_und_stack_top
    bl      zynq_fault
3:  wfe
    b       3b
