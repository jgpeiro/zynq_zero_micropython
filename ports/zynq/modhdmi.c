/*
 * modhdmi.c - _hdmi: framebuffers and the AXI VDMA that scans them out.
 * The user-facing module is modules/hdmi.py.
 *
 *   _hdmi.buffer(i)   bytearray over framebuffer i (0 or 1), 1280x720 RGB565
 *   _hdmi.address(i)  physical address of framebuffer i
 *   _hdmi.init()      reset the VDMA, clear both buffers, start scanning buffer 0
 *   _hdmi.show(i, wait=True)
 *                     write buffer i back from the D-cache to DDR and make the
 *                     VDMA scan it from the next frame; with wait, return only
 *                     once the VDMA has switched (safe to draw into the other one)
 *   _hdmi.flush(i)    only the cache write-back
 *   _hdmi.status()    dict: running, halted, error, frame, mmcm_locked,
 *                     video_locked, underflow, vdma_sr
 *   _hdmi.stop()      halt the VDMA (the monitor loses the picture)
 *   _hdmi.available() True if the VDMA answers (bitstream loaded)
 *
 * The framebuffers sit in their own DDR section (zynq.ld), mapped cacheable:
 * drawing is fast, and show() cleans the cache because HP0 is not coherent.
 *
 * SPDX-License-Identifier: MIT
 */
#include <string.h>

#include "py/runtime.h"
#include "py/mphal.h"
#include "py/mperrno.h"
#include "zynq_regs.h"
#include "mmu.h"

#define HDMI_W          (1280)
#define HDMI_H          (720)
#define HDMI_BPP        (2)
#define HDMI_STRIDE     (HDMI_W * HDMI_BPP)
#define HDMI_FB_SIZE    (HDMI_STRIDE * HDMI_H)
#define HDMI_NUM_FB     (2)

// AXI VDMA (PG020), MM2S channel, register direct mode
#define VDMA(off)           (*(volatile uint32_t *)(ZYNQ_VDMA_BASE + (off)))
#define VDMA_MM2S_CR        (0x00)
#define VDMA_MM2S_SR        (0x04)
#define VDMA_PARK_PTR       (0x28)
#define VDMA_VERSION        (0x2C)
#define VDMA_MM2S_VSIZE     (0x50)
#define VDMA_MM2S_HSIZE     (0x54)
#define VDMA_MM2S_STRIDE    (0x58)
#define VDMA_MM2S_ADDR(n)   (0x5C + 4 * (n))

#define CR_RS               (1u << 0)
#define CR_CIRCULAR         (1u << 1)   // 0 = park on PARK_PTR
#define CR_RESET            (1u << 2)
#define SR_HALTED           (1u << 0)
#define SR_ERRORS           (0x70u)     // internal, slave, decode errors

#define VIDEO_STATUS        (*(volatile uint32_t *)(ZYNQ_VIDEO_STATUS_BASE))

extern uint8_t _fb_start[];

static bool hdmi_running;

bool zynq_hdmi_present(uint32_t i, bool wait);

static uint8_t *fb_ptr(mp_obj_t i_in) {
    mp_int_t i = mp_obj_get_int(i_in);
    if (i < 0 || i >= HDMI_NUM_FB) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuffer index must be 0 or 1"));
    }
    return _fb_start + i * HDMI_FB_SIZE;
}

static bool vdma_present(void) {
    uint32_t v = VDMA(VDMA_VERSION);
    return v != 0 && v != 0xFFFFFFFFu;
}

static mp_obj_t hdmi_available(void) {
    return mp_obj_new_bool(vdma_present());
}
static MP_DEFINE_CONST_FUN_OBJ_0(hdmi_available_obj, hdmi_available);

static mp_obj_t hdmi_buffer(mp_obj_t i_in) {
    return mp_obj_new_bytearray_by_ref(HDMI_FB_SIZE, fb_ptr(i_in));
}
static MP_DEFINE_CONST_FUN_OBJ_1(hdmi_buffer_obj, hdmi_buffer);

static mp_obj_t hdmi_address(mp_obj_t i_in) {
    return mp_obj_new_int_from_uint((uintptr_t)fb_ptr(i_in));
}
static MP_DEFINE_CONST_FUN_OBJ_1(hdmi_address_obj, hdmi_address);

static mp_obj_t hdmi_init(void) {
    if (!vdma_present()) {
        mp_raise_msg(&mp_type_OSError,
            MP_ERROR_TEXT("no VDMA at 0x43000000 (is the HDMI bitstream loaded?)"));
    }

    // Reset the MM2S channel
    VDMA(VDMA_MM2S_CR) = CR_RESET;
    mp_uint_t t0 = mp_hal_ticks_ms();
    while (VDMA(VDMA_MM2S_CR) & CR_RESET) {
        if (mp_hal_ticks_ms() - t0 > 100) {
            mp_raise_OSError(MP_ETIMEDOUT);
        }
    }

    memset(_fb_start, 0, HDMI_NUM_FB * HDMI_FB_SIZE);
    zynq_dcache_clean_range(_fb_start, HDMI_NUM_FB * HDMI_FB_SIZE);

    // PG020 order: run, addresses, stride, hsize, then vsize (which starts it)
    VDMA(VDMA_MM2S_CR) = CR_RS;                       // park mode
    for (int i = 0; i < HDMI_NUM_FB; i++) {
        VDMA(VDMA_MM2S_ADDR(i)) = (uint32_t)(uintptr_t)(_fb_start + i * HDMI_FB_SIZE);
    }
    VDMA(VDMA_PARK_PTR) = 0;
    VDMA(VDMA_MM2S_STRIDE) = HDMI_STRIDE;
    VDMA(VDMA_MM2S_HSIZE) = HDMI_STRIDE;
    VDMA(VDMA_MM2S_VSIZE) = HDMI_H;
    hdmi_running = true;
    return mp_obj_new_int_from_uint(VDMA(VDMA_VERSION));
}
static MP_DEFINE_CONST_FUN_OBJ_0(hdmi_init_obj, hdmi_init);

