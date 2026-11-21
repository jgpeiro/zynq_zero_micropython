"""Software, build, boot and LVGL diagrams."""
from svglib import Svg, PS, PL, XIP, RTL, MEM, EXT, SW, SWC, WHITE, INK, ACCENT, GREY


def fig_build():
    s = Svg(700, 330, "bf")
    # HW lane
    s.text(10, 14, "./build.sh hw", 9, "start", "700")
    s.box(10, 22, 120, 66, "hw/", WHITE, "rtl/*.v (7 modules)\nscripts/build.tcl\nscripts/ps7_config.tcl\nconstraints/*.xdc", fs=9.5, sfs=7)
    s.box(160, 22, 150, 66, "Vivado 2021.1 (batch)", XIP, "block design, wrapper\nsynthesis, implementation\ntiming check (WNS ≥ 0)", fs=9, sfs=7)
    s.box(340, 22, 130, 66, "hw/build/", MEM, "system.bit\nps7_init.tcl (+ .html)\nsystem.xsa, reports", fs=9.5, sfs=7)
    s.line([(130, 55), (160, 55)])
    s.line([(310, 55), (340, 55)])
    # FW lane
    s.text(10, 112, "./build.sh fw", 9, "start", "700")
    s.box(10, 120, 120, 50, "MicroPython v1.29.0", SW, "git clone (+ micropython-lib)", fs=8.6, sfs=7)
    s.box(10, 178, 120, 50, "ports/zynq/", SWC, "C, startup.S, zynq.ld\nmodules/*.py (frozen)", fs=9, sfs=7)
    s.box(10, 236, 120, 72, "usermods/", SWC, "LVGL v9.6.0\nlv_binding_micropython\n@ 032dda4 (+ 1 patch)\nlvgl_hdmi, lv_conf.h", fs=9, sfs=7)
    s.box(160, 120, 150, 50, "mpy-cross", SW, "host build; freezes asyncio,\nfft.py, hdmi.py, lvhdmi.py", fs=9, sfs=7)
    s.box(160, 236, 150, 72, "gen_mpy.py + pycparser", SW, "preprocesses lvgl.h,\ngenerates lv_mpy.c\n(the lvgl module, 2.2 MB C)", fs=9, sfs=7)
    s.box(340, 160, 130, 76, "arm-none-eabi-gcc", WHITE, "-mcpu=cortex-a9 -marm\n-mfpu=vfpv3\n-mfloat-abi=softfp -Os", fs=9, sfs=7)
    s.box(340, 254, 130, 54, "firmware.elf", MEM, "1.35 MB code\n(LVGL=1)", fs=9.5, sfs=7)
    s.line([(130, 145), (160, 145)])
    s.line([(130, 203), (340, 203)])
    s.line([(130, 272), (160, 272)])
    s.line([(310, 145), (325, 145), (325, 180), (340, 180)])
    s.line([(310, 272), (325, 272), (325, 220), (340, 220)])
    s.line([(405, 236), (405, 254)])
    # Program
    s.box(520, 100, 170, 70, "./program.sh", WHITE, "Vivado loader → rdi_xsdb\nscripts/program.tcl\nover USB-JTAG", fs=9.5, sfs=7.2)
    s.box(520, 210, 170, 76, "ZYNQ ZERO", EXT, "PL configured (DONE LED)\nPS initialised\nfirmware in DDR at 0x0010_0000\nREPL on UART1", fs=9.5, sfs=7)
    s.line([(470, 55), (500, 55), (500, 125), (520, 125)])
    s.line([(470, 281), (500, 281), (500, 150), (520, 150)])
    s.line([(605, 170), (605, 210)], lw=1.6, label="JTAG", lpos=(625, 190))
    s.text(605, 314, "Everything volatile: lost at power-off", 7.6, "middle", fill="#555")
    return s.render()


