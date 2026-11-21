"""lvhdmi - LVGL v9.6 on the 1280x720 HDMI output.

    import lvgl as lv
    import lvhdmi
    disp = lvhdmi.init()               # HDMI (if the bitstream is loaded) + LVGL + dark theme
    lv.label(lv.screen_active()).set_text("Hello LVGL")
    lvhdmi.run()                       # LVGL main loop; Ctrl-C to stop

or, next to other asyncio tasks:  asyncio.create_task(lvhdmi.task())

LVGL draws directly into the HDMI framebuffers (DIRECT mode, double
buffered, see usermods/lvgl_hdmi/lvgl_hdmi.c); every frame is shown at the
next video frame without tearing. The LVGL tick comes from the CPU timer.
init(hardware=False) renders without the HDMI hardware, e.g. in QEMU.
"""
from micropython import const
import time

import lvgl as lv
import _hdmi
import _lvhdmi

WIDTH = const(1280)
HEIGHT = const(720)


def init(hardware=None, dark=True, primary=None, secondary=None, font=None):
    """Start HDMI and LVGL; return the lv.display."""
    if hardware is None:
        hardware = _hdmi.available()
    if not lv.is_initialized():
        lv.init()
    if hardware:
        _hdmi.init()
    _lvhdmi.create()
    disp = lv.display_get_default()
    th = lv.theme_default_init(
        disp,
        primary or lv.palette_main(lv.PALETTE.BLUE),
        secondary or lv.palette_main(lv.PALETTE.ORANGE),
        dark,
        font or lv.font_montserrat_16,
    )
    disp.set_theme(th)
    return disp


def frames():
    """Frames presented on HDMI since init()."""
    return _lvhdmi.frames()


def stats(reset=False):
    """(frames, areas, pixels, tick_calls, present_ms, full_redraws) since the last reset:
    flushed areas and pixels show how much LVGL redraws; present_ms is the time
    spent writing frames back from the cache and waiting for the video switch;
    full_redraws counts frames that repainted (nearly) the whole screen."""
    return _lvhdmi.stats(reset)


def run(duration_ms=None):
    """LVGL main loop: timers, animations and redraws. Ctrl-C stops it."""
    t0 = time.ticks_ms()
    while duration_ms is None or time.ticks_diff(time.ticks_ms(), t0) < duration_ms:
        wait = lv.timer_handler()
        time.sleep_ms(min(wait, 5))


def mem():
    """(total_bytes, used_bytes, frag_pct) of LVGL's memory pool (LV_MEM_SIZE)."""
    return _lvhdmi.mem()


async def task(period_ms=5):
    """The same loop as an asyncio task."""
    import asyncio
    while True:
        lv.timer_handler()
        await asyncio.sleep_ms(period_ms)
