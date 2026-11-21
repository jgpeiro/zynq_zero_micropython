/*
 * uart.c - Polled Cadence UART1 driver for the REPL (115200 8N1).
 *
 * There are no interrupts in this port. While Python code runs, the VM calls
 * zynq_uart_poll() every few bytecodes (MICROPY_VM_HOOK_LOOP) and from delays
 * (MICROPY_INTERNAL_EVENT_HOOK). It moves received bytes into a ring buffer and
 * turns Ctrl-C into a KeyboardInterrupt.
 *
 * SPDX-License-Identifier: MIT
 */
#include "py/runtime.h"
#include "shared/runtime/interrupt_char.h"
#include "zynq_regs.h"
#include "uart.h"

#define BAUD        (115200u)
#define RXBUF_SIZE  (512u)          // power of 2

static uint8_t rxbuf[RXBUF_SIZE];
static volatile uint32_t rx_head, rx_tail;

void zynq_uart_init(void) {
    // baud = ref / (CD * (BDIV + 1)); BDIV = 6 -> CD = ref / (7 * baud)
    const uint32_t bdiv = 6u;
    const uint32_t cd = (ZYNQ_UART_REF_HZ + (bdiv + 1u) * BAUD / 2u) / ((bdiv + 1u) * BAUD);

    UART_IDR = 0xFFFFFFFFu;
    UART_CR = UART_CR_TXDIS | UART_CR_RXDIS;
    UART_MR = UART_MR_8N1;
    UART_BAUDGEN = cd;
    UART_BAUDDIV = bdiv;
    UART_CR = UART_CR_TXRST | UART_CR_RXRST;
    while (UART_CR & (UART_CR_TXRST | UART_CR_RXRST)) {
    }
    UART_CR = UART_CR_TXEN | UART_CR_RXEN;
    rx_head = rx_tail = 0;
}

static inline bool hw_rx_any(void) {
    return !(UART_SR & UART_SR_RXEMPTY);
}

void zynq_uart_tx_strn(const char *str, size_t len) {
    while (len--) {
        while (UART_SR & UART_SR_TXFULL) {
        }
        UART_FIFO = (uint8_t)*str++;
    }
}

void zynq_uart_tx_flush(void) {
    while (!(UART_SR & UART_SR_TXEMPTY)) {
    }
}

void zynq_uart_poll(void) {
    while (hw_rx_any()) {
        int c = (uint8_t)UART_FIFO;
        if (c == mp_interrupt_char) {
            // Drop anything typed before Ctrl-C, like the other ports do
            rx_tail = rx_head;
            mp_sched_keyboard_interrupt();
            continue;
        }
        uint32_t next = (rx_head + 1u) & (RXBUF_SIZE - 1u);
        if (next != rx_tail) {
            rxbuf[rx_head] = (uint8_t)c;
            rx_head = next;
        }
    }
}

bool zynq_uart_rx_any(void) {
    return rx_head != rx_tail || hw_rx_any();
}

int zynq_uart_rx_chr(void) {
    // Buffered bytes first (collected while code was running), then the FIFO.
    // Reading the FIFO directly keeps Ctrl-C a plain character for readline.
    if (rx_head != rx_tail) {
        int c = rxbuf[rx_tail];
        rx_tail = (rx_tail + 1u) & (RXBUF_SIZE - 1u);
        return c;
    }
    if (hw_rx_any()) {
        return (uint8_t)UART_FIFO;
    }
    return -1;
}