def fig_boot():
    s = Svg(700, 310, "boot")
    lanes = [("xsdb", 36), ("PL", 96), ("PS", 156), ("CPU0", 216)]
    for name, y in lanes:
        s.rect(64, y - 26, 632, 52, "#f8f8f8", "#dddddd", 0.6, 0)
        s.text(56, y, name, 9, "end", "700")
    steps = [  # (lane y, label, sub, fill)
        (36, "connect", "hw_server", WHITE),
        (156, "rst -system", "PS reset", PS),
        (96, "fpga -file", "system.bit,\nDONE high", PL),
        (156, "ps7_init", "PLLs, MIO,\nDDR3 training", PS),
        (156, "post_config", "PS-PL level\nshifters on", PS),
        (216, "dow + con", "ELF → DDR,\npc = _vectors", MEM),
        (216, "reset_handler", "stacks, VFP,\n.bss, zynq_start", SW),
    ]
    prev = None
    for i, (y, lab, sub, fill) in enumerate(steps):
        x = 72 + i * 89
        s.box(x, y - 22, 82, 44, f"{i + 1}. {lab}", fill, sub, fs=8.6, sfs=7.0)
        if prev:
            px, py = prev
            s.line([(px, py), (x, y)], color=GREY, lw=0.9)
        prev = (x + 82, y)
    s.text(380, 268, "zynq_start(): MMU + L1 + L2  →  global timer  →  UART1 115200 8N1  →  gc_init, mp_init  →  REPL",
           8.6, "middle", "600")
    s.text(380, 286, "CPU1 stays in its BootROM wait loop throughout", 7.8, "middle", fill="#555")
    return s.render()


def fig_stack():
    s = Svg(700, 400, "stk")
    layers = [
        (10, "Python code", "REPL, mpremote run, examples/*.py (blink, fft_demo, hdmi_demo, lvgl_demo, lvgl_perf)", SW, 40),
    ]
    s.box(10, 10, 680, 38, "Python application code", SW, "REPL, mpremote run, examples/*.py  (blink, fft_demo, hdmi_demo, lvgl_demo, lvgl_perf)", fs=10, sfs=7.6)
    # frozen modules
    y = 58
    s.text(10, y + 4, "Frozen Python modules (manifest.py)", 8.4, "start", "700")
    for i, (n, d) in enumerate((("asyncio", "micropython-lib"), ("fft.py", "4 FFT methods"),
                                ("hdmi.py", "framebuf Display"), ("lvhdmi.py", "LVGL helper"))):
        s.box(10 + i * 172, y + 12, 164, 36, n, SW, d, fs=9.5, sfs=7.2)
    # C modules
    y = 118
    s.text(10, y + 4, "Built-in C modules", 8.4, "start", "700")
    mods = [("machine", "Pin, freq, reset,\nmem32, idle"), ("_fft", "C FFT, PL engine\ndriver, probe"),
            ("_hdmi", "framebuffers,\nVDMA driver"), ("zynq", "info(): MMU,\ncaches"),
            ("lvgl", "generated binding\n(lv_mpy.c)"), ("_lvhdmi", "LVGL display\ndriver")]
    for i, (n, d) in enumerate(mods):
        s.box(10 + i * 114.6, y + 12, 108, 46, n, SWC, d, fs=9.5, sfs=7)
    s.box(10 + 4 * 114.6, y + 64, 222.6, 30, "LVGL v9.6 core (draw sw, RGB565, TLSF)", SWC, fs=8.4)
    # MicroPython core
    y = 222
    s.box(10, y, 680, 40, "MicroPython v1.29.0 core", SW, "compiler, bytecode VM, ARM native/viper emitter, GC (16 MB), mpz ints, double floats, scheduler, pyexec REPL",
          fs=10, sfs=7.4)
    # HAL
    y = 272
    hal = [("startup.S", "vectors, stacks,\nVFP, .bss"), ("mmu.c", "flat map,\nL1 + L2"), ("mphalport.c", "ticks, delays,\nstdio"),
           ("uart.c", "polled UART1,\nCtrl-C"), ("main.c", "REPL loop, GC\nroots, faults"), ("zynq.ld", "DDR layout")]
    s.text(10, y + 4, "Port layer (ports/zynq)", 8.4, "start", "700")
    for i, (n, d) in enumerate(hal):
        s.box(10 + i * 114.6, y + 12, 108, 44, n, SWC, d, fs=9, sfs=7)
    # HW
    y = 340
    s.box(10, y, 334, 50, "Processing System", PS, "Cortex-A9, caches, DDR3, UART1, GPIO, global timer, SLCR", fs=9.5, sfs=7.2)
    s.box(356, y, 334, 50, "Programmable Logic (via GP0 / HP0)", PL, "AXI GPIO, FFT engines, VDMA, video status", fs=9.5, sfs=7.2)
    return s.render()


