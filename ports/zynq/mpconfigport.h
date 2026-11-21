/*
 * mpconfigport.h - MicroPython configuration for the Zynq-7000 (ZYNQ ZERO).
 *
 * SPDX-License-Identifier: MIT
 */
#include <stdint.h>

// ---- Board ---------------------------------------------------------------------
#define MICROPY_HW_BOARD_NAME       "ZYNQ ZERO"
#define MICROPY_HW_MCU_NAME         "XC7Z010 Cortex-A9"
#define MICROPY_PY_SYS_PLATFORM     "zynq"

// ---- Core features ---------------------------------------------------------------
#define MICROPY_CONFIG_ROM_LEVEL    (MICROPY_CONFIG_ROM_LEVEL_EXTRA_FEATURES)
#define MICROPY_ENABLE_GC           (1)
#define MICROPY_ENABLE_EMERGENCY_EXCEPTION_BUF (1)
#define MICROPY_LONGINT_IMPL        (MICROPY_LONGINT_IMPL_MPZ)
#define MICROPY_FLOAT_IMPL          (MICROPY_FLOAT_IMPL_DOUBLE)
#define MICROPY_HW_FPU              (1)
#define MICROPY_WARNINGS            (1)
#define MICROPY_KBD_EXCEPTION       (1)
#define MICROPY_ENABLE_SCHEDULER    (1)
#define MICROPY_MALLOC_USES_ALLOCATED_SIZE (1)
#define MICROPY_MEM_STATS           (1)

// Native code emitters (@micropython.native / @micropython.viper), ARM mode
#define MICROPY_EMIT_ARM            (1)

// No filesystem: code comes from the REPL (paste mode Ctrl-E, or mpremote run)
#define MICROPY_VFS                 (0)
#define MICROPY_READER_VFS          (0)

// ---- Modules ----------------------------------------------------------------------
#define MICROPY_PY_MACHINE          (1)
#define MICROPY_PY_MACHINE_INCLUDEFILE "zynq_modmachine.c"
#define MICROPY_PY_MACHINE_RESET    (1)
#define MICROPY_PY_MACHINE_BARE_METAL_FUNCS (1)
#define MICROPY_PY_MACHINE_PIN_BASE (1)
#define MICROPY_PY_MACHINE_PIN_MAKE_NEW mp_pin_make_new
#define MICROPY_PY_MACHINE_EXTRA_GLOBALS \
    { MP_ROM_QSTR(MP_QSTR_Pin), MP_ROM_PTR(&machine_pin_type) },
#define MICROPY_PY_RANDOM_SEED_INIT_FUNC (zynq_random_seed())
#define MICROPY_PY_OS_UNAME         (1)

// ---- Polling UART for Ctrl-C (no interrupts in this port) -------------------------
// Poll the UART every 64 backward jumps/calls while Python code runs ...
#define MICROPY_VM_HOOK_COUNT       (64)
#define MICROPY_VM_HOOK_INIT        static unsigned int vm_hook_divisor = MICROPY_VM_HOOK_COUNT;
#define MICROPY_VM_HOOK_POLL        if (--vm_hook_divisor == 0) { \
        vm_hook_divisor = MICROPY_VM_HOOK_COUNT; \
        extern void zynq_uart_poll(void); \
        zynq_uart_poll(); \
}
#define MICROPY_VM_HOOK_LOOP        MICROPY_VM_HOOK_POLL
#define MICROPY_VM_HOOK_RETURN      MICROPY_VM_HOOK_POLL
// ... and while sleeping / waiting for events
#define MICROPY_INTERNAL_EVENT_HOOK do { \
        extern void zynq_uart_poll(void); \
        zynq_uart_poll(); \
} while (0)

// ---- Type definitions ---------------------------------------------------------------
#define MP_SSIZE_MAX                (0x7fffffff)
typedef long mp_off_t;

#include <alloca.h>

// libm_dbl needs a non-macro log2
#define MP_NEED_LOG2                (1)

#define MP_STATE_PORT               MP_STATE_VM

uint32_t zynq_random_seed(void);
