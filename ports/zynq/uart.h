// SPDX-License-Identifier: MIT
#ifndef MICROPY_INCLUDED_ZYNQ_UART_H
#define MICROPY_INCLUDED_ZYNQ_UART_H

#include <stdbool.h>
#include <stddef.h>

void zynq_uart_init(void);
void zynq_uart_tx_strn(const char *str, size_t len);
void zynq_uart_tx_flush(void);
void zynq_uart_poll(void);
bool zynq_uart_rx_any(void);
int zynq_uart_rx_chr(void);   // -1 if nothing available

#endif // MICROPY_INCLUDED_ZYNQ_UART_H