def fig_uart():
    s = Svg(700, 230, "ua")
    s.box(10, 70, 90, 60, "CH340", EXT, "USB ↔ UART", fs=9.5, sfs=7.2)
    s.box(130, 40, 110, 50, "RX FIFO", MEM, "UART1, 64 bytes", fs=9, sfs=7.2)
    s.box(130, 120, 110, 50, "TX FIFO", MEM, "UART1, 64 bytes", fs=9, sfs=7.2)
    s.line([(100, 85), (130, 65)], label="MIO49", lpos=(112, 66), lfs=6.8)
    s.line([(130, 145), (100, 118)], label="MIO48", lpos=(112, 142), lfs=6.8)
    s.box(280, 30, 150, 70, "zynq_uart_poll()", SWC, "drain RX FIFO\nCtrl-C → KeyboardInterrupt\nelse → ring buffer", fs=9.5, sfs=7.2)
    s.line([(240, 65), (280, 65)])
    s.box(470, 30, 100, 36, "ring buffer", MEM, "512 bytes", fs=9, sfs=7)
    s.box(470, 74, 100, 36, "mp_sched_keyboard_\ninterrupt()", WHITE, fs=7.6, bold=False)
    s.line([(430, 48), (470, 48)])
    s.line([(430, 88), (470, 92)])
    s.box(600, 30, 90, 80, "readline /\npyexec", SW, "mp_hal_stdin_\nrx_chr()", fs=9.5, sfs=7)
    s.line([(570, 48), (600, 60)])
    s.box(280, 130, 150, 44, "mp_hal_stdout_tx_strn()", SWC, "wait while TXFULL", fs=8.6, sfs=7.2)
    s.line([(280, 152), (240, 147)])
    s.text(355, 196, "Callers of zynq_uart_poll(): VM hook every 64 jumps / calls / returns,", 8, "middle")
    s.text(355, 210, "mp_event_handle_nowait() (sleep_ms, input waits), machine.idle(), stdio poll", 8, "middle")
    return s.render()


def seq(s, lifelines, top, bottom):
    for x, name, fill in lifelines:
        s.box(x - 58, top, 116, 30, name, fill, fs=8.8)
        s.line([(x, top + 30), (x, bottom)], arrow=None, color=GREY, dash=True, lw=0.8)


def msg(s, x1, x2, y, label, dashed=False, color=INK):
    s.line([(x1, y), (x2, y)], dash=dashed, color=color, lw=1)
    s.text((x1 + x2) / 2, y - 6, label, 8.2, "middle")


def selfmsg(s, x, y, label, w=120):
    s.rect(x - 4, y - 7, 8, 14, "#e8e8e8", INK, 0.6, 0)
    s.text(x + 10, y, label, 8.2, "start")


