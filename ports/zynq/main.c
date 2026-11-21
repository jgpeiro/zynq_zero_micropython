/*
 * main.c - Entry point of the Zynq MicroPython port: hardware init, REPL loop,
 * GC hooks and the fault reporter.
 *
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>

#include "py/builtin.h"
#include "py/compile.h"
#include "py/lexer.h"
#include "py/mperrno.h"
#include "py/runtime.h"
#include "py/gc.h"
#include "py/mphal.h"
#include "py/stackctrl.h"
#include "shared/runtime/gchelper.h"
#include "shared/runtime/pyexec.h"
#include "zynq_regs.h"
#include "mmu.h"
#include "uart.h"

// From zynq.ld
extern uint8_t _sstack[], _estack[], _heap_start[], _heap_end[];

// Soft-reset hook for LVGL (usermods/lvgl_hdmi); empty when built without LVGL
__attribute__((weak)) void zynq_lvgl_deinit(void) {
}

static int mp_main(void) {
    mp_cstack_init_with_sp_here((size_t)(_estack - _sstack));
    gc_init(_heap_start, _heap_end);

    for (;;) {
        mp_init();

        for (;;) {
            if (pyexec_mode_kind == PYEXEC_MODE_RAW_REPL) {
                if (pyexec_raw_repl() != 0) {
                    break;
                }
            } else {
                if (pyexec_friendly_repl() != 0) {
                    break;
                }
            }
        }

        mp_printf(&mp_plat_print, "MPY: soft reboot\n");
        zynq_lvgl_deinit();
        gc_sweep_all();
        mp_deinit();
    }
    return 0;
}

// Called from startup.S with stacks, VFP and .bss ready
void zynq_start(void) {
    zynq_mmu_cache_init();
    zynq_timer_init();
    zynq_uart_init();
    mp_main();
}

// LVGL's TLSF pool (zynq.ld): LVGL keeps pointers to Python objects there
// (callbacks, user data), so scan it like a root region. Size 0 without LVGL.
extern void *_lv_pool_start[], *_lv_pool_end[];

void gc_collect(void) {
    gc_collect_start();
    gc_helper_collect_regs_and_stack();
    gc_collect_root(_lv_pool_start, _lv_pool_end - _lv_pool_start);
    gc_collect_end();
}

void nlr_jump_fail(void *val) {
    (void)val;
    static const char msg[] = "\r\nFATAL: uncaught NLR\r\n";
    zynq_uart_tx_strn(msg, sizeof(msg) - 1);
    for (;;) {
    }
}

// ---- Faults: print what happened over UART1, then stop ------------------------------
static void fault_puts(const char *s) {
    while (*s) {
        zynq_uart_tx_strn(s, 1);
        s++;
    }
}

static void fault_puthex(uint32_t v) {
    char buf[11] = "0x";
    for (int i = 0; i < 8; i++) {
        buf[2 + i] = "0123456789abcdef"[(v >> (28 - 4 * i)) & 0xF];
    }
    buf[10] = '\0';
    fault_puts(buf);
}

void zynq_fault(uint32_t kind, uint32_t pc) {
    static const char *const names[] = {
        "?", "undefined instruction", "SVC", "prefetch abort", "data abort", "?", "IRQ", "FIQ",
    };
    uint32_t dfsr, dfar, ifsr, ifar;
    __asm volatile ("mrc p15, 0, %0, c5, c0, 0" : "=r" (dfsr));
    __asm volatile ("mrc p15, 0, %0, c6, c0, 0" : "=r" (dfar));
    __asm volatile ("mrc p15, 0, %0, c5, c0, 1" : "=r" (ifsr));
    __asm volatile ("mrc p15, 0, %0, c6, c0, 2" : "=r" (ifar));

    fault_puts("\r\n*** FATAL: ");
    fault_puts(names[kind & 7]);
    fault_puts(" at pc=");
    fault_puthex(pc);
    if (kind == 4) {
        fault_puts(" addr=");
        fault_puthex(dfar);
        fault_puts(" dfsr=");
        fault_puthex(dfsr);
        if (dfar >= 0x40000000u && dfar < 0x80000000u) {
            fault_puts("\r\n    (PL address: is the bitstream loaded?)");
        }
    } else if (kind == 3) {
        fault_puts(" addr=");
        fault_puthex(ifar);
        fault_puts(" ifsr=");
        fault_puthex(ifsr);
    }
    fault_puts("\r\n*** stopped. Run program.sh again to restart.\r\n");
    zynq_uart_tx_flush();
    for (;;) {
    }
}

// ---- No filesystem: import only finds built-in (and frozen) modules ------------------
mp_lexer_t *mp_lexer_new_from_file(qstr filename) {
    mp_raise_OSError(MP_ENOENT);
}

mp_import_stat_t mp_import_stat(const char *path) {
    (void)path;
    return MP_IMPORT_STAT_NO_EXIST;
}

mp_obj_t mp_builtin_open(size_t n_args, const mp_obj_t *args, mp_map_t *kwargs) {
    (void)n_args;
    (void)args;
    (void)kwargs;
    mp_raise_OSError(MP_ENOENT);
}
MP_DEFINE_CONST_FUN_OBJ_KW(mp_builtin_open_obj, 1, mp_builtin_open);

// ---- libc stubs ---------------------------------------------------------------------
void exit(int status) {
    (void)status;
    for (;;) {
    }
}

void abort(void) {
    nlr_jump_fail(NULL);
    for (;;) {
    }
}

#ifndef NDEBUG
void __assert_func(const char *file, int line, const char *func, const char *expr) {
    (void)func;
    mp_printf(&mp_plat_print, "Assertion '%s' failed, at file %s:%d\n", expr, file, line);
    abort();
}
#endif
