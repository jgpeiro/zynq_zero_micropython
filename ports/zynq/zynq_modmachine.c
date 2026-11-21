/*
 * zynq_modmachine.c - Port part of the machine module.
 * Never compiled on its own: included by extmod/modmachine.c through
 * MICROPY_PY_MACHINE_INCLUDEFILE.
 *
 * SPDX-License-Identifier: MIT
 */
#include "py/mphal.h"
#include "zynq_regs.h"
#include "uart.h"

static void mp_machine_idle(void) {
    zynq_uart_poll();
}

MP_NORETURN static void mp_machine_reset(void) {
    // Full PS system reset. In JTAG boot mode the board then waits in the
    // BootROM: run program.sh again to reload everything.
    zynq_uart_tx_flush();
    SLCR_UNLOCK = SLCR_UNLOCK_KEY;
    SLCR_PSS_RST_CTRL = 1;
    for (;;) {
    }
}

static mp_int_t mp_machine_reset_cause(void) {
    // REBOOT_STATUS bits 16..22: SWDT, AWDT0, AWDT1, SLC, BOOTROM, POR, SRST_B
    return (mp_int_t)((SLCR_REBOOT_STATUS >> 16) & 0x7F);
}

static mp_obj_t mp_machine_unique_id(void) {
    // The PS has no serial number; return the device IDCODE.
    uint32_t id = SLCR_PSS_IDCODE;
    uint8_t buf[4] = { id >> 24, id >> 16, id >> 8, id };
    return mp_obj_new_bytes(buf, sizeof(buf));
}

static mp_obj_t mp_machine_get_freq(void) {
    return mp_obj_new_int_from_uint(ZYNQ_CPU_HZ);
}

static void mp_machine_set_freq(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    (void)args;
    mp_raise_NotImplementedError(MP_ERROR_TEXT("CPU clock is set by ps7_init"));
}

static void mp_machine_lightsleep(size_t n_args, const mp_obj_t *args) {
    if (n_args > 0) {
        mp_hal_delay_ms(mp_obj_get_int(args[0]));
    }
}

MP_NORETURN static void mp_machine_deepsleep(size_t n_args, const mp_obj_t *args) {
    mp_machine_lightsleep(n_args, args);
    mp_machine_reset();
}
