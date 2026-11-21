# LVGL 9.6 dashboard on the 720p HDMI output - non-interactive, runs by itself.
# Run with:  mpremote connect <port> run examples/lvgl_demo.py   (Ctrl-C to stop)
#
# Everything moves through LVGL animations (lv.anim_t) and timers (lv.timer_create):
#   gauge     lv.scale + needle, eased animation
#   signal    lv.chart line series, scrolling
#   spectrum  lv.chart bars, from a live FFT of a synthetic signal (fft.run, "c")
#   load      two lv.arc, different periods
#   LEDs      four lv.bar + lv.led, mirrored on the board's LED1..LED4 (AXI GPIO)
#   system    caches, frames/fps, redrawn pixels per frame, uptime
#
# Performance notes (what keeps this at 60 fps on the 666 MHz Cortex-A9):
#   - LVGL allocates from its own pool (LV_STDLIB_BUILTIN in usermods/lv_conf.h),
#     not from the 16 MB MicroPython heap, whose allocator gets slow there;
#   - batch many value changes in one frame (see spectrum) so LVGL doesn't run out
#     of invalid-area slots and redraw the whole 1280x720 screen;
#   - don't call gc.mem_free() periodically: it walks the whole heap.
# examples/lvgl_perf.py measures fps and redraw on the board.
import array
import math
import sys
import time

import lvgl as lv
import lvhdmi
import fft
import zynq
from machine import Pin

W, H = lvhdmi.WIDTH, lvhdmi.HEIGHT
ACCENT = lv.palette_main(lv.PALETTE.ORANGE)
BLUE = lv.palette_main(lv.PALETTE.BLUE)
CYAN = lv.palette_main(lv.PALETTE.CYAN)
GREEN = lv.palette_main(lv.PALETTE.GREEN)
RED = lv.palette_main(lv.PALETTE.RED)
PURPLE = lv.palette_main(lv.PALETTE.DEEP_PURPLE)
GREY = lv.palette_main(lv.PALETTE.GREY)

CARD_W, CARD_H = 400, 285
PLOT_W, PLOT_H = CARD_W - 28, CARD_H - 28 - 40     # inside the card, below its title
COLS = (20, 440, 860)
ROWS = (82, 382)

_keep = []          # LVGL holds only pointers: keep Python callbacks and anims alive


def card(parent, col, row, title):
    c = lv.obj(parent)
    c.set_size(CARD_W, CARD_H)
    c.set_pos(COLS[col], ROWS[row])
    c.remove_flag(lv.obj.FLAG.SCROLLABLE)
    c.set_style_pad_all(14, 0)
    t = lv.label(c)
    t.set_text(title)
    t.set_style_text_font(lv.font_montserrat_20, 0)
    t.set_style_text_color(ACCENT, 0)
    t.align(lv.ALIGN.TOP_LEFT, 0, 0)
    return c


def animate(exec_cb, start, end, duration, reverse=None, delay=0, path=None):
    a = lv.anim_t()
    a.init()
    a.set_values(start, end)
    a.set_duration(duration)
    a.set_reverse_duration(duration if reverse is None else reverse)
    a.set_repeat_count(lv.ANIM_REPEAT_INFINITE)
    a.set_delay(delay)
    a.set_path_cb(path or lv.anim_t.path_ease_in_out)
    a.set_custom_exec_cb(lambda _a, v: exec_cb(v))
    a.start()
    _keep.append(a)
    return a


def timer(cb, period):
    t = lv.timer_create(lambda _t: cb(), period, None)
    _keep.append(cb)
    return t