static mp_obj_t hdmi_flush(mp_obj_t i_in) {
    zynq_dcache_clean_range(fb_ptr(i_in), HDMI_FB_SIZE);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(hdmi_flush_obj, hdmi_flush);

// Write framebuffer i back to DDR and make the VDMA scan it from the next frame.
// With wait, return once the VDMA reads it (then the other buffer is free to draw
// into). Never raises: false means the VDMA didn't switch within 100 ms.
// Also used by the LVGL display driver (usermods/lvgl_hdmi).
bool zynq_hdmi_present(uint32_t i, bool wait) {
    zynq_dcache_clean_range(_fb_start + i * HDMI_FB_SIZE, HDMI_FB_SIZE);
    if (!hdmi_running) {
        return true;
    }
    VDMA(VDMA_PARK_PTR) = i;                           // RdFrmPtrRef, used from the next frame
    if (wait) {
        // PARK_PTR[20:16] = frame the VDMA is reading now
        mp_uint_t t0 = mp_hal_ticks_ms();
        while (((VDMA(VDMA_PARK_PTR) >> 16) & 0x1F) != i) {
            if (mp_hal_ticks_ms() - t0 > 100) {
                return false;
            }
        }
    }
    return true;
}

static mp_obj_t hdmi_show(size_t n_args, const mp_obj_t *args) {
    fb_ptr(args[0]);                                   // validates the index
    uint32_t i = (uint32_t)mp_obj_get_int(args[0]);
    bool wait = n_args < 2 || mp_obj_is_true(args[1]);
    if (!zynq_hdmi_present(i, wait)) {
        mp_raise_OSError(MP_ETIMEDOUT);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(hdmi_show_obj, 1, 2, hdmi_show);

static mp_obj_t hdmi_stop(void) {
    if (vdma_present()) {
        VDMA(VDMA_MM2S_CR) = 0;
    }
    hdmi_running = false;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(hdmi_stop_obj, hdmi_stop);

static mp_obj_t hdmi_status(void) {
    mp_obj_t d = mp_obj_new_dict(8);
    bool present = vdma_present();
    uint32_t sr = present ? VDMA(VDMA_MM2S_SR) : 0;
    uint32_t park = present ? VDMA(VDMA_PARK_PTR) : 0;
    uint32_t vs = present ? VIDEO_STATUS : 0;
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_running), mp_obj_new_bool(hdmi_running));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_halted), mp_obj_new_bool(sr & SR_HALTED));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_error), mp_obj_new_bool(sr & SR_ERRORS));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_frame), MP_OBJ_NEW_SMALL_INT((park >> 16) & 0x1F));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_mmcm_locked), mp_obj_new_bool(vs & 1));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_video_locked), mp_obj_new_bool(vs & 2));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_underflow), mp_obj_new_bool(vs & 4));
    mp_obj_dict_store(d, MP_OBJ_NEW_QSTR(MP_QSTR_vdma_sr), mp_obj_new_int_from_uint(sr));
    return d;
}
static MP_DEFINE_CONST_FUN_OBJ_0(hdmi_status_obj, hdmi_status);

static const mp_rom_map_elem_t hdmi_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__hdmi) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH), MP_ROM_INT(HDMI_W) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT), MP_ROM_INT(HDMI_H) },
    { MP_ROM_QSTR(MP_QSTR_available), MP_ROM_PTR(&hdmi_available_obj) },
    { MP_ROM_QSTR(MP_QSTR_buffer), MP_ROM_PTR(&hdmi_buffer_obj) },
    { MP_ROM_QSTR(MP_QSTR_address), MP_ROM_PTR(&hdmi_address_obj) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&hdmi_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_show), MP_ROM_PTR(&hdmi_show_obj) },
    { MP_ROM_QSTR(MP_QSTR_flush), MP_ROM_PTR(&hdmi_flush_obj) },
    { MP_ROM_QSTR(MP_QSTR_stop), MP_ROM_PTR(&hdmi_stop_obj) },
    { MP_ROM_QSTR(MP_QSTR_status), MP_ROM_PTR(&hdmi_status_obj) },
};
static MP_DEFINE_CONST_DICT(hdmi_module_globals, hdmi_module_globals_table);

const mp_obj_module_t mp_module__hdmi = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&hdmi_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR__hdmi, mp_module__hdmi);
