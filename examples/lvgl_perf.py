# lvgl_perf.py - check LVGL performance on the board.
#
#   mpremote connect /dev/ttyUSB1 run examples/lvgl_perf.py
#
# Prints the cache setup, then runs the LVGL demo dashboard for 10 s and reports
# frames per second, how much of each frame the CPU was busy, how much LVGL
# redrew, and LVGL's memory use. Expected with the default build: caches all
# True, about 60 fps, CPU well under 100 %, 0 full-screen redraws.
import gc
import time

import lvgl as lv
import lvhdmi
import zynq

print("zynq.info():")
for k, v in sorted(zynq.info().items()):
    print("  %-12s %s" % (k, hex(v) if k in ("sctlr", "actlr") else v))

import lvgl_demo                       # examples/lvgl_demo.py, copied to the board
lvhdmi.init()
lvgl_demo.build()
lvhdmi.run(1500)                       # let animations and timers settle

gc.collect()
lvhdmi.stats(True)
f0 = lvhdmi.frames()
busy = 0
worst = 0
t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < 10_000:
    t = time.ticks_us()
    lv.timer_handler()
    d = time.ticks_diff(time.ticks_us(), t)
    busy += d
    worst = max(worst, d)
    time.sleep_ms(1)
dt = time.ticks_diff(time.ticks_ms(), t0)
f, areas, px, _, present_ms, full = lvhdmi.stats()
n = max(f - f0, 1)
total, used, frag = lvhdmi.mem()

print("10 s of the demo:")
print("  %.1f fps, CPU busy %d %% (%.1f ms/frame, worst call %.1f ms)" % (
    n * 1000 / dt, busy // (dt * 10), busy / 1000 / n, worst / 1000))
print("  redraw %d areas, %d kpx per frame; %d full-screen redraws" % (areas // n, px // n // 1000, full))
print("  present (cache clean + VDMA switch) %.2f ms/frame" % (present_ms / n))
print("  LVGL pool %d of %d KB used, %d %% fragmented; GC heap %d KB free" % (
    used // 1024, total // 1024, frag, gc.mem_free() // 1024))
