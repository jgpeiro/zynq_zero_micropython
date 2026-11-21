"""Chapters 4-7 and appendices: build and boot, MicroPython port, drivers, LVGL."""
import figs_hw as H
import figs_sw as S


def build(d):
    # ======================================================================================
    d.chapter("Build, Programming and Boot")
    d.section("Build flow")
    d.figure("From sources to a running board: `build.sh hw`, `build.sh fw` and `program.sh`.",
             S.fig_build(), label="fig-build")
    d.p("The hardware and the firmware are built independently and only meet at the fixed addresses of "
        "{ref:tab-gp0} and the clock frequencies of {ref:clocks}. A firmware-only change, which covers "
        "everything in Chapters 5 to 7, needs no Vivado run: `./build.sh fw` and `./program.sh` with "
        "the existing bitstream.")
    d.table("Toolchain and third-party versions.", ["Component", "Version", "Fetched by"], [
        ["Vivado", "2021.1", "installed (`VIVADO_ROOT`)"],
        ["GNU Arm toolchain", "arm-none-eabi-gcc (PATH, or Vitis's copy)", "installed"],
        ["MicroPython", "v1.29.0", "`build.sh` (git clone, micropython-lib submodule)"],
        ["LVGL", "v9.6.0", "`build.sh` into `usermods/lv_binding_micropython/lvgl`"],
        ["lv_binding_micropython", "commit 032dda4b", "`build.sh` (+ pycparser submodule)"],
        ["QEMU (optional)", "qemu-system-arm, machine xilinx-zynq-a9", "installed"],
        ["Icarus Verilog (optional)", "iverilog", "installed; `build.sh sim`"],
    ], widths=[26, 38, 36])

    d.section("Programming over JTAG", label="sec-prog")
    d.figure("What `program.sh` does, across the debugger, the PL, the PS and CPU0.", S.fig_boot(), label="fig-boot")
    d.p("The board boots in JTAG mode. `program.sh` starts Vivado's `loader -exec rdi_xsdb` (the `xsdb` "
        "wrapper's bundled rlwrap crashes under WSL) with `scripts/program.tcl`, which:")
    d.ol(["connects to a fresh `hw_server` and resets the whole PS (`rst -system`);",
          "configures the PL with `system.bit` (`fpga -file`);",
          "runs the Vivado-generated `ps7_init`: PLLs, MIO multiplexing and voltages, DDR3 controller "
          "and training, then `ps7_post_config` to enable the PS-PL level shifters;",
          "stops CPU0, downloads `firmware.elf` into DDR (`dow`) and resumes it at the ELF entry "
          "point `_vectors` (`con`)."])
    d.p("Nothing is written to flash; a power cycle returns the board to its blank state. "
        "`machine.reset()` resets the PS through the SLCR, after which the board also waits in the "
        "BootROM for the next `program.sh`.")

    d.section("CPU start-up", label="sec-startup")
    d.p("`startup.S` places the exception vectors at the start of `.text` (0x0010_0000) and enters "
        "`reset_handler` in SVC mode:")
    d.ol(["mask IRQ and FIQ; turn off the MMU, caches, branch prediction and alignment checks left "
          "over from a previous run; point VBAR at `_vectors`;",
          "set up the stacks: 4 KB each for abort and undefined mode, so faults can still be "
          "reported, and the 256 KB SVC stack the firmware runs on;",
          "grant full access to CP10/CP11 and set FPEXC.EN (VFP and NEON);",
          "zero `.bss`, then call `zynq_start()`."])
    d.p("`zynq_start()` in `main.c` builds the translation table and enables the MMU, L1 and L2 caches "
        "(`zynq_mmu_cache_init`), starts the global timer if it is not running, programs UART1 for "
        "115200 8N1 and enters `mp_main()`: GC heap, MicroPython runtime, REPL.")

    # ======================================================================================
    d.chapter("MicroPython Port")
    d.p("`ports/zynq` is an out-of-tree MicroPython port: a Makefile that includes MicroPython's own "
        "make rules from `MICROPY_DIR`, plus a small set of C files. It has no RTOS, no interrupts and "
        "no filesystem; code arrives through the REPL (paste mode, `mpremote run`) or is frozen into "
        "the firmware.")
    d.section("Software architecture")
    d.figure("Software layers, from Python code down to the hardware.", S.fig_stack(), label="fig-stack")
    d.table("Port source files.", ["File", "Contents"], [
        ["`startup.S`", "exception vectors, stacks, VFP enable, `.bss` clearing; faults go to `zynq_fault()`"],
        ["`main.c`", "`zynq_start()`, REPL loop, soft reset, `gc_collect()` roots, fault reporter, no-filesystem stubs"],
        ["`mmu.c` / `mmu.h`", "translation table, L1 and L2 cache set-up, cache maintenance helpers"],
        ["`mphalport.c`", "ticks and delays on the global timer, stdio over UART1"],
        ["`uart.c`", "polled UART1 driver, receive ring buffer, Ctrl-C detection"],
        ["`machine_pin.c`", "`machine.Pin` for LED0 (PS GPIO) and LED1-4, KEY1 (AXI GPIO)"],
        ["`zynq_modmachine.c`", "port part of `machine`: reset, freq, unique_id, idle, sleep"],
        ["`modfft.c`", "`_fft`: C FFT and the PL engine driver"],
        ["`modhdmi.c`", "`_hdmi`: framebuffers and the VDMA driver"],
        ["`modzynq.c`", "`zynq.info()`: MMU and cache state"],
        ["`modules/*.py`", "`fft.py`, `hdmi.py`, `lvhdmi.py`, frozen through `manifest.py`"],
        ["`zynq.ld`", "memory layout in DDR"],
        ["`mpconfigport.h`, `zynq_regs.h`", "MicroPython configuration, register definitions, clock constants"],
    ], widths=[26, 74])

    d.section("Configuration")
    d.table("Main settings in `mpconfigport.h`.", ["Setting", "Value", "Effect"], [
        ["`MICROPY_CONFIG_ROM_LEVEL`", "EXTRA_FEATURES", "most of the language and standard modules"],
        ["`MICROPY_FLOAT_IMPL`", "DOUBLE", "64-bit floats on the VFPv3"],
        ["`MICROPY_LONGINT_IMPL`", "MPZ", "arbitrary-precision integers"],
        ["`MICROPY_EMIT_ARM`", "1", "`@micropython.native` and `@viper` produce ARM code"],
        ["`MICROPY_ENABLE_SCHEDULER`", "1", "scheduled callbacks, keyboard interrupt"],
        ["`MICROPY_VFS`", "0", "no filesystem; `open()` raises ENOENT"],
        ["`MICROPY_VM_HOOK_COUNT`", "64", "UART polled every 64 jumps, calls or returns"],
        ["`MICROPY_PY_MACHINE_PIN_BASE`", "1", "`machine.Pin`, `machine.Signal`"],
        ["`MICROPY_ROM_TEXT_COMPRESSION`", "1", "compressed error messages"],
    ], widths=[36, 20, 44], small=True)

    d.section("Memory", label="sec-mem")
    d.figure("Firmware layout in DDR, from `zynq.ld` and the linked `prebuilt/firmware.elf`.",
             H.fig_ddrmap(), label="fig-ddr")
    d.p("Everything lives in DDR from 0x0010_0000; the first megabyte is left alone because the low OCM "
        "can shadow it. `xsdb` loads the ELF's loadable segments directly, so `.data` has no separate "
        "load address and needs no copying at start-up.")
    d.table("Sections of the LVGL build.", ["Section", "Address", "Size", "Contents"], [
        [".text", "0x0010_0000", "1 353.5 KB", "vectors, code, read-only data, frozen bytecode"],
        [".ARM.exidx, .data", "0x0025_2628", "1.2 KB", "unwind index, initialised data"],
        [".lvgl_pool", "0x0025_2B10", "8 MB", "LVGL's TLSF heap; NOLOAD, not zeroed"],
        [".bss", "0x00A5_4000", "544.6 KB", "zeroed data; 512 KB is the C FFT's twiddle table"],
        [".stack", "0x00AD_C240", "264 KB", "SVC stack 256 KB, ABT and UND stacks 4 KB each"],
        [".heap", "0x00B1_E240", "16 MB", "MicroPython GC heap"],
        [".framebuffer", "0x01C0_0000", "3.52 MB", "two 1280 × 720 RGB565 buffers, 1 MB aligned"],
    ], mono=(1,), widths=[20, 18, 14, 48])
    d.p("`gc_collect()` scans three root regions: the CPU registers and C stack, MicroPython's own "
        "state, and the LVGL pool (see {ref:sec-lvmem}).")

    d.section("Time base")
    d.p("`mp_hal_ticks_ms()` and `ticks_us()` scale the 64-bit global-timer count (333.33 MHz) as "
        "whole seconds plus remainder, which cannot overflow in 64 bits. `ticks_cpu()` returns the raw "
        "count. `sleep_ms()` loops on `mp_event_handle_nowait()`, so the UART keeps being polled and "
        "scheduled callbacks keep running while Python sleeps; `sleep_us()` busy-waits on the "
        "counter.")

    d.section("UART and REPL", label="sec-uart")
    d.figure("Receive and transmit paths of the REPL.", S.fig_uart(), label="fig-uart")
    d.p("UART1 is polled. While Python code runs, the VM calls `zynq_uart_poll()` every 64 backward "
        "jumps, calls or returns (`MICROPY_VM_HOOK_*`), and while it waits or sleeps through "
        "`MICROPY_INTERNAL_EVENT_HOOK`. The poll drains the 64-byte hardware FIFO into a 512-byte ring "
        "buffer; Ctrl-C instead discards pending input and schedules a `KeyboardInterrupt`, so even a "
        "tight Python loop can be stopped. When the REPL itself waits for a key it reads the FIFO "
        "directly, so readline still sees Ctrl-C as an ordinary character.")
    d.listing("ports/zynq/uart.c", """void zynq_uart_poll(void) {
    while (hw_rx_any()) {
        int c = (uint8_t)UART_FIFO;
        if (c == mp_interrupt_char) {
            // Drop anything typed before Ctrl-C, like the other ports do
            rx_tail = rx_head;
            mp_sched_keyboard_interrupt();
            continue;
        }
        uint32_t next = (rx_head + 1u) & (RXBUF_SIZE - 1u);
        if (next != rx_tail) {
            rxbuf[rx_head] = (uint8_t)c;
            rx_head = next;
        }
    }
}""", first_line=56)

    d.section("Faults")
    d.p("All exceptions except reset go to `fault_common`, which switches to the undefined-mode stack "
        "and calls `zynq_fault()`. It prints the exception type and PC over UART1, plus the fault "
        "address and status (DFAR/DFSR or IFAR/IFSR) for aborts, and stops. A data abort between "
        "0x4000_0000 and 0x7FFF_FFFF adds the hint that the bitstream is probably not loaded.")

    d.section("Soft reset")
    d.p("Ctrl-D in the REPL ends `pyexec`, and `mp_main()` reinitialises the runtime: it calls "
        "`zynq_lvgl_deinit()` (a weak empty function unless LVGL is linked in), sweeps the heap with "
        "`gc_sweep_all()`, then `mp_deinit()` and `mp_init()`. Hardware state (PL, VDMA, caches) is "
        "kept; the next `hdmi.Display()` or `lvhdmi.init()` resets the VDMA itself.")

    d.section("Testing in QEMU")
    d.p("`./build.sh qemu` builds a variant for QEMU's `xilinx-zynq-a9` machine, which models the PS "
        "(UART1, timers, DDR) but no PL. That build points the AXI GPIO at a DDR scratch word "
        "(0x1FF0_0000) so `machine.Pin` still works; the FFT engines report “not available”, "
        "and `hdmi.Display(hardware=False)` and `lvhdmi.init(hardware=False)` render without the "
        "VDMA. `tools/qemu_fb.py` runs a script in QEMU and dumps a framebuffer to PNG through the "
        "QEMU monitor; with `QEMU_EXTRA=\"-icount shift=1\"` guest time follows instruction count "
        "(2 ns each), which gives realistic CPU timings apart from cache and DDR effects.")

    # ======================================================================================
    d.chapter("Hardware Drivers")
    d.section("machine")
    d.table("Port-specific `machine` functions.", ["Function", "Behaviour"], [
        ["`machine.freq()`", "666 666 667 (`ZYNQ_CPU_HZ`); setting it raises NotImplementedError, ps7_init owns the clocks"],
        ["`machine.reset()`", "PS system reset through SLCR PSS_RST_CTRL; the board then waits in the BootROM"],
        ["`machine.reset_cause()`", "SLCR REBOOT_STATUS bits 22:16 (SWDT, AWDT0/1, SLC, BootROM, POR, SRST_B)"],
        ["`machine.unique_id()`", "the 4-byte PS IDCODE (the PS has no serial number)"],
        ["`machine.idle()`", "polls the UART"],
        ["`machine.lightsleep(ms)`", "a delay; `deepsleep` delays, then resets"],
        ["`machine.mem8/16/32`", "raw access to any address, e.g. PL registers"],
    ], widths=[26, 74])

    d.section("machine.Pin")
    d.table("Pins.", ["Name", "Hardware", "Modes", "Notes"], [
        ["LED0", "PS GPIO bank 0, MIO9", "IN, OUT", "MIO9 switched to GPIO, LVCMOS33, on first use"],
        ["LED1-LED4", "AXI GPIO channel 1, bits 0-3", "OUT", "written from a shadow register"],
        ["KEY1", "AXI GPIO channel 2, bit 0", "IN", "0 when pressed; `machine.Signal(..., invert=True)`"],
    ], widths=[13, 30, 12, 45])
    d.p("PS GPIO writes use the MASK_DATA register, which changes single bits without "
        "read-modify-write. Pins implement the virtual pin protocol, so they work with "
        "`machine.Signal`, and `asyncio` code can drive them like on any other port.")

    d.section("fft", label="sec-fftdrv")
    d.p("`fft.py` (frozen) offers one interface over four implementations. `fft.fft(x, method)` and "
        "`fft.ifft(X, method)` take and return lists of complex numbers; `fft.run(re, im, method, "
        "inverse)` works in place on two `array('d')`. All methods return the same convention: "
        "forward = Σ x[n]e^(−j2πkn/N), inverse = (1/N) Σ X[k]e^(+j2πkn/N).")
    d.table("FFT methods.", ["Method", "Where", "Arithmetic", "Sizes"], [
        ["`\"python\"`", "CPU0, bytecode", "double, radix-2 in Python", "any power of 2"],
        ["`\"c\"`", "CPU0, `_fft.c`", "double, VFPv3, cached twiddle table", "up to 65 536"],
        ["`\"xilinx\"`", "PL, xfft v9.1", "16-bit in, unscaled 27-bit out", "8 to 1024"],
        ["`\"verilog\"`", "PL, myfft_axil", "Q1.15, ½ per stage, saturating", "8 to 1024"],
    ], widths=[15, 25, 38, 22])
    d.figure("`fft.run(re, im, \"verilog\")`: one transform on a PL engine.", S.fig_fftseq(), label="fig-fftseq")
    d.p("The driver probes the engine's ID register first and raises `OSError` with a hint if the "
        "bitstream is not loaded. It scales the input into 16 bits (for FORMAT 0 so that every "
        "complex magnitude stays below 0.9 of full scale), runs the transform with a one-second "
        "timeout, and scales the result back. `fft.benchmark()` compares the methods; for the PL "
        "engines it also reports the engine's own CYCLES count, which excludes the AXI transfers.")

    d.section("hdmi", label="sec-hdmidrv")
    d.table("`_hdmi` (C) and `hdmi` (frozen Python).", ["Function", "Behaviour"], [
        ["`_hdmi.init()`", "check the VDMA, reset it, clear both buffers, program addresses, stride and size, park on buffer 0"],
        ["`_hdmi.buffer(i)`", "`bytearray` view of framebuffer i (1280 × 720 × 2 bytes)"],
        ["`_hdmi.show(i, wait=True)`", "clean buffer i from the D-cache, park the VDMA on it, optionally wait for the switch"],
        ["`_hdmi.flush(i)`", "only the cache clean"],
        ["`_hdmi.status()`", "running, halted, error, frame, mmcm_locked, video_locked, underflow, vdma_sr"],
        ["`_hdmi.stop()`, `available()`", "halt the VDMA; check that it answers"],
        ["`hdmi.Display(double_buffer, hardware)`", "a `framebuf.FrameBuffer` (RGB565) on a framebuffer; `show()` presents it"],
        ["`hdmi.text(fb, s, x, y, color, scale)`", "scaled 8 × 8 text; `rgb()` and colour constants"],
    ], widths=[34, 66])
    d.figure("Presenting a frame: cache clean, park, wait for the VDMA to switch.", S.fig_present(), label="fig-present")
    d.listing("ports/zynq/modhdmi.c", """bool zynq_hdmi_present(uint32_t i, bool wait) {
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
}""", first_line=133)
    d.p("`zynq_hdmi_present()` is shared by `_hdmi.show()` and the LVGL driver. Waiting for the "
        "switch is what makes double buffering safe: when it returns, the VDMA is reading buffer i, "
        "so the other buffer can be drawn without tearing.")

    d.section("zynq")
    d.p("`zynq.info()` returns a dictionary with the live MMU and cache state (`mmu`, `dcache`, "
        "`icache`, `branch_pred`, `l2`), the raw SCTLR and ACTLR values and `cpu_hz`. It exists to "
        "check a board quickly when performance looks wrong: on the board all five flags should be `True`. "
        "(In QEMU `l2` reads `False`, because QEMU does not keep the L2 controller's enable bit.)")

    # ======================================================================================
    d.chapter("LVGL Integration")
    d.p("LVGL v9.6 is linked into the firmware through the official MicroPython binding, "
        "lv_binding_micropython, which generates the `lvgl` module from LVGL's headers. A small "
        "display driver connects it to the HDMI framebuffers.")
    d.section("Overview")
    d.figure("LVGL in the firmware: binding, core, memory pool and display driver.", S.fig_lvgl(), label="fig-lvgl")
    d.table("`lvhdmi` (frozen) and `_lvhdmi` (C).", ["Function", "Behaviour"], [
        ["`lvhdmi.init(hardware=None, dark=True, ...)`", "`lv.init()`, start HDMI if the bitstream is there, create the display, apply the default theme; returns the `lv.display`"],
        ["`lvhdmi.run(duration_ms=None)`", "main loop: `lv.timer_handler()`, then sleep up to 5 ms; Ctrl-C stops it"],
        ["`lvhdmi.task(period_ms=5)`", "the same loop as an `asyncio` task"],
        ["`lvhdmi.frames()`", "frames presented since `init()`"],
        ["`lvhdmi.stats(reset=False)`", "(frames, areas, pixels, tick_calls, present_ms, full_redraws)"],
        ["`lvhdmi.mem()`", "(total, used, frag_pct) of the LVGL pool"],
    ], widths=[38, 62])

    d.section("Build integration", label="sec-lvbuild")
    d.p("The Makefile adds `usermods/` as `USER_C_MODULES` when `LVGL=1` (the default). That directory "
        "holds the binding (fetched by `build.sh` at a fixed commit, with LVGL v9.6.0 cloned inside it) "
        "and the `lvgl_hdmi` driver module. During the build, the binding preprocesses `lvgl.h` with "
        "`lv_conf.h` and runs `gen_mpy.py`, which parses the result with pycparser and writes "
        "`lv_mpy.c`, about 2.2 MB of C that defines every LVGL type, function, enum and callback for "
        "Python.")
    d.p("One patch is needed for MicroPython 1.29, which removed `mp_obj_int_to_bytes_impl()`: "
        "`build.sh` rewrites the generator's call to the new `mp_obj_int_to_bytes()` with `sed`, "
        "idempotently. LVGL and generated code compile with warnings visible but not fatal; the port's "
        "own sources stay `-Werror`. Building with `LVGL=0` leaves all of it out.")

    d.section("Display driver", label="sec-lvdrv")
    d.p("`_lvhdmi.create()` gives LVGL the two HDMI framebuffers themselves as draw buffers, in "
        "`LV_DISPLAY_RENDER_MODE_DIRECT`. LVGL renders each frame into the buffer that is not on "
        "screen, at the pixels' final positions, so nothing is ever copied; in this mode LVGL also "
        "copies the areas it redrew in the previous frame into the new buffer, keeping the two in "
        "sync.")
    d.listing("usermods/lvgl_hdmi/lvgl_hdmi.c", """static mp_obj_t lvhdmi_create(void) {
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
}""", first_line=78)
    d.p("LVGL calls the flush callback once per redrawn area. The driver acts only on the last one of a "
        "frame: it works out which buffer `px_map` points to and hands it to "
        "`zynq_hdmi_present(i, true)`, which cleans the whole buffer from the cache, parks the VDMA on "
        "it and waits for the switch. Only then does it call `lv_display_flush_ready()`, so LVGL never "
        "starts drawing into the buffer on screen, and the frame rate is capped at the display's "
        "60 Hz.")
    d.figure("Double buffering in DIRECT mode over four video frames.", S.fig_lvtimeline(), label="fig-lvtime")
    d.note("The whole 1.76 MB buffer is cleaned, not just the flushed areas, because the DIRECT-mode "
           "sync copies of the previous frame's areas must reach DDR too. Cleaning lines that are "
           "already clean is cheap; the measured present time is a small part of the frame budget.")

    d.section("Memory and the garbage collector", label="sec-lvmem")
    d.figure("Who refers to what: the LVGL pool is a GC root region.", S.fig_gc(), label="fig-gc")
    d.p("The binding's default, `LV_STDLIB_MICROPYTHON`, makes LVGL allocate from the MicroPython GC "
        "heap. LVGL allocates and frees draw buffers and layers every frame, and MicroPython's "
        "allocator searches its block table linearly for each multi-block request. With a 16 MB heap "
        "that search took about 80 % of the CPU and the demo dashboard ran at about 1 fps on the "
        "board.")
    d.p("The firmware therefore uses LVGL's built-in TLSF allocator (`LV_STDLIB_BUILTIN`) with an "
        "8 MB pool. `LV_ATTRIBUTE_LARGE_RAM_ARRAY` places the pool in its own section, `.lvgl_pool`, "
        "which the linker script brackets with `_lv_pool_start` and `_lv_pool_end`. Because LVGL "
        "objects in the pool can hold the only reference to a Python callback, `gc_collect()` scans "
        "the pool as a root region:")
    d.listing("ports/zynq/main.c", """extern void *_lv_pool_start[], *_lv_pool_end[];

void gc_collect(void) {
    gc_collect_start();
    gc_helper_collect_regs_and_stack();
    gc_collect_root(_lv_pool_start, _lv_pool_end - _lv_pool_start);
    gc_collect_end();
}""", first_line=68)
    d.p("The scan is conservative: any word that looks like a pointer into the heap keeps that block "
        "alive. At soft reset `zynq_lvgl_deinit()` calls `lv_deinit()`, which also resets the pool, "
        "before the heap is swept.")

    d.section("Tick and main loop")
    d.p("LVGL's tick comes from `lv_tick_set_cb()` with a callback returning `mp_hal_ticks_ms()`, so no "
        "timer interrupt is needed. `lvhdmi.run()` calls `lv.timer_handler()`, which runs due LVGL "
        "timers and animations, Python timer callbacks included, and redraws invalidated areas, then "
        "sleeps for the time LVGL asks for, at most 5 ms. The refresh period is 16 ms "
        "(`LV_DEF_REFR_PERIOD`), and the VDMA wait aligns frames to the 60 Hz output.")

    d.section("Configuration")
    d.table("Settings changed in `usermods/lv_conf.h` (from the binding's default).", ["Setting", "Value", "Reason"], [
        ["`LV_COLOR_DEPTH`", "16", "RGB565, the framebuffer format"],
        ["`LV_USE_STDLIB_MALLOC`", "`LV_STDLIB_BUILTIN`", "TLSF allocator, see {ref:sec-lvmem}"],
        ["`LV_MEM_SIZE`", "8 MB", "pool size"],
        ["`LV_ATTRIBUTE_LARGE_RAM_ARRAY`", "`section(\".bss.lvgl_pool\")`", "places the pool for the linker script"],
        ["`LV_DEF_REFR_PERIOD`", "16", "about 60 Hz"],
        ["`LV_INV_BUF_SIZE`", "64", "more invalidated areas per frame before a full-screen redraw (default 32)"],
        ["`LV_FONT_MONTSERRAT_*`", "12-48", "12, 14, 16, 20, 24, 28, 36, 48"],
        ["`LV_USE_SYSMON`", "1", "FPS and CPU overlay in the bottom-right corner"],
        ["`LV_USE_OS`", "`LV_OS_NONE`", "single-threaded, no locking"],
    ], widths=[34, 28, 38], small=True)

    d.section("Performance", label="sec-perf")
    d.figure("CPU time per frame for the full demo dashboard, before and after the allocator change.",
             S.fig_perf(), label="fig-perf")
    d.p("The figures come from QEMU with `-icount shift=1`, which models a 666 MHz A9 by instruction "
        "count but not its caches or DDR; the board is expected to be in the same range. The profile "
        "was taken with QEMU's hot-block plugin, folded by function.")
    d.table("Measurements of `examples/lvgl_demo.py` (1280 × 720, eight animated cards).", ["Quantity", "Before", "After"], [
        ["Frames per second", "26.4", "62.6 (QEMU, no vsync wait); 60 on HDMI"],
        ["CPU in `lv.timer_handler()` per frame", "35.2 ms", "3.2 ms (19 % of the CPU at 60 fps)"],
        ["Longest single `timer_handler()` call", "120.6 ms", "5.2 ms"],
        ["Top function in the profile", "`gc_alloc` 80 %", "`lv_draw_sw_blend_color_to_rgb565` 14 %"],
        ["Pixels redrawn per frame", "-", "about 111 000 (12 % of the screen), no full-screen redraws"],
        ["LVGL pool in use", "-", "20 KB of 8 MB"],
        ["20 s run, GC heap", "-", "stable; 1 250 frames"],
    ], widths=[34, 22, 44])
    d.p("Two smaller issues in the demo itself cost frames as well. Updating 32 chart bars one by one "
        "produced more invalidated areas than LVGL's buffer holds, which forces a full-screen redraw; "
        "the demo now turns invalidation off while it changes the values and invalidates the chart "
        "once. And a once-a-second `gc.mem_free()` walked the whole 16 MB heap, about 0.1 s per call. "
        "`examples/lvgl_perf.py` reports frames per second, CPU load, redraw size and memory on the "
        "board.")

    # ======================================================================================
    d.chapter("Build Options and Commands", appendix_letter="A")
    d.table("Commands.", ["Command", "Result"], [
        ["`./build.sh`", "hardware and firmware"],
        ["`./build.sh hw`", "`hw/build/system.bit`, `ps7_init.tcl`, reports (Vivado batch)"],
        ["`./build.sh fw`", "`ports/zynq/build/firmware.elf`; fetches MicroPython, LVGL and the binding on first use"],
        ["`./build.sh qemu`", "QEMU firmware and its REPL (Ctrl-A x quits)"],
        ["`./build.sh sim`", "iverilog simulations of the FFT engines and the HDMI transmitter"],
        ["`./build.sh clean`", "remove firmware build output (needed when switching `LVGL`)"],
        ["`./program.sh [bit] [ps7_init] [elf]`", "load everything over JTAG"],
        ["`mpremote connect PORT run file.py`", "run a script from the PC"],
    ], widths=[38, 62])
    d.table("Make variables of `ports/zynq/Makefile`.", ["Variable", "Default", "Meaning"], [
        ["`MICROPY_DIR`", "-", "MicroPython source tree (set by `build.sh`)"],
        ["`LVGL`", "1", "link LVGL and the `lvgl_hdmi` driver"],
        ["`MMU`", "1", "0: no MMU, no D-cache, no L2 (I-cache only)"],
        ["`L2`", "1", "0: leave the L2 cache off"],
        ["`HEAP_SIZE`", "16M", "GC heap size"],
        ["`STACK_SIZE`", "256K", "SVC stack size"],
        ["`QEMU`", "0", "1: QEMU variant in `build-qemu/`"],
        ["`DEBUG`", "0", "1: `-O0`, assertions on"],
        ["`CROSS_COMPILE`", "arm-none-eabi-", "toolchain prefix"],
    ], widths=[22, 20, 58])

    d.chapter("Documentation Release History", appendix_letter="B")
    d.table("Release history.", ["Date", "Description"], [
        ["16 November 2026", "Initial release: PS/PL architecture, FFT engines, HDMI pipeline, MicroPython "
                             "port, drivers and LVGL v9.6 integration, including the LVGL allocator change."],
    ], widths=[22, 78])