# ---- header and footer ---------------------------------------------------------------
def header(scr):
    bar = lv.obj(scr)
    bar.set_size(W, 66)
    bar.set_pos(0, 0)
    bar.set_style_radius(0, 0)
    bar.set_style_border_width(0, 0)
    bar.set_style_bg_color(lv.color_hex(0x16213E), 0)
    bar.remove_flag(lv.obj.FLAG.SCROLLABLE)
    title = lv.label(bar)
    title.set_text("ZYNQ ZERO  |  LVGL %d.%d.%d  |  MicroPython %s" % (
        lv.version_major(), lv.version_minor(), lv.version_patch(),
        ".".join(str(v) for v in sys.implementation.version[:3])))
    title.set_style_text_font(lv.font_montserrat_28, 0)
    title.align(lv.ALIGN.LEFT_MID, 10, 0)
    spin = lv.spinner(bar)
    spin.set_size(40, 40)
    spin.set_anim_params(1200, 270)
    spin.align(lv.ALIGN.RIGHT_MID, -10, 0)
    clock = lv.label(bar)
    clock.set_style_text_font(lv.font_montserrat_28, 0)
    clock.set_style_text_color(ACCENT, 0)
    clock.align(lv.ALIGN.RIGHT_MID, -70, 0)
    t0 = time.ticks_ms()

    def tick():
        s = time.ticks_diff(time.ticks_ms(), t0) // 1000
        clock.set_text("%02d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60))
    tick()
    timer(tick, 250)


def footer(scr):
    msg = lv.label(scr)
    msg.set_width(W - 220)                             # leave room for the perf monitor
    msg.set_long_mode(lv.label.LONG_MODE.SCROLL_CIRCULAR)
    msg.set_text("LVGL renders straight into the HDMI framebuffers (DIRECT mode, double buffered)  -  "
                 "the AXI VDMA scans them out over HP0  -  Video Timing Controller + AXI4-Stream to "
                 "Video Out make 1280x720 @ 60 Hz  -  TMDS encoding and 10:1 serialisation in Verilog  -  "
                 "the LED bars drive LED1..LED4 through an AXI GPIO  -  the spectrum is a live FFT "
                 "computed by the fft module  -  ")
    msg.set_style_text_color(GREY, 0)
    msg.align(lv.ALIGN.BOTTOM_LEFT, 20, -8)


# ---- cards ---------------------------------------------------------------------------
def gauge(scr):
    c = card(scr, 0, 0, "lv.scale + needle")
    scale = lv.scale(c)
    scale.set_size(220, 220)
    scale.set_mode(lv.scale.MODE.ROUND_INNER)
    scale.set_label_show(True)
    scale.set_total_tick_count(41)
    scale.set_major_tick_every(5)
    scale.set_range(0, 200)
    scale.set_angle_range(270)
    scale.set_rotation(135)
    scale.set_style_length(6, lv.PART.ITEMS)
    scale.set_style_length(12, lv.PART.INDICATOR)
    scale.set_style_line_color(CYAN, lv.PART.INDICATOR)
    scale.set_style_arc_color(CYAN, lv.PART.MAIN)
    scale.align(lv.ALIGN.BOTTOM_MID, 0, 6)
    needle = lv.line(scale)
    needle.set_style_line_width(5, 0)
    needle.set_style_line_rounded(True, 0)
    needle.set_style_line_color(ACCENT, 0)
    value = lv.label(c)
    value.set_style_text_font(lv.font_montserrat_36, 0)
    value.align(lv.ALIGN.TOP_RIGHT, 0, -6)

    def set_v(v):
        scale.set_line_needle_value(needle, 80, v)
        value.set_text(str(v))
    animate(set_v, 10, 190, 2600, 1800, path=lv.anim_t.path_overshoot)


def signal(scr):
    c = card(scr, 1, 0, "lv.chart  line")
    ch = lv.chart(c)
    ch.set_size(PLOT_W, PLOT_H)
    ch.align(lv.ALIGN.BOTTOM_MID, 0, 0)
    ch.set_type(lv.chart.TYPE.LINE)
    ch.set_point_count(100)
    ch.set_update_mode(lv.chart.UPDATE_MODE.SHIFT)
    ch.set_axis_range(lv.chart.AXIS.PRIMARY_Y, 0, 100)
    ch.set_div_line_count(5, 8)
    ch.set_style_width(0, lv.PART.INDICATOR)          # no point markers
    ch.set_style_height(0, lv.PART.INDICATOR)
    s1 = ch.add_series(CYAN, lv.chart.AXIS.PRIMARY_Y)
    s2 = ch.add_series(ACCENT, lv.chart.AXIS.PRIMARY_Y)
    st = [0]

    def step():
        k = st[0]
        st[0] += 1
        ch.set_next_value(s1, int(50 + 35 * math.sin(k * 0.12) + 8 * math.sin(k * 0.71)))
        ch.set_next_value(s2, int(50 + 30 * math.cos(k * 0.05) * math.sin(k * 0.19)))
    for _ in range(100):
        step()
    timer(step, 40)


def spectrum(scr):
    c = card(scr, 2, 0, "Spectrum: fft.run(..., 'c')")
    ch = lv.chart(c)
    ch.set_size(PLOT_W, PLOT_H)
    ch.align(lv.ALIGN.BOTTOM_MID, 0, 0)
    ch.set_type(lv.chart.TYPE.BAR)
    nbins = 32
    ch.set_point_count(nbins)
    ch.set_axis_range(lv.chart.AXIS.PRIMARY_Y, 0, 100)
    ch.set_div_line_count(4, 0)
    ch.set_style_pad_column(2, 0)
    ser = ch.add_series(GREEN, lv.chart.AXIS.PRIMARY_Y)
    disp = lv.display_get_default()
    n = 2 * 2 * nbins                                  # 128-point FFT, show bins 0..31
    re = array.array("d", bytearray(8 * n))
    im = array.array("d", bytearray(8 * n))
    hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / n) for i in range(n)]
    st = [0.0]

    def step():
        t = st[0]
        st[0] += 0.05
        f1 = 6 + 4 * math.sin(t)                       # two drifting tones + noise
        f2 = 20 + 8 * math.sin(0.37 * t + 1)
        seed = int(t * 1000) & 0xFFFF
        for i in range(n):
            seed = (seed * 25173 + 13849) & 0xFFFF
            re[i] = hann[i] * (math.sin(2 * math.pi * f1 * i / n)
                               + 0.6 * math.sin(2 * math.pi * f2 * i / n)
                               + (seed / 65536 - 0.5) * 0.05)
            im[i] = 0.0
        fft.run(re, im, "c")
        # Each set_series_value_by_id() would invalidate its own bar: 32 areas in
        # one frame overflow LVGL's invalid-area buffer and force a full-screen
        # redraw. Batch the update and invalidate the chart once instead.
        disp.enable_invalidation(False)
        for k in range(nbins):
            mag = math.sqrt(re[k] * re[k] + im[k] * im[k]) / (n / 4)   # Hann gain 1/2
            db = 20 * math.log10(mag + 1e-3)               # -60 .. 0 dB
            ch.set_series_value_by_id(ser, k, max(0, int((db + 60) * 100 / 60)))
        disp.enable_invalidation(True)
        ch.refresh()
    step()
    timer(step, 100)


