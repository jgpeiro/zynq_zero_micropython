/*
 * lvgl_hdmi.c - _lvhdmi: LVGL v9 display driver for the ZYNQ ZERO HDMI output.
 *
 * LVGL renders straight into the two HDMI framebuffers (1280x720 RGB565, the
 * same memory the AXI VDMA scans out), in DIRECT render mode with double
 * buffering: no copies. When the last area of a frame is flushed, the driver
 * writes the buffer back from the D-cache and parks the VDMA on it, waiting
 * for the switch, so LVGL never draws into the buffer on screen (no tearing,
 * at most 60 fps). LVGL itself keeps the two buffers in sync in this mode.
 *
 *   _lvhdmi.create()   lv_display for 1280x720 on the HDMI framebuffers,
 *                      set as default; get it with lv.display_get_default()
 *   _lvhdmi.frames()   number of frames presented so far
 *   _lvhdmi.stats(reset=False)  (frames, areas, pixels, tick_calls, present_ms,
 *                      full_redraws): what LVGL redraws, for performance checks
 *   _lvhdmi.mem()      (total, used, frag_pct) of LVGL's memory pool
 *
 * Call lv.init() first, and _hdmi.init() (or hdmi.Display()) to start the
 * video output; without it the driver still renders, e.g. in QEMU.
 * The LVGL tick comes from the global timer (mp_hal_ticks_ms).
 *
 * SPDX-License-Identifier: MIT
 */
#include "py/runtime.h"
#include "py/mphal.h"
#include "lvgl/lvgl.h"
#include "mmu.h"
#include "mphalport.h"
#include "zynq_regs.h"

#define HDMI_W          (1280)
#define HDMI_H          (720)
#define HDMI_FB_SIZE    (HDMI_W * HDMI_H * 2)

extern uint8_t _fb_start[];                             // zynq.ld
bool zynq_hdmi_present(uint32_t i, bool wait);          // modhdmi.c

static lv_display_t *hdmi_disp;
static uint32_t hdmi_frames;

// Counters for _lvhdmi.stats()
static struct {
    uint32_t areas;             // flushed areas
    uint64_t pixels;            // flushed pixels
    uint32_t ticks;             // tick_cb calls
    uint64_t present_cycles;    // global-timer counts spent in zynq_hdmi_present
    uint32_t full_frames;       // frames that redrew >= 90% of the screen
    uint32_t frame_px;          // pixels flushed so far in the current frame
} st;

static uint32_t tick_cb(void) {
    st.ticks++;
    return (uint32_t)mp_hal_ticks_ms();
}

static void flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map) {
    uint32_t px = (uint32_t)(lv_area_get_width(area) * lv_area_get_height(area));
    st.areas++;
    st.pixels += px;
    st.frame_px += px;
    // DIRECT mode: px_map is the start of the framebuffer LVGL drew into
    if (lv_display_flush_is_last(disp)) {
        uint32_t i = (px_map >= _fb_start + HDMI_FB_SIZE) ? 1 : 0;
        uint64_t t0 = zynq_timer_count();
        // Whole buffer: besides the flushed areas, LVGL copied the previous
        // frame's dirty areas into it (buffer sync), and those must reach DDR too.
        zynq_hdmi_present(i, true);
        st.present_cycles += zynq_timer_count() - t0;
        hdmi_frames++;
        if (st.frame_px >= HDMI_W * HDMI_H / 10 * 9) {
            st.full_frames++;
        }
        st.frame_px = 0;
    }
    lv_display_flush_ready(disp);
}

static mp_obj_t lvhdmi_create(void) {
    if (!lv_is_initialized()) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("call lv.init() first"));
    }
    lv_tick_set_cb(tick_cb);
    if (hdmi_disp == NULL) {
        hdmi_disp = lv_display_create(HDMI_W, HDMI_H);
        lv_display_set_color_format(hdmi_disp, LV_COLOR_FORMAT_RGB565);
        lv_display_set_buffers(hdmi_disp, _fb_start, _fb_start + HDMI_FB_SIZE, HDMI_FB_SIZE,
            LV_DISPLAY_RENDER_MODE_DIRECT);
        lv_display_set_flush_cb(hdmi_disp, flush_cb);
        hdmi_frames = 0;
    }
    lv_display_set_default(hdmi_disp);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(lvhdmi_create_obj, lvhdmi_create);

static mp_obj_t lvhdmi_frames(void) {
    return mp_obj_new_int_from_uint(hdmi_frames);
}
static MP_DEFINE_CONST_FUN_OBJ_0(lvhdmi_frames_obj, lvhdmi_frames);

// _lvhdmi.stats(reset=False) -> (frames, areas, pixels, tick_calls, present_ms, full_redraws)
static mp_obj_t lvhdmi_stats(size_t n_args, const mp_obj_t *args) {
    mp_obj_t t[6] = {
        mp_obj_new_int_from_uint(hdmi_frames),
        mp_obj_new_int_from_uint(st.areas),
        mp_obj_new_int_from_ull(st.pixels),
        mp_obj_new_int_from_uint(st.ticks),
        mp_obj_new_int_from_ull(st.present_cycles / (ZYNQ_GTIMER_HZ / 1000)),
        mp_obj_new_int_from_uint(st.full_frames),
    };
    if (n_args > 0 && mp_obj_is_true(args[0])) {
        st.areas = 0;
        st.pixels = 0;
        st.ticks = 0;
        st.present_cycles = 0;
        st.full_frames = 0;
    }
    return mp_obj_new_tuple(6, t);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lvhdmi_stats_obj, 0, 1, lvhdmi_stats);

// Called by main.c on soft reset (Ctrl-D), before the GC heap is wiped: LVGL
// keeps its objects in that heap, so shut it down while they still exist.
void zynq_lvgl_deinit(void) {
    if (lv_is_initialized()) {
        lv_deinit();
    }
    hdmi_disp = NULL;
}

// _lvhdmi.mem() -> (total_bytes, used_bytes, frag_pct) of LVGL's memory pool
static mp_obj_t lvhdmi_mem(void) {
    lv_mem_monitor_t m;
    lv_mem_monitor(&m);
    mp_obj_t t[3] = {
        mp_obj_new_int_from_uint(m.total_size),
        mp_obj_new_int_from_uint(m.total_size - m.free_size),
        MP_OBJ_NEW_SMALL_INT(m.frag_pct),
    };
    return mp_obj_new_tuple(3, t);
}
static MP_DEFINE_CONST_FUN_OBJ_0(lvhdmi_mem_obj, lvhdmi_mem);

static const mp_rom_map_elem_t lvhdmi_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR_mem), MP_ROM_PTR(&lvhdmi_mem_obj) },
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__lvhdmi) },
    { MP_ROM_QSTR(MP_QSTR_create), MP_ROM_PTR(&lvhdmi_create_obj) },
    { MP_ROM_QSTR(MP_QSTR_frames), MP_ROM_PTR(&lvhdmi_frames_obj) },
    { MP_ROM_QSTR(MP_QSTR_stats), MP_ROM_PTR(&lvhdmi_stats_obj) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH), MP_ROM_INT(HDMI_W) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT), MP_ROM_INT(HDMI_H) },
};
static MP_DEFINE_CONST_DICT(lvhdmi_module_globals, lvhdmi_module_globals_table);

const mp_obj_module_t mp_module__lvhdmi = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&lvhdmi_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR__lvhdmi, mp_module__lvhdmi);
