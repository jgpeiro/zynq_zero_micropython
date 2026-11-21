"""Hardware diagrams: system, PS, clocks, address map, PL block design."""
from svglib import Svg, PS, PL, XIP, RTL, MEM, EXT, SW, WHITE, INK, ACCENT, GREY


def legend_hw(s, x, y):
    s.legend(x, y, [(PS, "PS"), (PL, "PL region"), (XIP, "Xilinx IP"), (RTL, "own Verilog"),
                    (MEM, "memory"), (EXT, "off-chip")])


def fig_system():
    s = Svg(700, 430, "sys")
    # Off-chip, left
    left = [("DDR3 SDRAM", "MT41J256M16, x16\n512 MB, 1.5 V", 30, 62),
            ("CH340 USB-UART", "115200 8N1\nREPL", 112, 48),
            ("USB-JTAG", "FTDI ADBUS\nxsdb / hw_server", 178, 48),
            ("LED0", "active high", 244, 34),
            ("Oscillator X2", "PS_CLK 33.333 MHz", 296, 40),
            ("Reset", "MAX809T + KEY2\nPS_POR_B", 354, 44)]
    for name, sub, y, h in left:
        s.box(6, y, 106, h, name, EXT, sub, fs=9.2, sfs=7.4)
    # Chip
    s.rect(150, 14, 400, 404, "#fbfbfb", INK, 1.4, 4)
    s.text(160, 26, "XC7Z010-1CLG400C (U5)", 10, "start", "700")
    # PS
    s.rect(162, 40, 186, 368, PS, "#2f5f8a", 1.1, 3)
    s.text(172, 52, "Processing System (PS)", 9.5, "start", "700", "#1f4466")
    s.box(172, 62, 166, 54, "Cortex-A9 MPCore", WHITE, "CPU0 666.67 MHz (MicroPython)\nCPU1 parked in BootROM", fs=9.5, sfs=7.6)
    s.box(172, 122, 80, 40, "L2 cache", MEM, "512 KB PL310", fs=9, sfs=7.4)
    s.box(258, 122, 80, 40, "OCM", MEM, "256 KB", fs=9, sfs=7.4)
    s.box(172, 168, 166, 30, "Central interconnect", WHITE, fs=9)
    s.box(172, 204, 166, 36, "DDR controller", WHITE, "DDR3-1066, 16-bit", fs=9, sfs=7.4)
    s.box(172, 246, 80, 40, "UART1", WHITE, "MIO48 / 49", fs=9, sfs=7.4)
    s.box(258, 246, 80, 40, "GPIO", WHITE, "MIO9", fs=9, sfs=7.4)
    s.box(172, 292, 166, 34, "SLCR, PLLs, clocks", WHITE, "ARM / DDR / IO PLL", fs=9, sfs=7.4)
    s.box(172, 332, 166, 66, "PS-PL interfaces", WHITE, "M_AXI_GP0  32-bit master\nS_AXI_HP0  64-bit slave\nFCLK_CLK0 100 MHz, FCLK_RESET0_N", fs=9, sfs=7.4)
    # PL
    s.rect(362, 40, 178, 368, PL, "#4a7a35", 1.1, 3)
    s.text(372, 52, "Programmable Logic (PL)", 9.5, "start", "700", "#2f5a1f")
    s.box(372, 66, 158, 40, "AXI interconnect", XIP, "GP0 → 5 slaves", fs=9, sfs=7.4)
    s.box(372, 116, 158, 40, "AXI GPIO", XIP, "LED1-4 out, KEY1 in", fs=9, sfs=7.4)
    s.box(372, 166, 76, 50, "FFT", RTL, "own radix-2", fs=9, sfs=7.4)
    s.box(454, 166, 76, 50, "FFT", XIP, "xfft v9.1 +\nfront end", fs=9, sfs=7.4)
    s.box(372, 226, 158, 120, "", PL, stroke="#4a7a35", dash=True)
    s.text(380, 236, "HDMI 720p60 pipeline", 8.8, "start", "700", "#2f5a1f")
    s.box(380, 244, 70, 30, "AXI VDMA", XIP, fs=8.4)
    s.box(454, 244, 70, 30, "565 → 888", XIP, fs=8.4)
    s.box(380, 280, 70, 30, "Vid out + VTC", XIP, fs=8.0)
    s.box(454, 280, 70, 30, "hdmi_tx", RTL, fs=8.4)
    s.box(380, 316, 144, 24, "clk_wiz: 74.25 / 371.25 MHz", XIP, fs=7.8, bold=False)
    s.box(372, 356, 158, 42, "Video status GPIO", XIP, "locked / underflow", fs=9, sfs=7.4)
    # PS <-> PL buses
    s.bus([(338, 352), (356, 352), (356, 86), (372, 86)], "GP0", (348, 344), color="#5a5a5a", lw=3.5)
    s.bus([(380, 259), (366, 259), (366, 380), (338, 380)], "HP0", (352, 392), color=ACCENT, lw=3.5)
    # Off-chip, right
    right = [("LED1-LED4", "W13 V12 U12 T12", 110, 40), ("KEY1", "Y16, pull-up", 160, 34),
             ("HDMI J1", "TMDS_33, bank 35\nDVI signalling", 262, 50)]
    for name, sub, y, h in right:
        s.box(572, y, 118, h, name, EXT, sub, fs=9.5, sfs=7.8)
    for y, lab in ((130, "bank 34"), (177, "bank 34"), (287, "bank 35")):
        s.line([(540, y), (572, y)], arrow="end" if y != 177 else "start")
        s.text(556, y - 6, lab, 7.0)
    # Off-chip connections, left: to the PS edge, labelled with the pins
    for y, lab, ar in ((61, "DDR", "both"), (136, "MIO48/49", "both"), (202, "JTAG", "end"),
                       (261, "MIO9", "start"), (316, "PS_CLK", "end"), (376, "POR_B", "end")):
        s.line([(112, y), (162, y)], arrow=ar)
        s.text(132, y - 6, lab, 6.8)
    legend_hw(s, 10, 426 - 4)
    return s.render()