def fig_fftseq():
    s = Svg(700, 330, "fs")
    A, B, C = 90, 330, 580
    seq(s, [(A, "fft.run(re, im, \"verilog\")", SW), (B, "_fft.hw (C, CPU0)", SWC), (C, "engine @ 0x43C0_0000", RTL)], 6, 322)
    y = 56
    msg(s, A, B, y, "base, re, im, inverse")
    msg(s, B, C, y + 22, "read ID, LOG2N_MAX, STATUS, FORMAT")
    selfmsg(s, B, y + 44, "scale to 16 bits (|x| < 1 for FORMAT 0)")
    msg(s, B, C, y + 66, "N writes: 0x1000 + 4i ← {im, re} Q1.15 (stored bit-reversed)")
    msg(s, B, C, y + 88, "LOG2N, INVERSE, CTRL = 1 (start)")
    s.rect(C - 5, y + 96, 10, 58, "#f7d6e0", INK, 0.7, 0)
    s.text(C + 12, y + 118, "log2(N) stages", 8, "start")
    s.text(C + 12, y + 130, "busy = 1", 8, "start")
    msg(s, B, C, y + 110, "poll STATUS until done (1 s timeout)", dashed=True)
    msg(s, C, B, y + 160, "STATUS.done = 1, CYCLES", color="#444")
    msg(s, B, C, y + 182, "N reads: 0x2000 (+ 0x3000) + 4i")
    selfmsg(s, B, y + 204, "rescale: forward Σ, inverse Σ / N")
    msg(s, B, A, y + 226, "(pl_cycles, overflow)", color="#444")
    return s.render()


def fig_present():
    s = Svg(700, 290, "pr")
    A, B, C, D = 80, 250, 430, 610
    seq(s, [(A, "LVGL / hdmi.show()", SW), (B, "L1 D-cache", MEM), (C, "DDR3", MEM), (D, "AXI VDMA", XIP)], 6, 284)
    y = 56
    msg(s, A, B, y, "draw into buffer i (cached)")
    msg(s, A, B, y + 28, "DCCMVAC × 57 600 lines, DSB")
    msg(s, B, C, y + 52, "dirty lines written back")
    msg(s, A, D, y + 80, "PARK_PTR = i   (GP0, strongly-ordered)")
    s.rect(D - 5, y + 90, 10, 40, "#fde4c9", INK, 0.7, 0)
    s.text(D + 10, y + 102, "finishes the", 8, "start")
    s.text(D + 10, y + 114, "current frame", 8, "start")
    msg(s, A, D, y + 106, "poll PARK_PTR[20:16] == i  (100 ms timeout)", dashed=True)
    msg(s, D, C, y + 148, "reads buffer i over HP0", color=ACCENT)
    msg(s, D, A, y + 176, "PARK_PTR[20:16] = i", color="#444")
    selfmsg(s, A, y + 204, "buffer 1-i is off screen: safe to draw")
    return s.render()


