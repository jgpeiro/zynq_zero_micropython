/*
 * zynq_regs.h - Zynq-7000 registers used by the MicroPython port (UG585 app. B)
 * and the AXI GPIO in the PL (PG144).
 *
 * SPDX-License-Identifier: MIT
 */
#ifndef MICROPY_INCLUDED_ZYNQ_REGS_H
#define MICROPY_INCLUDED_ZYNQ_REGS_H

#include <stdint.h>

#define REG32(addr) (*(volatile uint32_t *)(uintptr_t)(addr))

// ---- Clocks (must match hw/scripts/ps7_config.tcl) -----------------------------
#ifndef ZYNQ_CPU_HZ
#define ZYNQ_CPU_HZ         (666666667u)    // PCW_APU_PERIPHERAL_FREQMHZ
#endif
#ifndef ZYNQ_UART_REF_HZ
#define ZYNQ_UART_REF_HZ    (100000000u)    // PCW_UART_PERIPHERAL_FREQMHZ
#endif
#define ZYNQ_GTIMER_HZ      (ZYNQ_CPU_HZ / 2u)  // global timer runs at CPU_3x2x

// ---- SLCR ------------------------------------------------------------------------
#define SLCR_BASE           (0xF8000000u)
#define SLCR_LOCK           REG32(SLCR_BASE + 0x004)
#define SLCR_UNLOCK         REG32(SLCR_BASE + 0x008)
#define SLCR_LOCK_KEY       (0x767Bu)
#define SLCR_UNLOCK_KEY     (0xDF0Du)
#define SLCR_APER_CLK_CTRL  REG32(SLCR_BASE + 0x12C)
#define APER_GPIO_CLKACT    (1u << 22)
#define SLCR_PSS_RST_CTRL   REG32(SLCR_BASE + 0x200)
#define SLCR_REBOOT_STATUS  REG32(SLCR_BASE + 0x258)
#define SLCR_PSS_IDCODE     REG32(SLCR_BASE + 0x530)
#define SLCR_MIO_PIN(n)     REG32(SLCR_BASE + 0x700 + 4u * (n))
#define MIO_IO_LVCMOS33     (3u << 9)

// ---- PS GPIO (bank 0 = MIO0-31) ----------------------------------------------------
#define GPIO_BASE           (0xE000A000u)
#define GPIO_MASK_DATA_0_LSW REG32(GPIO_BASE + 0x000)  // [31:16] mask (0 = write), [15:0] data
#define GPIO_DATA_0         REG32(GPIO_BASE + 0x040)
#define GPIO_DATA_0_RO      REG32(GPIO_BASE + 0x060)
#define GPIO_DIRM_0         REG32(GPIO_BASE + 0x204)
#define GPIO_OEN_0          REG32(GPIO_BASE + 0x208)

// ---- ARM global timer ----------------------------------------------------------------
#define GTIMER_BASE         (0xF8F00200u)
#define GTIMER_COUNT_LO     REG32(GTIMER_BASE + 0x00)
#define GTIMER_COUNT_HI     REG32(GTIMER_BASE + 0x04)
#define GTIMER_CTRL         REG32(GTIMER_BASE + 0x08)
#define GTIMER_CTRL_ENABLE  (1u << 0)

// ---- UART1 (MIO48 TX / MIO49 RX -> CH340) ---------------------------------------------
#define UART1_BASE          (0xE0001000u)
#define UART_CR             REG32(UART1_BASE + 0x00)
#define UART_MR             REG32(UART1_BASE + 0x04)
#define UART_IDR            REG32(UART1_BASE + 0x0C)
#define UART_BAUDGEN        REG32(UART1_BASE + 0x18)
#define UART_SR             REG32(UART1_BASE + 0x2C)
#define UART_FIFO           REG32(UART1_BASE + 0x30)
#define UART_BAUDDIV        REG32(UART1_BASE + 0x34)
#define UART_CR_RXRST       (1u << 0)
#define UART_CR_TXRST       (1u << 1)
#define UART_CR_RXEN        (1u << 2)
#define UART_CR_RXDIS       (1u << 3)
#define UART_CR_TXEN        (1u << 4)
#define UART_CR_TXDIS       (1u << 5)
#define UART_MR_8N1         (4u << 3)       // PAR = 1xx (none), CHRL = 8 bit, 1 stop
#define UART_SR_RXEMPTY     (1u << 1)
#define UART_SR_TXEMPTY     (1u << 3)
#define UART_SR_TXFULL      (1u << 4)

// ---- AXI GPIO in the PL (M_AXI_GP0), see hw/scripts/build.tcl --------------------------
#ifndef ZYNQ_AXI_GPIO_BASE
#define ZYNQ_AXI_GPIO_BASE  (0x41200000u)
#endif
#define AXI_GPIO_DATA       REG32(ZYNQ_AXI_GPIO_BASE + 0x0)   // channel 1: LED1..LED4
#define AXI_GPIO_TRI        REG32(ZYNQ_AXI_GPIO_BASE + 0x4)
#define AXI_GPIO2_DATA      REG32(ZYNQ_AXI_GPIO_BASE + 0x8)   // channel 2: KEY1
#define AXI_GPIO2_TRI       REG32(ZYNQ_AXI_GPIO_BASE + 0xC)

// ---- HDMI video path in the PL (see hw/scripts/build.tcl) ------------------------------
#define ZYNQ_VDMA_BASE          (0x43000000u)   // axi_vdma_0 (MM2S only)
#define ZYNQ_VIDEO_STATUS_BASE  (0x41210000u)   // axi_gpio_video: bit0 MMCM locked,
                                                // bit1 vid_out locked, bit2 underflow

#endif // MICROPY_INCLUDED_ZYNQ_REGS_H
