/*
 * modzynq.c - zynq: what the CPU is actually running with.
 *
 *   zynq.info() -> dict: mmu, dcache, icache, branch_pred, l2,
 *                  sctlr, actlr, cpu_hz
 *
 * Useful to check performance problems on the board: everything should be True.
 *
 * SPDX-License-Identifier: MIT
 */
#include "py/runtime.h"
#include "zynq_regs.h"
#include "mmu.h"

static void store(mp_obj_t d, qstr k, mp_obj_t v) {
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(k), v);
}

static mp_obj_t zynq_info(void) {
    uint32_t sctlr, actlr;
    __asm volatile ("mrc p15, 0, %0, c1, c0, 0" : "=r" (sctlr));
    __asm volatile ("mrc p15, 0, %0, c1, c0, 1" : "=r" (actlr));
    mp_obj_t d = mp_obj_new_dict(8);
    store(d, MP_QSTR_mmu, mp_obj_new_bool(sctlr & (1u << 0)));
    store(d, MP_QSTR_dcache, mp_obj_new_bool(sctlr & (1u << 2)));
    store(d, MP_QSTR_icache, mp_obj_new_bool(sctlr & (1u << 12)));
    store(d, MP_QSTR_branch_pred, mp_obj_new_bool(sctlr & (1u << 11)));
    store(d, MP_QSTR_l2, mp_obj_new_bool(zynq_l2_enabled()));
    store(d, MP_QSTR_sctlr, mp_obj_new_int_from_uint(sctlr));
    store(d, MP_QSTR_actlr, mp_obj_new_int_from_uint(actlr));
    store(d, MP_QSTR_cpu_hz, mp_obj_new_int_from_uint(ZYNQ_CPU_HZ));
    return d;
}
static MP_DEFINE_CONST_FUN_OBJ_0(zynq_info_obj, zynq_info);

static const mp_rom_map_elem_t zynq_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_zynq) },
    { MP_ROM_QSTR(MP_QSTR_info), MP_ROM_PTR(&zynq_info_obj) },
};
static MP_DEFINE_CONST_DICT(zynq_module_globals, zynq_module_globals_table);

const mp_obj_module_t mp_module_zynq = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&zynq_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_zynq, mp_module_zynq);