def fig_ps():
    s = Svg(700, 400, "ps")
    s.rect(10, 10, 680, 330, PS, "#2f5f8a", 1.2, 4)
    s.text(20, 24, "Zynq-7010 Processing System, as configured by hw/scripts/ps7_config.tcl", 9.5, "start", "700", "#1f4466")
    # APU
    s.rect(20, 34, 330, 190, "#eef5fc", "#2f5f8a", 1, 3)
    s.text(30, 46, "Application Processor Unit (APU)", 9, "start", "700", "#1f4466")
    s.box(30, 56, 150, 80, "CPU0  Cortex-A9", WHITE, "ARMv7-A, NEON + VFPv3-D32\nL1 I-cache 32 KB, 4-way\nL1 D-cache 32 KB, 4-way\nruns MicroPython", fs=9.5, sfs=7.4)
    s.box(190, 56, 150, 80, "CPU1  Cortex-A9", WHITE, "held in the BootROM\n(wfe loop)", fs=9.5, sfs=7.4, dash=True, color=GREY)
    s.box(30, 144, 310, 26, "Snoop Control Unit, global timer (333.33 MHz), private timers, GIC", WHITE, fs=8.4, bold=False)
    s.box(30, 178, 150, 38, "L2 cache PL310", MEM, "512 KB, 8-way, enabled", fs=9, sfs=7.4)
    s.box(190, 178, 150, 38, "On-chip memory", MEM, "256 KB OCM", fs=9, sfs=7.4)
    # Interconnect + DDR
    s.box(370, 34, 150, 36, "Central interconnect", WHITE, fs=9)
    s.box(370, 82, 150, 46, "Memory interconnect", WHITE, "HP ports → DDR", fs=9, sfs=7.4)
    s.box(540, 34, 140, 94, "DDR controller", WHITE, "DDR3, 16-bit\n533.33 MHz clock\n1066 MT/s", fs=9.5, sfs=7.6)
    # IOP
    s.rect(370, 140, 310, 84, "#eef5fc", "#2f5f8a", 1, 3)
    s.text(380, 152, "I/O peripherals (IOP) and MIO", 9, "start", "700", "#1f4466")
    s.box(380, 162, 90, 52, "UART1", WHITE, "Cadence UART\nMIO48 TX\nMIO49 RX", fs=9, sfs=7.2)
    s.box(478, 162, 90, 52, "GPIO", WHITE, "bank 0\nMIO9 = LED0", fs=9, sfs=7.2)
    s.box(576, 162, 96, 52, "disabled", WHITE, "QSPI, SD0/1, UART0\nENET0/1, USB0/1\nI2C0/1", fs=8.6, sfs=7.0, dash=True, color=GREY)
    # SLCR / PS-PL
    s.box(20, 234, 330, 96, "", WHITE)
    s.text(30, 246, "System level control (SLCR, 0xF800_0000)", 9, "start", "700")
    s.text(30, 262, "ARM PLL 1333.3 MHz → CPU 6x4x 666.67 MHz", 8, "start")
    s.text(30, 276, "DDR PLL 1066.7 MHz → DDR 3x 533.33 MHz", 8, "start")
    s.text(30, 290, "IO PLL 1000 MHz → UART ref 100 MHz, FCLK_CLK0 100 MHz", 8, "start")
    s.text(30, 304, "MIO pin mux, MIO bank voltages (500: 3.3 V, 501: 1.8 V)", 8, "start")
    s.text(30, 318, "PS-PL level shifters (enabled by ps7_post_config)", 8, "start")
    s.box(370, 234, 310, 96, "", WHITE)
    s.text(380, 246, "PS-PL interfaces in use", 9, "start", "700")
    s.text(380, 264, "M_AXI_GP0   32-bit AXI3 master, 0x4000_0000-0x7FFF_FFFF", 8, "start", mono=False)
    s.text(380, 280, "S_AXI_HP0   64-bit AXI3 slave → memory interconnect", 8, "start")
    s.text(380, 296, "FCLK_CLK0   100 MHz,  FCLK_RESET0_N", 8, "start")
    s.text(380, 312, "unused: GP1, ACP, HP1-3, S_AXI_GP0/1, interrupts", 8, "start", fill=GREY)
    # Links
    s.line([(350, 52), (370, 52)], arrow="both")
    s.line([(520, 52), (540, 52)], arrow="both")
    s.line([(520, 105), (540, 105)], arrow="end")
    s.line([(445, 70), (445, 82)], arrow=None)
    s.line([(445, 70), (445, 140)], arrow="end")
    # off chip
    s.box(540, 352, 140, 40, "DDR3 512 MB", EXT, "MT41J256M16", fs=9, sfs=7.4)
    s.line([(610, 128), (610, 352)], arrow="both", lw=1.6)
    s.box(10, 352, 200, 40, "PL (see Chapter 3)", PL, "GP0 slaves, HP0 master (VDMA)", fs=9, sfs=7.4)
    s.bus([(380, 330), (380, 372), (210, 372)], "GP0", (300, 366), lw=3)
    s.bus([(210, 386), (460, 386), (460, 128)], "HP0 (not cache coherent)", (330, 398), color=ACCENT, lw=3)
    s.box(240, 352, 110, 26, "CH340 / LED0", EXT, fs=8.4)
    return s.render()