def load(scr):
    c = card(scr, 0, 1, "lv.arc")
    outer = lv.arc(c)
    outer.set_size(210, 210)
    outer.set_bg_angles(0, 360)
    outer.set_rotation(270)
    outer.remove_style(None, lv.PART.KNOB)
    outer.set_style_arc_width(16, lv.PART.MAIN)
    outer.set_style_arc_width(16, lv.PART.INDICATOR)
    outer.set_style_arc_color(BLUE, lv.PART.INDICATOR)
    outer.align(lv.ALIGN.BOTTOM_MID, 0, 0)
    inner = lv.arc(c)
    inner.set_size(150, 150)
    inner.set_bg_angles(0, 360)
    inner.set_rotation(270)
    inner.remove_style(None, lv.PART.KNOB)
    inner.set_style_arc_width(12, lv.PART.MAIN)
    inner.set_style_arc_width(12, lv.PART.INDICATOR)
    inner.set_style_arc_color(ACCENT, lv.PART.INDICATOR)
    inner.align(lv.ALIGN.BOTTOM_MID, 0, -30)
    pct = lv.label(c)
    pct.set_style_text_font(lv.font_montserrat_28, 0)
    pct.align(lv.ALIGN.BOTTOM_MID, 0, -92)

    def set_outer(v):
        outer.set_value(v)
        pct.set_text("%d%%" % v)
    animate(set_outer, 5, 95, 3000, path=lv.anim_t.path_ease_in_out)
    animate(inner.set_value, 0, 100, 1700, delay=400, path=lv.anim_t.path_linear)


