// SPDX-License-Identifier: MIT
#ifndef MICROPY_INCLUDED_ZYNQ_MMU_H
#define MICROPY_INCLUDED_ZYNQ_MMU_H

#include <stdbool.h>
#include <stddef.h>

void zynq_mmu_cache_init(void);
void zynq_cache_sync_code(const void *addr, size_t len);
void zynq_dcache_clean_range(const void *addr, size_t len);
bool zynq_l2_enabled(void);

#endif // MICROPY_INCLUDED_ZYNQ_MMU_H
