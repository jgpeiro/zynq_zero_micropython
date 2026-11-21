/*
 * mphalport.c - stdio over UART1 and time from the ARM global timer.
 *
 * SPDX-License-Identifier: MIT
 */
#include "py/mphal.h"
#include "py/runtime.h"
#include "py/stream.h"
#include "zynq_regs.h"
#include "uart.h"

// ---- Global timer ------------------------------------------------------------------
void zynq_timer_init(void) {
    if (!(GTIMER_CTRL & GTIMER_CTRL_ENABLE)) {
        GTIMER_CTRL = GTIMER_CTRL_ENABLE;          // prescaler 0
    }
}

uint64_t zynq_timer_count(void) {
    uint32_t hi, lo;
    do {
        hi = GTIMER_COUNT_HI;
        lo = GTIMER_COUNT_LO;
    } while (hi != GTIMER_COUNT_HI);
    return ((uint64_t)hi << 32) | lo;
}

// count * scale / ZYNQ_GTIMER_HZ without 64-bit overflow
static uint64_t timer_scaled(uint32_t scale) {
    uint64_t c = zynq_timer_count();
    uint64_t whole = c / ZYNQ_GTIMER_HZ;
    uint64_t frac = c % ZYNQ_GTIMER_HZ;
    return whole * scale + frac * scale / ZYNQ_GTIMER_HZ;
}

mp_uint_t mp_hal_ticks_ms(void) {
    return (mp_uint_t)timer_scaled(1000u);
}

mp_uint_t mp_hal_ticks_us(void) {
    return (mp_uint_t)timer_scaled(1000000u);
}

mp_uint_t mp_hal_ticks_cpu(void) {
    return (mp_uint_t)zynq_timer_count();
}

void mp_hal_delay_ms(mp_uint_t ms) {
    mp_uint_t start = mp_hal_ticks_ms();
    do {
        mp_event_handle_nowait();               // polls UART, runs scheduled callbacks
    } while (mp_hal_ticks_ms() - start < ms);
}

void mp_hal_delay_us(mp_uint_t us) {
    uint64_t end = zynq_timer_count() + (uint64_t)us * (ZYNQ_GTIMER_HZ / 1000000u);
    while ((int64_t)(zynq_timer_count() - end) < 0) {
    }
}

uint32_t zynq_random_seed(void) {
    return (uint32_t)zynq_timer_count();
}

// ---- stdio -------------------------------------------------------------------------
uintptr_t mp_hal_stdio_poll(uintptr_t poll_flags) {
    uintptr_t ret = 0;
    zynq_uart_poll();
    if ((poll_flags & MP_STREAM_POLL_RD) && zynq_uart_rx_any()) {
        ret |= MP_STREAM_POLL_RD;
    }
    if (poll_flags & MP_STREAM_POLL_WR) {
        ret |= MP_STREAM_POLL_WR;
    }
    return ret;
}

int mp_hal_stdin_rx_chr(void) {
    for (;;) {
        int c = zynq_uart_rx_chr();
        if (c >= 0) {
            return c;
        }
        mp_event_handle_nowait();
    }
}

mp_uint_t mp_hal_stdout_tx_strn(const char *str, size_t len) {
    zynq_uart_tx_strn(str, len);
    return len;
}