def fig_lvgl():
    s = Svg(700, 360, "lv")
    s.box(10, 10, 680, 34, "Python: import lvgl as lv, lvhdmi;  lvhdmi.init(); build widgets; lvhdmi.run()", SW, fs=9.2, bold=False)
    s.box(10, 60, 200, 64, "lvhdmi.py (frozen)", SW, "init(): lv.init, _hdmi.init,\n_lvhdmi.create, default theme\nrun() / task(): lv.timer_handler", fs=9.5, sfs=7.2)
    s.box(230, 60, 220, 64, "lvgl module (lv_mpy.c)", SWC, "generated from lvgl.h by gen_mpy.py\nwidgets, styles, anim, timers,\ncallbacks into Python", fs=9.5, sfs=7.2)
    s.box(470, 60, 220, 64, "_lvhdmi (usermods/lvgl_hdmi)", SWC, "create(), frames(), stats(), mem()\nflush_cb, tick_cb", fs=9.5, sfs=7.2)
    s.box(230, 144, 220, 76, "LVGL v9.6 core", SWC, "refresh: invalidated areas\nsoftware renderer, RGB565\nLV_DISPLAY_RENDER_MODE_DIRECT\nlv_conf.h", fs=9.5, sfs=7.2)
    s.box(470, 144, 220, 76, "modhdmi.c", SWC, "zynq_hdmi_present(i, wait):\nclean D-cache, PARK_PTR = i,\nwait for the switch", fs=9.5, sfs=7.2)
    s.box(10, 144, 200, 76, "TLSF pool 8 MB", MEM, ".lvgl_pool (LV_STDLIB_BUILTIN)\nlv_malloc / lv_free\nscanned by gc_collect()", fs=9.5, sfs=7.2)
    s.box(10, 244, 200, 50, "global timer", PS, "tick_cb → mp_hal_ticks_ms()", fs=9.5, sfs=7.2)
    s.box(230, 244, 220, 50, "framebuffer 0 / 1", MEM, "draw buffers = scan-out buffers\n(no copy)", fs=9.5, sfs=7.2)
    s.box(470, 244, 220, 50, "AXI VDMA → HDMI", XIP, "park mode, frame store i", fs=9.5, sfs=7.2)
    s.line([(110, 44), (110, 60)])
    s.line([(340, 44), (340, 60)])
    s.line([(210, 92), (230, 92)])
    s.line([(450, 92), (470, 92)])
    s.line([(340, 124), (340, 144)], arrow="both")
    s.line([(580, 124), (580, 144)])
    s.line([(450, 182), (470, 182)])
    s.line([(230, 182), (210, 182)])
    s.line([(340, 220), (340, 244)], label="renders into", lpos=(374, 232), lfs=6.8)
    s.line([(580, 220), (580, 244)])
    s.line([(450, 269), (470, 269)], arrow="start", label="HP0", lpos=(460, 262), lfs=6.8)
    s.line([(210, 269), (220, 269), (220, 208), (230, 208)], arrow="end", color=GREY)
    s.text(350, 318, "Soft reset (Ctrl-D): main.c calls zynq_lvgl_deinit() → lv_deinit() before gc_sweep_all(),", 7.8, "middle", fill="#444")
    s.text(350, 332, "so LVGL never holds pointers into a wiped heap; lvhdmi.init() works again afterwards.", 7.8, "middle", fill="#444")
    return s.render()


def fig_lvtimeline():
    s = Svg(700, 210, "lt")
    x0, fw = 120, 140
    s.text(110, 40, "VDMA scans", 8.4, "end", "600")
    s.text(110, 84, "LVGL draws", 8.4, "end", "600")
    s.text(110, 128, "CPU", 8.4, "end", "600")
    for i in range(4):
        x = x0 + i * fw
        shown = i % 2
        s.box(x, 26, fw - 2, 28, f"buffer {shown}", "#e3f1da" if shown == 0 else "#d7e7f6", fs=8.6, bold=False)
        drawn = 1 - shown
        s.box(x + 4, 70, 70, 28, f"render {drawn}", "#f7d6e0", fs=8, bold=False)
        s.box(x + 76, 114, 44, 28, "clean", MEM, fs=7.6, bold=False)
        s.line([(x + fw - 6, 112), (x + fw - 2, 58)], color=ACCENT, lw=1)
        s.line([(x, 20), (x, 150)], arrow=None, color=GREY, dash=True, lw=0.7)
    s.line([(x0 + 4 * fw, 20), (x0 + 4 * fw, 150)], arrow=None, color=GREY, dash=True, lw=0.7)
    for i in range(5):
        s.text(x0 + i * fw, 162, f"vsync {i}", 7.2, "middle", fill="#555")
    s.text(x0 + 2 * fw, 180, "16.7 ms per frame (60 Hz). Red: PARK_PTR = i, effective at the next vsync.", 7.8, "middle")
    s.text(x0 + 2 * fw, 194, "LVGL also copies the areas redrawn last frame into the new buffer (DIRECT-mode sync).",
           7.4, "middle", fill="#555")
    return s.render()


