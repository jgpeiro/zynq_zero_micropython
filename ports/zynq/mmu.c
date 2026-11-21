/*
 * mmu.c - Flat (VA = PA) MMU map and L1 caches for the Cortex-A9.
 *
 *   0x0000_0000 - 0x3FFF_FFFF  DDR + low OCM   normal, write-back write-allocate
 *   0x4000_0000 - 0xBFFF_FFFF  PL (GP0/GP1)    strongly-ordered, execute-never
 *                              (as in Xilinx's translation table: a PL register read
 *                              can't overtake an earlier PL register write)
 *   0xC000_0000 - 0xFFEF_FFFF  PS peripherals  device, execute-never
 *   0xFFF0_0000 - 0xFFFF_FFFF  high OCM        normal, cacheable
 *
 * The HDMI framebuffers (_fb_start.._fb_end, see zynq.ld) are inner write-back
 * but outer NON-cacheable: they are cached in L1 only, so the L1 clean in
 * zynq_dcache_clean_range() is enough to make them visible to the VDMA.
 *
 * The 512 KB L2 cache (PL310) is enabled with Xilinx's standard settings, as
 * the Xilinx standalone BSP does; without it every L1 miss goes to the 16-bit
 * DDR3. Build with ZYNQ_L2=0 to leave it off, or with ZYNQ_MMU=0 to run with only
 * the I-cache (no MMU, no D-cache, no L2), e.g. to rule out cache problems.
 *
 * SPDX-License-Identifier: MIT
 */
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include "mmu.h"

#ifndef ZYNQ_MMU
#define ZYNQ_MMU (1)
#endif

#define SECT            (2u << 0)
#define SECT_B          (1u << 2)
#define SECT_C          (1u << 3)
#define SECT_XN         (1u << 4)
#define SECT_AP_RW      (3u << 10)
#define SECT_TEX(x)     ((uint32_t)(x) << 12)

#define SECT_NORMAL_WBWA (SECT | SECT_AP_RW | SECT_TEX(1) | SECT_C | SECT_B)
// TEX = 1xx: outer policy TEX[1:0] = 00 (non-cacheable), inner C,B = 01 (WB-WA)
#define SECT_INNER_WB_OUTER_NC (SECT | SECT_AP_RW | SECT_TEX(4) | SECT_B)
#define SECT_DEVICE      (SECT | SECT_AP_RW | SECT_B | SECT_XN)  // shareable device
#define SECT_STRONG      (SECT | SECT_AP_RW | SECT_XN)           // strongly-ordered

#define SCTLR_M         (1u << 0)
#define SCTLR_A         (1u << 1)
#define SCTLR_C         (1u << 2)
#define SCTLR_Z         (1u << 11)
#define SCTLR_I         (1u << 12)

#define L1_LINE         (32u)

#ifndef ZYNQ_L2
#define ZYNQ_L2 (1)
#endif

#if ZYNQ_MMU
static uint32_t ttb[4096] __attribute__((aligned(16384)));
extern uint8_t _fb_start[], _fb_end[];   // zynq.ld
#endif

// ---- PL310 L2 cache controller (Zynq TRM UG585 ch. 3.4, Xilinx xil_cache.c) ----------
#define L2CC_BASE           (0xF8F02000u)
#define L2CC(off)           (*(volatile uint32_t *)(L2CC_BASE + (off)))
#define L2CC_CNTRL          (0x100)
#define L2CC_AUX_CNTRL      (0x104)
#define L2CC_TAG_RAM        (0x108)
#define L2CC_DATA_RAM       (0x10C)
#define L2CC_INT_RAW        (0x21C)
#define L2CC_INT_CLEAR      (0x220)
#define L2CC_CACHE_SYNC     (0x730)
#define L2CC_INV_WAY        (0x77C)
#define SLCR_UNLOCK_REG     (*(volatile uint32_t *)0xF8000008u)
#define SLCR_LOCK_REG       (*(volatile uint32_t *)0xF8000004u)
#define SLCR_L2C_RAM        (*(volatile uint32_t *)0xF8000A1Cu)

#if ZYNQ_MMU && ZYNQ_L2
static void l2_enable(void) {
    // Still on from a previous run (JTAG reload without power cycle): its lines
    // belong to the old image, so drop them without writing back, as is done
    // for L1 above. Called with the L1 D-cache freshly invalidated.
    if (L2CC(L2CC_CNTRL) & 1) {
        L2CC(L2CC_CNTRL) = 0;
        __asm volatile ("dsb" ::: "memory");
    }
    // L2 RAM latency setting the TRM requires before enabling
    SLCR_UNLOCK_REG = 0xDF0D;
    SLCR_L2C_RAM = 0x00020202;
    SLCR_LOCK_REG = 0x767B;
    // 8-way, 64 KB ways, I/D prefetch, early BRESP (Xilinx defaults)
    L2CC(L2CC_AUX_CNTRL) = (L2CC(L2CC_AUX_CNTRL) & 0xFFF1FFFFu) | 0x72360000u;
    L2CC(L2CC_TAG_RAM) = 0x111;
    L2CC(L2CC_DATA_RAM) = 0x121;
    L2CC(L2CC_INT_CLEAR) = L2CC(L2CC_INT_RAW);
    // Invalidate all ways
    L2CC(L2CC_INV_WAY) = 0xFFFF;
    while (L2CC(L2CC_INV_WAY) & 0xFFFF) {
    }
    L2CC(L2CC_CACHE_SYNC) = 0;
    while (L2CC(L2CC_CACHE_SYNC) & 1) {
    }
    L2CC(L2CC_CNTRL) = 1;
    __asm volatile ("dsb" ::: "memory");
}
#endif