def fig_clocks():
    s = Svg(700, 330, "clk")
    s.box(10, 140, 86, 46, "PS_CLK", EXT, "33.333 MHz\nX2", fs=9.5, sfs=7.6)
    s.rect(110, 14, 300, 300, PS, "#2f5f8a", 1, 3)
    s.text(120, 26, "PS clock generator (ps7_init)", 9, "start", "700", "#1f4466")
    plls = [("ARM PLL", "1333.33 MHz", 40), ("DDR PLL", "1066.67 MHz", 140), ("IO PLL", "1000 MHz", 220)]
    for n, f, y in plls:
        s.box(130, y, 86, 44, n, WHITE, f, fs=9, sfs=7.6)
        s.line([(96, 163), (112, 163), (112, y + 22), (130, y + 22)])
    outs = [(40, "CPU_6x4x  666.67 MHz", "Cortex-A9 cores"), (62, "CPU_3x2x  333.33 MHz", "global timer, SCU"),
            (140, "DDR_3x  533.33 MHz", "DDR3 controller, 1066 MT/s"),
            (220, "UART_REF  100 MHz", "UART1 (CD 124, BDIV 6)"), (242, "FCLK_CLK0  100 MHz", "to the PL")]
    for y, name, use in outs:
        s.line([(216, y + 11), (246, y + 11)])
        s.text(250, y + 11, name, 8.2, "start", "600")
        s.text(250, y + 22, use, 7.4, "start", "normal", "#555")
    # PL side
    s.rect(430, 14, 260, 300, PL, "#4a7a35", 1, 3)
    s.text(440, 26, "PL clock domains", 9, "start", "700", "#2f5a1f")
    s.box(442, 40, 236, 64, "clk_fpga_0  100 MHz", WHITE, "AXI interconnects, AXI GPIOs, FFT engines,\nVDMA, 565→888 converter, video out (aclk)", fs=9, sfs=7.4)
    s.box(442, 132, 236, 50, "clk_wiz_hdmi (MMCM)", XIP, "100 / 5 × 37.125 = VCO 742.5 MHz\nCLKOUT0 ÷10, CLKOUT1 ÷2", fs=9, sfs=7.4)
    s.box(442, 202, 112, 62, "74.25 MHz", WHITE, "pixel clock\nVTC, video out,\nTMDS encoders", fs=9, sfs=7.2)
    s.box(566, 202, 112, 62, "371.25 MHz", WHITE, "serial clock\nOSERDESE2 DDR\n742.5 Mb/s / lane", fs=9, sfs=7.2)
    s.line([(340, 253), (420, 253), (420, 72), (442, 72)], lw=1.4)
    s.line([(560, 104), (560, 132)])
    s.line([(498, 182), (498, 202)])
    s.line([(622, 182), (622, 202)])
    s.text(560, 286, "clk_fpga_0 and the two HDMI clocks are declared", 7.6, "middle", fill="#444")
    s.text(560, 298, "asynchronous (zynq_zero_timing.xdc)", 7.6, "middle", fill="#444")
    return s.render()