def fig_gc():
    s = Svg(700, 230, "gc")
    s.box(10, 20, 150, 90, "GC roots", WHITE, "CPU registers + C stack\nMP_STATE (incl. mp_lv_roots,\nthe binding's LVGL globals)\n.lvgl_pool  ← added", fs=9.5, sfs=7.2)
    s.box(230, 10, 220, 120, "", "#d7e7f6")
    s.text(240, 24, "GC heap  16 MB", 9, "start", "700")
    s.box(244, 36, 90, 34, "callback", WHITE, "lambda / def", fs=8.4, sfs=6.8)
    s.box(344, 36, 96, 34, "lv.obj wrapper", WHITE, "Python object", fs=8.4, sfs=6.8)
    s.box(244, 82, 196, 38, "user objects, arrays, strings", WHITE, fs=8.2, bold=False)
    s.box(520, 10, 170, 120, "", "#f7d6e0")
    s.text(530, 24, "LVGL pool  8 MB", 9, "start", "700")
    s.box(532, 36, 146, 34, "lv_obj_t, styles", WHITE, "event_dsc → Python callback", fs=8.4, sfs=6.8)
    s.box(532, 82, 146, 38, "draw buffers, layers", WHITE, "allocated / freed each frame", fs=8.2, sfs=6.8)
    s.line([(532, 53), (334, 53)], color=ACCENT, label="only reference", lpos=(480, 47), lfs=7)
    s.line([(440, 53), (532, 58)], color=GREY)
    s.line([(160, 76), (520, 76)], dash=True, color=ACCENT, label="scanned conservatively", lpos=(470, 90), lfs=7)
    s.text(350, 160, "Before: LVGL allocated from the GC heap (LV_STDLIB_MICROPYTHON). Every draw-buffer allocation",
           7.8, "middle")
    s.text(350, 174, "searched the 16 MB heap's block table linearly: gc_alloc took about 80 % of the CPU.",
           7.8, "middle")
    s.text(350, 194, "Now: TLSF allocation in O(1) from its own pool; gc_collect() treats the pool as a root region,",
           7.8, "middle", "600")
    s.text(350, 208, "so a Python callback that only LVGL refers to is never freed.", 7.8, "middle", "600")
    return s.render()


def fig_perf():
    s = Svg(700, 190, "pf")
    rows = [("Before: LV_STDLIB_MICROPYTHON", 35.2, "#c9c9c9", "26 fps, 100 % CPU"),
            ("After: TLSF pool + batching", 3.2, ACCENT, "62 fps in QEMU (60 on HDMI), 19 % CPU")]
    x0, scale = 220, 11
    for i, (lab, v, c, note) in enumerate(rows):
        y = 26 + i * 52
        s.text(x0 - 10, y + 14, lab, 8.6, "end", "600")
        s.rect(x0, y, v * scale, 28, c, c, 0.5, 0)
        s.text(x0 + v * scale + 6, y + 9, f"{v} ms", 8.6, "start", "700")
        s.text(x0 + v * scale + 6, y + 21, note, 7.6, "start", fill="#555")
    for t in range(0, 41, 10):
        x = x0 + t * scale
        s.line([(x, 132), (x, 136)], arrow=None, color=GREY)
        s.text(x, 146, str(t), 7.4, "middle", fill="#555")
    s.line([(x0, 132), (x0 + 40 * scale, 132)], arrow=None, color=GREY, lw=0.8)
    s.text(x0 + 20 * scale, 160, "CPU time in lv.timer_handler() per frame, ms (full dashboard)", 7.8, "middle")
    s.text(x0 + 20 * scale, 178, "QEMU -icount shift=1 (2 ns per instruction, about a 666 MHz A9); cache and DDR effects not modelled",
           7.2, "middle", fill="#555")
    return s.render()