def leds(scr):
    c = card(scr, 1, 1, "lv.bar -> LED1..LED4 (AXI GPIO)")
    colors = (RED, GREEN, BLUE, PURPLE)
    periods = (900, 1300, 1700, 2300)
    for i in range(4):
        y = 50 + i * 54
        name = lv.label(c)
        name.set_text("LED%d" % (i + 1))
        name.set_style_text_font(lv.font_montserrat_20, 0)
        name.set_pos(0, y + 4)
        bar = lv.bar(c)
        bar.set_size(220, 22)
        bar.set_range(0, 100)
        bar.set_pos(72, y + 4)
        bar.set_style_bg_color(colors[i], lv.PART.INDICATOR)
        led = lv.led(c)
        led.set_size(26, 26)
        led.set_color(colors[i])
        led.set_pos(318, y + 2)
        pin = Pin("LED%d" % (i + 1), Pin.OUT)

        def make(bar, led, pin):
            state = [None]

            def set_v(v):
                bar.set_value(v, False)                # lv_anim_enable_t is a bool here
                on = v > 50
                if on != state[0]:                     # touch the LED and pin only on change
                    state[0] = on
                    led.on() if on else led.off()
                    pin.value(on)
            return set_v
        animate(make(bar, led, pin), 0, 100, periods[i], delay=i * 200)


def system(scr):
    c = card(scr, 2, 1, "System")
    info = lv.label(c)
    info.set_style_text_font(lv.font_montserrat_20, 0)
    info.set_style_text_line_space(8, 0)
    info.set_pos(0, 40)
    t0 = time.ticks_ms()
    ci = zynq.info()
    caches = "L1 I+D, L2" if ci["l2"] else ("L1 I+D, no L2" if ci["dcache"] else "OFF")
    last = [lvhdmi.frames(), t0]
    fps = [0]
    lvhdmi.stats(True)

    # Note: no gc.mem_free() here - it walks the whole 16 MB heap (~0.1 s per call)
    def update():
        now = time.ticks_ms()
        f, areas, px, _, present_ms, _ = lvhdmi.stats(True)
        dt = time.ticks_diff(now, last[1])
        n = f - last[0]
        if dt > 0:
            fps[0] = n * 1000 // dt
        last[0], last[1] = f, now
        up = time.ticks_diff(now, t0) // 1000
        info.set_text(
            "CPU      Cortex-A9  %d MHz\n"
            "Caches   %s\n"
            "Frames   %d  (%d fps)\n"
            "Redraw   %d kpx/frame\n"
            "Uptime   %d:%02d" % (
                ci["cpu_hz"] // 1_000_000, caches, f, fps[0], px // max(n, 1) // 1000,
                up // 60, up % 60))
    update()
    timer(update, 1000)


def build():
    scr = lv.screen_active()
    scr.set_style_bg_color(lv.color_hex(0x0B1020), 0)
    scr.remove_flag(lv.obj.FLAG.SCROLLABLE)
    header(scr)
    gauge(scr)
    signal(scr)
    spectrum(scr)
    load(scr)
    leds(scr)
    system(scr)
    footer(scr)


def main(duration_ms=None):
    lvhdmi.init()
    build()
    lvhdmi.run(duration_ms)


if __name__ == "__main__":
    main()
