"""Chapters 1 and 2: introduction and processing system."""
import figs_hw as H


def build(d):
    # ======================================================================================
    d.chapter("Introduction")
    d.section("Summary")
    d.p("ZYNQ ZERO MicroPython turns the ZYNQ ZERO board, built around a Xilinx Zynq-7010, into a "
        "MicroPython computer. CPU0 of the Cortex-A9 pair runs a bare-metal MicroPython port, and the "
        "programmable logic (PL) adds peripherals that Python code reaches over AXI: GPIO, two FFT "
        "engines and a 720p HDMI output. On top of that the firmware carries the LVGL v9.6 graphics "
        "library, drawing straight into the video framebuffers.")
    d.p("This document describes how the system is put together, from the Zynq configuration and the "
        "Verilog modules to the MicroPython port, its drivers and the LVGL integration. Every address, "
        "clock and size in it is taken from the project sources and the linked firmware.")
    d.ul([
        ("Processor: Cortex-A9 CPU0 at 666.67 MHz, bare metal", [
            "ARM (A32) code, VFPv3 double-precision floating point",
            "MMU with a flat map, L1 I/D caches 32 KB each, 512 KB L2 cache",
            "CPU1 stays parked in the BootROM"]),
        ("Memory: 512 MB DDR3 (16-bit, 1066 MT/s)", [
            "16 MB MicroPython GC heap, 8 MB LVGL pool, two 1.76 MB framebuffers"]),
        ("MicroPython v1.29.0", [
            "REPL on UART1 at 115200 8N1 through the on-board CH340",
            "`asyncio`, native and viper code emitters, frozen modules"]),
        ("PL peripherals on M_AXI_GP0 (AXI4-Lite)", [
            "AXI GPIO for LED1-LED4 and KEY1, exposed as `machine.Pin`",
            "FFT engine written in Verilog (radix-2, one butterfly per clock)",
            "Xilinx FFT LogiCORE behind a Verilog AXI4-Lite front end",
            "AXI VDMA control and a video status register"]),
        ("HDMI output, 1280 × 720 at 60 Hz", [
            "RGB565 framebuffers in DDR, read by an AXI VDMA over S_AXI_HP0",
            "Xilinx video IP for streaming and timing, own TMDS transmitter in Verilog"]),
        "FFT in four implementations behind one API: Python, C, Xilinx IP and own Verilog",
        "LVGL v9.6 with a zero-copy, tear-free display driver; 60 fps for a full dashboard",
        "Script-only build (Vivado 2021.1 batch, GNU Arm toolchain), JTAG loading, QEMU target for testing",
    ])

    d.section("The board", label="board")
    d.p("The ZYNQ ZERO (rev B) is a small Zynq-7010 board. The design uses the resources in "
        "{ref:tab-board}; everything else (QSPI flash, SD card, header I/O) is left unconfigured "
        "and can be added later in `ps7_config.tcl` and the block design.")
    d.table("ZYNQ ZERO resources used by the design.", ["Resource", "Part / pin", "Connection", "Used for"], [
        ["SoC", "XC7Z010-1CLG400C (U5)", "-", "PS + PL"],
        ["DDR3", "MT41J256M16, 512 MB", "PS bank 502, 1.5 V, x16", "all code and data"],
        ["PS clock", "X2, 33.333 MHz", "PS_CLK (E7)", "PS PLL reference"],
        ["USB-UART", "CH340", "UART1, MIO48 TX / MIO49 RX, 1.8 V", "REPL"],
        ["USB-JTAG", "FTDI (ADBUS0-3)", "TCK, TDI, TDO, TMS", "programming, download"],
        ["LED0", "R38", "MIO9, bank 500, 3.3 V", "`Pin(\"LED0\")`"],
        ["LED1-LED4", "4.7 kΩ + LED", "PL W13, V12, U12, T12 (bank 34)", "`Pin(\"LED1\")`..."],
        ["KEY1", "R37 4.7 kΩ pull-up", "PL Y16 (bank 34)", "`Pin(\"KEY1\")`, 0 = pressed"],
        ["HDMI", "J1", "PL bank 35, TMDS_33", "720p60 video (DVI)"],
        ["Reset", "MAX809T + KEY2", "PS_POR_B", "power-on reset"],
    ], label="tab-board", widths=[13, 25, 33, 29])
    d.note("The HDMI DDC level shifter (U15) is not fitted on this board, so the design cannot read the "
           "monitor's EDID. It always sends 1280 × 720 at 60 Hz, which every HDMI display accepts.")

    d.section("System overview", label="overview")
    d.figure("System overview: the Zynq-7010 with its PS and PL halves and the board components "
             "around them.", H.fig_system(), label="fig-system")
    d.p("{ref:fig-system} shows the two halves of the chip and how they meet. The PS boots and runs "
        "the firmware out of DDR3. The CPU reaches the PL through the general-purpose master port "
        "M_AXI_GP0, an AXI interconnect fanning out to five AXI4-Lite slaves: the LED/key GPIO, the "
        "two FFT engines, the VDMA's control port and a video status GPIO. In the other direction, "
        "the VDMA reads the framebuffers out of DDR through the high-performance slave port S_AXI_HP0 "
        "and streams them to the HDMI transmitter.")
    d.p("There are no interrupts anywhere in the system. The UART, the FFT engines and the video DMA are "
        "all polled, which keeps the bare-metal port small and its timing easy to follow.")
    d.table("Where each function runs.", ["Function", "Runs on", "Implementation"], [
        ["Python interpreter, REPL", "PS, CPU0", "MicroPython v1.29.0, `ports/zynq`"],
        ["LED0", "PS GPIO", "MIO9 through the PS GPIO controller"],
        ["LED1-LED4, KEY1", "PL", "Xilinx AXI GPIO"],
        ["FFT `\"python\"`, `\"c\"`", "PS, CPU0", "`fft.py`, `modfft.c`"],
        ["FFT `\"verilog\"`", "PL", "`myfft_axil.v` (own radix-2 core)"],
        ["FFT `\"xilinx\"`", "PL", "Xilinx FFT v9.1 + `xfft_ctrl.v`"],
        ["Framebuffer drawing (framebuf, LVGL)", "PS, CPU0", "`hdmi.py`, LVGL software renderer"],
        ["Scan-out, timing, colour conversion", "PL", "AXI VDMA, VTC, AXI4-Stream to Video Out, subset converter"],
        ["TMDS encoding and serialisation", "PL", "`hdmi_tx.v`, `tmds_encoder.v`"],
    ], widths=[34, 16, 50])

    d.section("Source tree")
    d.table("Repository layout.", ["Path", "Contents"], [
        ["`build.sh`", "builds the hardware, the firmware, the QEMU variant; runs the simulations"],
        ["`program.sh`, `scripts/program.tcl`", "loads bitstream, PS init and firmware over JTAG"],
        ["`hw/rtl/`", "Verilog: `axil_slave`, `tdp_ram`, `twiddle_rom`, `myfft_axil`, `xfft_ctrl`, `tmds_encoder`, `hdmi_tx`"],
        ["`hw/scripts/`", "`build.tcl` (block design + implementation), `ps7_config.tcl` (PS settings)"],
        ["`hw/constraints/`", "pins (`zynq_zero.xdc`), clock groups (`zynq_zero_timing.xdc`)"],
        ["`hw/sim/`", "iverilog testbenches for the FFT engines and the HDMI path, checked against numpy"],
        ["`ports/zynq/`", "the MicroPython port: C sources, `startup.S`, `zynq.ld`, Makefile, frozen modules"],
        ["`usermods/`", "`lvgl_hdmi` display driver, `lv_conf.h`; LVGL and its binding are fetched here"],
        ["`examples/`", "blink, knight_rider, async_leds, fft_demo, hdmi_demo, lvgl_demo, lvgl_perf"],
        ["`tools/`", "QEMU helpers: scripted REPL, framebuffer dump to PNG"],
        ["`prebuilt/firmware.elf`", "firmware built with LVGL, ready for `program.sh`"],
    ], widths=[30, 70])

    # ======================================================================================
    d.chapter("Processing System")
    d.p("The Zynq PS is configured once, in `hw/scripts/ps7_config.tcl`. Vivado turns those settings into "
        "`ps7_init.tcl`, which `program.sh` runs over JTAG before the firmware starts. The firmware "
        "itself never touches the PLLs, the DDR controller or the MIO multiplexer, apart from switching "
        "MIO9 to GPIO for LED0.")
    d.section("Configuration")
    d.figure("Processing system blocks and how the design uses them.", H.fig_ps(), label="fig-ps")
    d.table("PS7 settings (`ps7_config.tcl`).", ["Parameter", "Value", "Why"], [
        ["`PCW_CRYSTAL_PERIPHERAL_FREQMHZ`", "33.333333", "X2 oscillator on PS_CLK"],
        ["`PCW_APU_PERIPHERAL_FREQMHZ`", "666.666666", "CPU clock; `ZYNQ_CPU_HZ` in the port"],
        ["`PCW_PRESET_BANK0_VOLTAGE`", "LVCMOS 3.3V", "MIO0-15 (strap MIO7 = 0)"],
        ["`PCW_PRESET_BANK1_VOLTAGE`", "LVCMOS 1.8V", "MIO16-53 (strap MIO8 = 1)"],
        ["`PCW_UIPARAM_DDR_MEMORY_TYPE`", "DDR 3", ""],
        ["`PCW_UIPARAM_DDR_PARTNO`", "MT41J256M16 RE-125", "timing parameters for the fitted part"],
        ["`PCW_UIPARAM_DDR_BUS_WIDTH`", "16 Bit", "one x16 device"],
        ["`PCW_UART1_UART1_IO`", "MIO 48 .. 49", "CH340"],
        ["`PCW_UART_PERIPHERAL_FREQMHZ`", "100", "`ZYNQ_UART_REF_HZ` in the port"],
        ["`PCW_GPIO_MIO_GPIO_ENABLE`", "1", "LED0 on MIO9"],
        ["`PCW_USE_M_AXI_GP0`", "1", "CPU → PL registers"],
        ["`PCW_FPGA0_PERIPHERAL_FREQMHZ`", "100", "FCLK_CLK0, the PL's main clock"],
        ["`PCW_USE_S_AXI_HP0`, `_DATA_WIDTH`", "1, 64", "VDMA → DDR"],
        ["QSPI, SD0/1, UART0, ENET0/1, USB0/1, I2C0/1", "disabled", "not used yet"],
    ], mono=(1,), widths=[42, 22, 36], small=True, label="tab-ps7")

    d.section("Processor")
    d.p("The APU is a dual Cortex-A9 MPCore. MicroPython runs on CPU0 only; CPU1 is left in the "
        "BootROM's wait-for-event loop, where JTAG boot leaves it. The firmware is built as ARM (A32) "
        "code with `-mcpu=cortex-a9 -marm -mfpu=vfpv3 -mfloat-abi=softfp`. MicroPython floats are "
        "doubles (`MICROPY_FLOAT_IMPL_DOUBLE`), computed by the VFPv3 unit, and `sqrt` uses the "
        "hardware instruction. NEON is enabled at start-up but the compiler is not asked to use it.")
    d.p("The ARM global timer, a 64-bit counter in the MPCore private region, is the system's time base. "
        "It runs at CPU_3x2x, half the CPU clock (333.33 MHz). All of `time.ticks_ms()`, "
        "`ticks_us()`, `ticks_cpu()`, the delays and the LVGL tick derive from it.")

    d.section("Clocks", label="clocks")
    d.figure("Clock tree. PLL frequencies are those Vivado derives for this configuration; "
             "`hw/build/ps7_init.html` lists the exact divider settings.", H.fig_clocks(), label="fig-clocks")
    d.table("Clocks the design depends on.", ["Clock", "Frequency", "Source", "Consumers"], [
        ["CPU_6x4x", "666.67 MHz", "ARM PLL", "Cortex-A9 cores, L1"],
        ["CPU_3x2x", "333.33 MHz", "ARM PLL", "global timer (`ZYNQ_GTIMER_HZ`), SCU"],
        ["DDR_3x", "533.33 MHz", "DDR PLL", "DDR3 controller (1066 MT/s, 16-bit: 2.1 GB/s peak)"],
        ["UART_REF", "100 MHz", "IO PLL", "UART1 baud generator"],
        ["FCLK_CLK0 (clk_fpga_0)", "100 MHz", "IO PLL", "every AXI block in the PL"],
        ["pixel clock", "74.25 MHz", "clk_wiz_hdmi CLKOUT0", "VTC, video out, TMDS encoders, OSERDES CLKDIV"],
        ["serial clock", "371.25 MHz", "clk_wiz_hdmi CLKOUT1", "OSERDESE2 CLK (DDR: 742.5 Mb/s)"],
    ], widths=[20, 17, 21, 42])

    d.section("Address map", label="amap")
    d.figure("System address map with the MMU attribute of each region.", H.fig_addrmap(), label="fig-amap")
    d.table("Address map summary.", ["Region", "Base", "Size", "Contents"], [
        ["DDR3", "0x0000_0000", "512 MB", "firmware from 0x0010_0000 (see {ref:sec-mem})"],
        ["M_AXI_GP0", "0x4000_0000", "1 GB window", "PL slaves, see {ref:tab-gp0}"],
        ["UART1", "0xE000_1000", "4 KB", "REPL"],
        ["GPIO", "0xE000_A000", "4 KB", "MIO9 (LED0)"],
        ["SLCR", "0xF800_0000", "4 KB", "MIO mux, resets, IDCODE, L2 RAM latency"],
        ["Global timer", "0xF8F0_0200", "-", "64-bit counter, 333.33 MHz"],
        ["L2 cache controller", "0xF8F0_2000", "4 KB", "PL310"],
        ["OCM (high)", "0xFFFC_0000", "256 KB", "BootROM area; CPU1 waits here"],
    ], mono=(1,), widths=[20, 18, 14, 48])

    d.section("MMU and caches", label="mmu")
    d.p("`mmu.c` builds a flat translation table (virtual = physical) of 4096 one-megabyte sections and "
        "turns on the MMU, both L1 caches, branch prediction and the L2 cache. {ref:tab-mmu} lists the "
        "section types.")
    d.table("Translation table sections (`mmu.c`).", ["Range", "Type", "Descriptor", "Why"], [
        ["0x0000_0000-0x3FFF_FFFF", "Normal, inner + outer write-back write-allocate", "TEX=001 C=1 B=1",
         "code and data, cached in L1 and L2"],
        ["framebuffer sections (0x01C0_0000-0x01FF_FFFF)", "Normal, inner WB-WA, outer non-cacheable",
         "TEX=100 C=0 B=1", "L1 only, see below"],
        ["0x4000_0000-0xBFFF_FFFF", "Strongly-ordered, execute-never", "TEX=000 C=0 B=0 XN",
         "PL registers: a read never overtakes a write"],
        ["0xC000_0000-0xFFEF_FFFF", "Device, execute-never", "TEX=000 C=0 B=1 XN", "PS peripherals"],
        ["0xFFF0_0000-0xFFFF_FFFF", "Normal, WB-WA", "TEX=001 C=1 B=1", "high OCM"],
    ], label="tab-mmu", widths=[27, 29, 18, 26], small=True)
    d.h4("L2 cache")
    d.p("The PL310 is set up the way Xilinx's standalone BSP does it: the SLCR L2 RAM latency register "
        "(0xF800_0A1C) is written with 0x0002_0202, the auxiliary control register gets 8 ways of 64 KB "
        "with instruction and data prefetch and early BRESP (0x7236_0000), tag and data RAM latencies "
        "are 0x111 and 0x121, all ways are invalidated, and the controller is enabled. If the L2 is "
        "already on, left over from an earlier run reloaded over JTAG, it is switched off and "
        "invalidated first, so lines belonging to the old image are dropped rather than written back. "
        "Building with `L2=0` leaves it off; `MMU=0` runs with the I-cache only.")
    d.h4("Coherency with the PL")
    d.p("S_AXI_HP0 goes straight to the DDR controller and is not coherent with either cache level. "
        "The VDMA would read stale data wherever the CPU's writes still sit in a cache. The design "
        "handles this in two steps:")
    d.ul(["The framebuffers get their own 1 MB-aligned sections, mapped outer non-cacheable. They are "
          "cached in L1, so drawing stays fast, but never allocate in L2.",
          "Before a buffer is shown, the driver cleans it from L1 by address (DCCMVAC, 32-byte lines, "
          "then DSB). With L2 out of the picture that is enough to put every pixel in DDR."])
    d.p("Native and viper code is handled the same way: after the emitter writes machine code, "
        "`zynq_cache_sync_code()` cleans the range to the point of unification (DCCMVAU) and "
        "invalidates the I-cache and branch predictor.")

    d.section("PS peripherals and MIO")
    d.table("PS peripherals used by the firmware.", ["Peripheral", "Base", "Registers used", "Driver"], [
        ["UART1 (Cadence)", "0xE000_1000", "CR, MR, IDR, BAUDGEN, SR, FIFO, BAUDDIV", "`uart.c`"],
        ["GPIO bank 0", "0xE000_A000", "MASK_DATA_0_LSW, DATA_0_RO, DIRM_0, OEN_0", "`machine_pin.c`"],
        ["SLCR", "0xF800_0000", "LOCK/UNLOCK, MIO_PIN_09, APER_CLK_CTRL, PSS_RST_CTRL, REBOOT_STATUS, PSS_IDCODE, L2C_RAM",
         "`machine_pin.c`, `zynq_modmachine.c`, `mmu.c`"],
        ["Global timer", "0xF8F0_0200", "COUNT_LO/HI, CTRL", "`mphalport.c`"],
        ["L2 cache controller", "0xF8F0_2000", "CNTRL, AUX_CNTRL, TAG/DATA_RAM, INV_WAY, CACHE_SYNC", "`mmu.c`"],
    ], mono=(1,), widths=[18, 15, 44, 23], small=True)
    d.p("UART1 runs at 115200 baud from its 100 MHz reference: with BDIV = 6 the baud generator divisor "
        "is CD = round(100 MHz / (7 × 115200)) = 124, giving 115 207 baud (+0.006 %).")

    d.section("PS-PL interfaces", label="pspl")
    d.table("PS-PL interfaces enabled.", ["Interface", "Direction", "Width", "Use"], [
        ["M_AXI_GP0", "PS master → PL", "32-bit AXI3, 0x4000_0000-0x7FFF_FFFF", "registers of all PL peripherals"],
        ["S_AXI_HP0", "PL master → DDR", "64-bit AXI3", "VDMA framebuffer reads"],
        ["FCLK_CLK0", "PS → PL", "100 MHz", "PL main clock"],
        ["FCLK_RESET0_N", "PS → PL", "active low", "reset for both PL clock domains"],
    ], widths=[18, 20, 30, 32])
    d.note("`ps7_post_config` in `program.tcl` enables the PS-PL level shifters after the bitstream is "
           "loaded. Until then any access to 0x4000_0000 and up fails, and the firmware's fault handler "
           "reports it as “PL address: is the bitstream loaded?”.")
