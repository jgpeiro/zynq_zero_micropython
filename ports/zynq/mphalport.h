// SPDX-License-Identifier: MIT
#ifndef MICROPY_INCLUDED_ZYNQ_MPHALPORT_H
#define MICROPY_INCLUDED_ZYNQ_MPHALPORT_H

#include <stddef.h>
#include "shared/runtime/interrupt_char.h"
#include "mmu.h"

// Called by the native emitter after writing machine code
#define MP_HAL_CLEAN_DCACHE(addr, size) zynq_cache_sync_code((addr), (size))

void zynq_timer_init(void);
uint64_t zynq_timer_count(void);

#endif // MICROPY_INCLUDED_ZYNQ_MPHALPORT_H