def fig_addrmap():
    s = Svg(700, 490, "amap")
    regions = [
        ("0x0000_0000", "DDR3, 512 MB", "firmware, heap, LVGL pool, framebuffers", MEM, 100,
         "Normal, WB-WA (L1+L2)"),
        ("0x2000_0000", "unmapped DDR window", "512 MB not fitted", WHITE, 36, "Normal (unused)"),
        ("0x4000_0000", "M_AXI_GP0 → PL", "5 slaves, 64 KB each", PL, 100, "Strongly-ordered, XN"),
        ("0x8000_0000", "M_AXI_GP1", "not enabled", WHITE, 36, "Strongly-ordered, XN"),
        ("0xC000_0000", "SMC, quad-SPI linear (unused)", "", WHITE, 30, "Device, XN"),
        ("0xE000_0000", "I/O peripherals", "UART1 0xE000_1000, GPIO 0xE000_A000", PS, 34, "Device, XN"),
        ("0xF800_0000", "SLCR, PS system registers", "", PS, 30, "Device, XN"),
        ("0xF8F0_0000", "MPCore private + L2C", "global timer 0xF8F0_0200, PL310 0xF8F0_2000", PS, 34, "Device, XN"),
        ("0xFFF0_0000", "high OCM", "BootROM-parked CPU1", MEM, 28, "Normal, WB-WA"),
    ]
    y = 10
    gp_top = gp_bot = 0
    for addr, name, sub, fill, h, attr in regions:
        s.text(118, y + 6, addr, 8.4, "end", mono=True)
        s.box(126, y, 250, h, name, fill, sub or None, fs=9.2, sfs=7.4)
        s.text(386, y + h / 2, attr, 8, "start", fill="#444")
        if name.startswith("M_AXI_GP0"):
            gp_top, gp_bot = y, y + h
        y += h + 4
    s.text(118, y + 2, "0xFFFF_FFFF", 8.4, "end", mono=True)
    # GP0 zoom
    zx = 540
    gp = [("0x4120_0000", "axi_gpio_0", "LED1-4, KEY1"), ("0x4121_0000", "axi_gpio_video", "video status"),
          ("0x4300_0000", "axi_vdma_0", "S_AXI_LITE"), ("0x43C0_0000", "myfft_0", "own FFT"),
          ("0x43C1_0000", "xfft_ctrl_0", "Xilinx FFT")]
    gy = 166
    s.text(zx + 75, gy - 12, "GP0 slaves (64 KB each)", 8.6, "middle", "700")
    for i, (a, n, sub) in enumerate(gp):
        yy = gy + i * 33
        s.box(zx, yy, 150, 29, n, RTL if "fft" in n else XIP, sub, fs=8.6, sfs=7.0)
        s.text(zx - 6, yy + 15, a, 7.6, "end", mono=True)
    s.line([(376, gp_top), (470, gy - 2)], arrow=None, dash=True, color=GREY)
    s.line([(376, gp_bot), (470, gy + 5 * 33)], arrow=None, dash=True, color=GREY)
    s.text(350, 484, "Not to scale. MMU attributes from ports/zynq/mmu.c", 7.6, "middle", fill="#555")
    return s.render()