bool zynq_l2_enabled(void) {
    #if ZYNQ_MMU && ZYNQ_L2
    return L2CC(L2CC_CNTRL) & 1;
    #else
    return false;
    #endif
}

static inline void dsb(void) {
    __asm volatile ("dsb" ::: "memory");
}
static inline void isb(void) {
    __asm volatile ("isb" ::: "memory");
}

static inline uint32_t sctlr_read(void) {
    uint32_t v;
    __asm volatile ("mrc p15, 0, %0, c1, c0, 0" : "=r" (v));
    return v;
}
static inline void sctlr_write(uint32_t v) {
    __asm volatile ("mcr p15, 0, %0, c1, c0, 0" :: "r" (v) : "memory");
    isb();
}

static void icache_bp_invalidate_all(void) {
    __asm volatile ("mcr p15, 0, %0, c7, c5, 0" :: "r" (0) : "memory");  // ICIALLU
    __asm volatile ("mcr p15, 0, %0, c7, c5, 6" :: "r" (0) : "memory");  // BPIALL
    dsb();
    isb();
}

#if ZYNQ_MMU
// Invalidate (no clean) the whole L1 D-cache: 32 KB, 4 ways, 32-byte lines.
static void dcache_invalidate_all(void) {
    for (uint32_t way = 0; way < 4; way++) {
        for (uint32_t set = 0; set < 256; set++) {
            uint32_t sw = (way << 30) | (set << 5);
            __asm volatile ("mcr p15, 0, %0, c7, c6, 2" :: "r" (sw) : "memory");  // DCISW
        }
    }
    dsb();
}
#endif

void zynq_mmu_cache_init(void) {
    #if ZYNQ_MMU
    uint32_t fb_first = (uint32_t)(uintptr_t)_fb_start >> 20;
    uint32_t fb_last = ((uint32_t)(uintptr_t)_fb_end - 1) >> 20;
    for (uint32_t i = 0; i < 4096; i++) {
        uint32_t base = i << 20;
        if (i >= fb_first && i <= fb_last) {
            ttb[i] = base | SECT_INNER_WB_OUTER_NC;      // HDMI framebuffers: L1 only
        } else if (i < 0x400 || i == 0xFFF) {
            ttb[i] = base | SECT_NORMAL_WBWA;
        } else if (i < 0xC00) {
            ttb[i] = base | SECT_STRONG;
        } else {
            ttb[i] = base | SECT_DEVICE;
        }
    }
    dsb();

    __asm volatile ("mcr p15, 0, %0, c8, c7, 0" :: "r" (0) : "memory");      // TLBIALL
    dcache_invalidate_all();
    icache_bp_invalidate_all();

    __asm volatile ("mcr p15, 0, %0, c3, c0, 0" :: "r" (0x55555555u));       // DACR: all client
    __asm volatile ("mcr p15, 0, %0, c2, c0, 2" :: "r" (0));                 // TTBCR: TTBR0 only
    __asm volatile ("mcr p15, 0, %0, c2, c0, 0" :: "r" ((uint32_t)ttb));     // TTBR0, walks uncached
    dsb();
    isb();

    uint32_t sctlr = sctlr_read();
    sctlr &= ~SCTLR_A;
    sctlr |= SCTLR_M | SCTLR_C | SCTLR_I | SCTLR_Z;
    sctlr_write(sctlr);

    #if ZYNQ_L2
    l2_enable();
    #endif
    #else
    icache_bp_invalidate_all();
    uint32_t sctlr = sctlr_read();
    sctlr &= ~SCTLR_A;
    sctlr |= SCTLR_I | SCTLR_Z;
    sctlr_write(sctlr);
    #endif
}

// Make freshly written code (native emitter / viper) visible to instruction fetch.
void zynq_cache_sync_code(const void *addr, size_t len) {
    #if ZYNQ_MMU
    uintptr_t a = (uintptr_t)addr & ~(uintptr_t)(L1_LINE - 1);
    uintptr_t end = (uintptr_t)addr + len;
    for (; a < end; a += L1_LINE) {
        __asm volatile ("mcr p15, 0, %0, c7, c11, 1" :: "r" (a) : "memory");  // DCCMVAU
    }
    dsb();
    #else
    (void)addr;
    (void)len;
    #endif
    icache_bp_invalidate_all();
}

// Write dirty cache lines in [addr, addr+len) back to DDR so that a DMA master
// on a non-coherent port (e.g. the HDMI VDMA on HP0) sees what the CPU wrote.
void zynq_dcache_clean_range(const void *addr, size_t len) {
    #if ZYNQ_MMU
    uintptr_t a = (uintptr_t)addr & ~(uintptr_t)(L1_LINE - 1);
    uintptr_t end = (uintptr_t)addr + len;
    for (; a < end; a += L1_LINE) {
        __asm volatile ("mcr p15, 0, %0, c7, c10, 1" :: "r" (a) : "memory");  // DCCMVAC
    }
    dsb();
    #else
    (void)addr;
    (void)len;
    #endif
}