def fig_ddrmap():
    """Firmware layout in DDR (from the linked ELF)."""
    s = Svg(700, 445, "ddr")
    rows = [
        ("0x0000_0000", "reserved 1 MB", "low OCM shadows 0x0-0x2FFFF", WHITE, 24),
        ("0x0010_0000", ".text + .rodata  1.32 MB", "vectors, MicroPython, LVGL, binding, frozen .mpy", "#f0e6c8", 40),
        ("0x0025_2628", ".ARM.exidx, .data  1.2 KB", "", "#f0e6c8", 18),
        ("0x0025_2B10", ".lvgl_pool  8 MB", "LVGL TLSF heap (NOLOAD, scanned by the GC)", "#f7d6e0", 52),
        ("0x00A5_4000", ".bss  545 KB", "incl. FFT twiddle table 512 KB, UART ring", "#e9e9e9", 26),
        ("0x00AD_C240", ".stack  264 KB", "SVC 256 KB + ABT 4 KB + UND 4 KB", "#e9e9e9", 22),
        ("0x00B1_E240", ".heap  16 MB", "MicroPython GC heap (gc_init)", "#d7e7f6", 62),
        ("0x01B1_E240", "free", "", WHITE, 18),
        ("0x01C0_0000", ".framebuffer 0  1.76 MB", "1280 × 720 RGB565, 1 MB aligned, L1-only", "#e3f1da", 34),
        ("0x01E1_C000", ".framebuffer 1  1.76 MB", "VDMA frame store 1", "#e3f1da", 34),
        ("0x01F8_4000", "free to 0x1FFF_FFFF", "QEMU builds: LED scratch at 0x1FF0_0000", WHITE, 24),
    ]
    y = 12
    for addr, name, sub, fill, h in rows:
        s.text(118, y + 6, addr, 8.2, "end", mono=True)
        s.box(126, y, 300, h, name, fill, sub or None, fs=8.8, sfs=7.2)
        y += h + 3
    s.text(118, y + 2, "0x2000_0000", 8.2, "end", mono=True)
    # side notes
    s.box(452, 60, 238, 64, "Loaded by xsdb (dow)", WHITE, "Only .text, .exidx and .data have\nfile contents. NOLOAD sections are\nzeroed (.bss) or left as is.", fs=8.8, sfs=7.4)
    s.box(452, 140, 238, 52, "LVGL ↔ GC", WHITE, "gc_collect() scans .lvgl_pool for\npointers to Python objects", fs=8.8, sfs=7.4)
    s.box(452, 210, 238, 52, "Heap size", WHITE, "HEAP_SIZE / STACK_SIZE are Make\nvariables (--defsym to zynq.ld)", fs=8.8, sfs=7.4)
    s.box(452, 288, 238, 56, "VDMA", WHITE, "MM2S_START_ADDRESS 0/1 point at\nthe two framebuffers; read over HP0", fs=8.8, sfs=7.4)
    s.line([(452, 166), (426, 120)], dash=True, color=GREY)
    s.line([(452, 316), (426, 316)], dash=True, color=GREY)
    s.text(276, 436, "Sizes from prebuilt/firmware.elf (LVGL build). Not to scale.", 7.6, "middle", fill="#555")
    return s.render()
