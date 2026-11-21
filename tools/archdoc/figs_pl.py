"""PL diagrams: block design, FFT engines, HDMI pipeline, colour remap, hdmi_tx."""
from svglib import Svg, PS, PL, XIP, RTL, MEM, EXT, WHITE, INK, ACCENT, GREY


def fig_bd():
    s = Svg(700, 470, "bd")
    s.rect(4, 4, 692, 440, "#fafcf8", "#4a7a35", 1, 3)
    s.text(14, 16, "Block design \u201csystem\u201d (hw/scripts/build.tcl)", 9, "start", "700", "#2f5a1f")
    # PS7
    s.box(14, 34, 92, 300, "ps7", PS, "processing_\nsystem7", fs=11, sfs=7.6)
    s.text(60, 112, "M_AXI_GP0", 7.4, "middle", "600")
    s.text(60, 262, "S_AXI_HP0", 7.4, "middle", "600")
    s.text(60, 306, "FCLK_CLK0\nFCLK_RESET0_N", 7.0, "middle")
    # GP0 interconnect (vertical, rotated label)
    s.rect(130, 34, 44, 200, XIP, INK, 1, 2)
    s.raw('<text x="155" y="134" font-family="Inter" font-size="8.4" font-weight="600" text-anchor="middle" '
          'transform="rotate(-90 155 134)" fill="#2b2b2b">ps7_0_axi_periph  (1 \u2192 5)</text>')
    s.bus([(106, 120), (130, 120)], lw=3)
    slaves = [("axi_gpio_0", "0x4120_0000", XIP, 42), ("axi_gpio_video", "0x4121_0000", XIP, 82),
              ("myfft_0", "0x43C0_0000", RTL, 122), ("xfft_ctrl_0", "0x43C1_0000", RTL, 162),
              ("axi_vdma_0", "0x4300_0000  S_AXI_LITE", XIP, 202)]
    for name, addr, fill, y in slaves:
        s.box(200, y, 128, 32, name, fill, addr, fs=9, sfs=7.0, mono_sub=True)
        s.bus([(174, y + 16), (200, y + 16)], lw=2.2)
    # GPIO ports
    s.box(560, 34, 128, 34, "leds_tri_o[3:0]", WHITE, "LED1-4", fs=8.2, sfs=7.0)
    s.box(560, 74, 128, 22, "keys_tri_i[0]  KEY1", WHITE, fs=8.2, bold=False)
    s.line([(328, 51), (560, 51)])
    s.line([(560, 85), (346, 85), (346, 60), (328, 60)])
    # Video status: concat -> axi_gpio_video
    s.box(480, 112, 84, 28, "video_status", XIP, "xlconcat 3", fs=8.4, sfs=6.8)
    s.line([(480, 126), (404, 126), (404, 98), (328, 98)])
    # Xilinx FFT next to its front end
    s.box(380, 158, 84, 44, "xfft_0", XIP, "FFT v9.1\n1024, burst", fs=9, sfs=6.8)
    s.line([(328, 170), (380, 170)], label="config, data", lfs=6.6, lpos=(354, 165))
    s.line([(380, 188), (328, 188)], label="M_AXIS_DATA", lfs=6.6, lpos=(354, 199))
    # VDMA memory port -> HP0 interconnect
    s.rect(130, 248, 44, 70, XIP, INK, 1, 2)
    s.raw('<text x="155" y="283" font-family="Inter" font-size="7.8" font-weight="600" text-anchor="middle" '
          'transform="rotate(-90 155 283)" fill="#2b2b2b">AXI interconnect</text>')
    s.bus([(244, 234), (244, 270), (174, 270)], "M_AXI_MM2S", (210, 262), color=ACCENT, lw=2.6)
    s.bus([(130, 270), (106, 270)], color=ACCENT, lw=3)
    # Video chain (bottom row)
    y = 352
    chain = [("rgb565_to_888", "axis_subset_\nconverter", XIP, 196), ("v_axi4s_vid_out_0", "async FIFO", XIP, 312),
             ("hdmi_tx_0", "TMDS + OSERDESE2", RTL, 444)]
    for name, sub, fill, x in chain:
        s.box(x, y, 104, 40, name, fill, sub, fs=8.6, sfs=6.8)
    s.bus([(296, 234), (296, 300), (248, 300), (248, y)], "M_AXIS_MM2S 16 b", (200, 328), lw=2.2)
    s.bus([(300, y + 20), (312, y + 20)], lw=2.2)
    s.bus([(416, y + 26), (444, y + 26)], lw=2.2)
    s.text(430, y + 36, "vid_io", 6.6)
    s.box(312, 300, 104, 30, "v_tc_0", XIP, "720p generator", fs=8.6, sfs=6.8)
    s.line([(364, 330), (364, y)], label="vtiming", lpos=(386, 341), lfs=6.8)
    s.box(560, y, 128, 40, "HDMI J1", WHITE, "hdmi_clk_p/n, hdmi_d_p/n[2:0]", fs=8.6, sfs=6.6)
    s.bus([(548, y + 20), (560, y + 20)], lw=2.2)
    # Clocking and status wires
    s.box(480, 270, 110, 34, "clk_wiz_hdmi", XIP, "74.25 / 371.25 MHz", fs=8.6, sfs=6.8)
    s.box(600, 270, 88, 34, "rst_pixel", XIP, "proc_sys_reset", fs=8.6, sfs=6.8)
    s.line([(500, 304), (500, y)], color=GREY, label="pix, ser", lpos=(518, 328), lfs=6.6)
    s.line([(590, 287), (600, 287)], color=GREY)
    s.line([(106, 320), (118, 320), (118, 430), (560, 430), (560, 304)], color=GREY, label="FCLK_CLK0",
           lpos=(330, 424), lfs=6.8)
    s.line([(520, 270), (520, 140)], color=GREY, label="locked", lpos=(536, 210), lfs=6.6)
    s.line([(416, 362), (428, 362), (428, 250), (544, 250), (544, 140)], color=GREY)
    s.text(470, 244, "locked, underflow", 6.6, "middle", fill="#555")
    s.legend(14, 458, [(PS, "PS"), (XIP, "Xilinx IP"), (RTL, "own Verilog (module reference)"), (WHITE, "ports")])
    return s.render()


def fig_myfft():
    s = Svg(700, 330, "mf")
    s.rect(4, 4, 692, 298, "#fdf6f8", "#8a2251", 1, 3)
    s.text(14, 16, "myfft_axil (hw/rtl/myfft_axil.v)", 9, "start", "700", "#8a2251")
    s.box(14, 34, 96, 56, "axil_slave", RTL, "AXI4-Lite →\nreg bus, 1-cycle\nread latency", fs=9, sfs=7)
    s.bus([(-2, 62), (14, 62)], lw=2.2)
    s.box(14, 104, 96, 82, "Registers", WHITE, "ID, CTRL, STATUS\nLOG2N, INVERSE\nCYCLES, LOG2N_MAX\nFORMAT", fs=9, sfs=7)
    s.box(14, 200, 96, 86, "Sequencer", WHITE, "stage s = 0..log2N-1\nbutterfly j\ni0, i1, twiddle k\nbusy / done", fs=9, sfs=7)
    s.line([(62, 90), (62, 104)])
    s.line([(62, 186), (62, 200)])
    s.box(134, 34, 104, 40, "bit reversal", WHITE, "input index", fs=8.8, sfs=7)
    s.line([(110, 54), (134, 54)], label="IN", lpos=(122, 47), lfs=6.4)
    # RAMs
    s.box(268, 34, 96, 74, "RAM 0", MEM, "tdp_ram\n1024 × 32\nQ1.15 {im, re}", fs=9.5, sfs=7.2)
    s.box(268, 128, 96, 74, "RAM 1", MEM, "tdp_ram\n1024 × 32\nQ1.15 {im, re}", fs=9.5, sfs=7.2)
    s.line([(238, 54), (268, 54)])
    s.text(244, 214, "ping-pong: stage s reads one\nRAM and writes the other", 7.2, "end", fill="#555")
    # Pipeline
    px = 400
    stages = [("p1", "RAM / ROM\nread"), ("p2", "operands\nx0, x1, W"), ("p3", "4 products\n(DSP48)"),
              ("p4", "W·x1 →\nQ1.15"), ("p5", "x0 ± W·x1\n½, round, sat")]
    for i, (n, d) in enumerate(stages):
        x = px + i * 56
        s.box(x, 54, 50, 76, n, RTL, d, fs=9.5, sfs=6.6)
        if i:
            s.line([(x - 6, 92), (x, 92)])
    s.text(px + 138, 44, "butterfly pipeline, one radix-2 butterfly per clock", 7.6, "middle", "600")
    s.line([(364, 70), (400, 70)], label="x0, x1", lpos=(382, 64), lfs=6.6)
    s.line([(364, 150), (380, 150), (380, 110), (400, 110)])
    s.box(400, 170, 106, 46, "twiddle_rom", RTL, "512 × 36\n{cos, sin} 18-bit", fs=8.8, sfs=7)
    s.line([(453, 170), (453, 130)])
    s.line([(680, 92), (690, 92), (690, 246), (380, 246), (380, 190), (364, 190)], label="y0, y1 → other RAM",
           lpos=(560, 240), lfs=7)
    s.line([(110, 243), (330, 243), (330, 202)], color=GREY, label="addresses / enables", lpos=(200, 237), lfs=6.8)
    s.line([(330, 202), (330, 202)], arrow=None)
    s.line([(268, 90), (250, 90), (250, 270), (110, 270)], color=GREY, label="0x2000+4i (natural order)",
           lpos=(180, 280), lfs=6.8)
    s.text(350, 318, "Cycles per transform: log2(N) × (N/2 + 6)  →  1024 points: 5 180 cycles = 51.8 µs at 100 MHz",
           8, "middle", "600")
    return s.render()


def fig_xfft():
    s = Svg(700, 210, "xf")
    s.rect(4, 4, 470, 200, "#fdf6f8", "#8a2251", 1, 3)
    s.text(14, 14, "xfft_ctrl", 8.6, "start", "700", "#8a2251")
    s.box(14, 34, 92, 50, "axil_slave", RTL, "AXI4-Lite", fs=9, sfs=7)
    s.box(14, 100, 92, 86, "Registers", WHITE, "same map as\nmyfft_axil\nID “XFFT”\nFORMAT 1", fs=9, sfs=7)
    s.box(130, 34, 92, 50, "in_ram", MEM, "1024 × 32", fs=9, sfs=7)
    s.box(130, 110, 120, 76, "Stream FSM", WHITE, "IDLE → CFG → RUN\nconfig word, then\nN samples (TLAST)\nthen collect N", fs=9, sfs=7)
    s.box(330, 34, 120, 50, "out_re / out_im", MEM, "1024 × 32 each\nsign-extended", fs=9, sfs=7)
    s.line([(106, 59), (130, 59)], label="IN", lpos=(118, 52), lfs=6.4)
    s.line([(176, 84), (176, 110)])
    s.box(530, 60, 160, 110, "xfft_0", XIP, "Fast Fourier Transform v9.1\nradix-2 burst I/O\nN = 8..1024 at run time\n16-bit in, 16-bit phase\nunscaled, 27-bit out\nnatural order", fs=10, sfs=7.4)
    s.bus([(250, 128), (530, 128)], "S_AXIS_CONFIG (16 b)  +  S_AXIS_DATA (32 b)", (390, 120), lw=2.2, lfs=7.4)
    s.bus([(530, 156), (470, 156), (470, 70), (450, 70)], "M_AXIS_DATA (64 b)", (500, 196), lw=2.2, lfs=7.4)
    s.line([(390, 34), (390, 27), (60, 27), (60, 34)], color=GREY, label="OUT_RE / OUT_IM (0x2000 / 0x3000)", lpos=(250, 22), lfs=6.6)
    return s.render()


def fig_hdmi():
    s = Svg(700, 330, "hd")
    # clock domain bands
    s.rect(4, 4, 404, 250, "#f4f9f0", "#4a7a35", 0.8, 3, dash=True)
    s.text(12, 16, "clk_fpga_0  100 MHz", 8, "start", "600", "#2f5a1f")
    s.rect(414, 4, 282, 250, "#fff7ef", "#c07a2a", 0.8, 3, dash=True)
    s.text(422, 16, "pixel 74.25 MHz  /  serial 371.25 MHz", 8, "start", "600", "#8a5a1f")
    s.box(14, 30, 108, 70, "DDR3", MEM, "framebuffer 0 / 1\n1280 × 720 RGB565\n2560 B per line", fs=9.5, sfs=7.2)
    s.box(150, 30, 112, 70, "axi_vdma_0", XIP, "MM2S only, park mode\n2 frame stores\nline buffer 2048\nburst 32", fs=9.5, sfs=7.0)
    s.bus([(122, 65), (150, 65)], "HP0\n64 b", (136, 84), color=ACCENT, lw=3, arrow="start", lfs=7)
    s.box(290, 30, 106, 70, "rgb565_to_888", XIP, "axis_subset_\nconverter\n16 b → 24 b\n{R, B, G}", fs=8.8, sfs=7.0)
    s.bus([(262, 65), (290, 65)], "16 b", (276, 56), lw=2.4)
    s.box(290, 150, 106, 74, "v_axi4s_vid_out_0", XIP, "AXI4-Stream →\nparallel video\nasync FIFO\nVTG slave", fs=8.4, sfs=7.0)
    s.bus([(343, 100), (343, 150)], "24 b", (360, 126), lw=2.4)
    s.box(430, 30, 112, 70, "v_tc_0", XIP, "video timing\ncontroller\n720p, static\nno AXI-Lite", fs=9.5, sfs=7.0)
    s.line([(486, 100), (486, 168), (396, 168)], label="vtiming", lpos=(450, 162), lfs=7)
    s.line([(396, 190), (470, 190), (470, 100)], label="vtg_ce → gen_clken", lpos=(430, 204), lfs=6.8)
    s.box(560, 130, 124, 94, "hdmi_tx_0", RTL, "3 × TMDS 8b/10b\n4 × OSERDESE2 pair\n10:1 DDR\nOBUFDS, TMDS_33", fs=10, sfs=7.4)
    s.bus([(396, 214), (560, 214)], "vid_io: data 24 b, DE, HSYNC, VSYNC", (478, 230), lw=2.4, lfs=7)
    s.box(560, 30, 124, 46, "clk_wiz_hdmi", XIP, "MMCM", fs=9.5, sfs=7.0)
    s.line([(622, 76), (622, 130)], label="pix, ser", lpos=(642, 104), lfs=7)
    s.box(560, 270, 124, 50, "HDMI J1", EXT, "clock + 3 data lanes\n742.5 Mb/s each", fs=9.5, sfs=7.2)
    s.bus([(622, 224), (622, 270)], lw=2.6)
    s.box(150, 270, 246, 50, "axi_gpio_video  (0x4121_0000)", XIP, "bit 0 MMCM locked, bit 1 vid_out locked,\nbit 2 underflow", fs=8.8, sfs=7.2)
    s.line([(343, 224), (343, 270)], color=GREY)
    s.line([(560, 53), (420, 53), (420, 262), (396, 262), (396, 270)], color=GREY)
    s.box(14, 150, 108, 74, "CPU", PS, "_hdmi / _lvhdmi:\nset addresses,\nPARK_PTR,\npoll status", fs=9.5, sfs=7.0)
    s.line([(122, 170), (180, 170), (180, 100)], label="GP0: S_AXI_LITE", lpos=(150, 164), lfs=6.8)
    s.line([(68, 150), (68, 100)], label="draws (cached)", lpos=(96, 125), lfs=6.8)
    return s.render()


def fig_rgb():
    s = Svg(700, 192, "rgb")
    cw = 16

    def bits(x, y, cells):
        for i, (lab, fill) in enumerate(cells):
            s.rect(x + i * cw, y, cw, 20, fill, INK, 0.7, 0)
            s.text(x + i * cw + cw / 2, y + 10, lab, 6.6, mono=True)
    R, G, B = "#f6c6c6", "#c9e8c2", "#c6d6f6"
    inp = [(f"R{i}", R) for i in range(4, -1, -1)] + [(f"G{i}", G) for i in range(5, -1, -1)] + \
          [(f"B{i}", B) for i in range(4, -1, -1)]
    x0 = 222
    s.text(x0 - 10, 34, "VDMA tdata[15:0]", 8, "end", "600")
    bits(x0, 24, inp)
    s.text(x0, 18, "15", 6.8, "start", mono=True)
    s.text(x0 + 16 * cw, 18, "0", 6.8, "end", mono=True)
    out = [(f"R{i}", R) for i in range(4, -1, -1)] + [("R4", R), ("R3", R), ("R2", R)] + \
          [(f"B{i}", B) for i in range(4, -1, -1)] + [("B4", B), ("B3", B), ("B2", B)] + \
          [(f"G{i}", G) for i in range(5, -1, -1)] + [("G5", G), ("G4", G)]
    xo = 158
    s.text(xo - 10, 124, "tdata[23:0]", 8, "end", "600")
    bits(xo, 114, out)
    s.text(xo, 108, "23", 6.8, "start", mono=True)
    s.text(xo + 24 * cw, 108, "0", 6.8, "end", mono=True)
    for lab, a, n in (("R (red)", 0, 8), ("B (blue)", 8, 8), ("G (green)", 16, 8)):
        s.line([(xo + a * cw + 2, 140), (xo + (a + n) * cw - 2, 140)], arrow=None, lw=0.8)
        s.text(xo + (a + n / 2) * cw, 149, lab, 7.6)
    # mapping lines (MSB of each colour)
    s.line([(x0 + 2.5 * cw, 44), (xo + 2.5 * cw, 114)], color=GREY, lw=0.8)
    s.line([(x0 + 13.5 * cw, 44), (xo + 10.5 * cw, 114)], color=GREY, lw=0.8)
    s.line([(x0 + 8 * cw, 44), (xo + 19 * cw, 114)], color=GREY, lw=0.8)
    s.text(350, 166, "high bits replicated into the low bits: 0x1F → 0xFF, full white and black stay exact",
           7.6, "middle", fill="#555")
    s.text(350, 182, "TDATA_REMAP {tdata[15:11], tdata[15:13], tdata[4:0], tdata[4:2], tdata[10:5], tdata[10:9]}",
           7.4, "middle", mono=True)

    return s.render()


def fig_hdmitx():
    s = Svg(700, 300, "tx")
    s.rect(4, 4, 692, 262, "#fdf6f8", "#8a2251", 1, 3)
    s.text(14, 16, "hdmi_tx (hw/rtl/hdmi_tx.v)", 9, "start", "700", "#8a2251")
    s.box(14, 40, 92, 196, "input\nregister", WHITE, "pix_clk\n\nvid_data\n{R, B, G}\nDE\nHSYNC\nVSYNC", fs=9, sfs=7.2)
    rows = [("B", "C = {VSYNC, HSYNC}", 40), ("G", "C = 00", 94), ("R", "C = 00", 148)]
    for i, (c, ctl, y) in enumerate(rows):
        s.box(140, y, 170, 46, f"tmds_encoder  ch{i} ({c})", RTL, "stage 1: XOR / XNOR chain\nstage 2: DC balance, " + ctl,
              fs=8.6, sfs=6.8)
        s.line([(106, y + 23), (140, y + 23)])
    s.box(140, 202, 170, 34, "clock lane: 10'b0000011111", WHITE, fs=8.2, bold=False)
    for i, y in enumerate((40, 94, 148, 202)):
        h = 46 if i < 3 else 34
        s.box(346, y, 90, h, "OSERDESE2", XIP, "master + slave\n10:1 DDR", fs=8.4, sfs=6.8)
        s.line([(310, y + h / 2), (346, y + h / 2)], label="10 b", lpos=(328, y + h / 2 - 6), lfs=6.4)
        s.poly([(462, y + h / 2 - 12), (462, y + h / 2 + 12), (484, y + h / 2)], WHITE)
        s.line([(436, y + h / 2), (462, y + h / 2)], arrow=None)
        s.text(473, y + h / 2 - 16, "OBUFDS", 6.4)
    pins = [("hdmi_d_p/n[0]", "D19 / D20"), ("hdmi_d_p/n[1]", "C20 / B20"), ("hdmi_d_p/n[2]", "B19 / A20"),
            ("hdmi_clk_p/n", "H16 / H17")]
    for (n, b), y in zip(pins, (63, 117, 171, 219)):
        s.line([(484, y), (540, y)])
        s.text(546, y - 4, n, 8, "start", "600")
        s.text(546, y + 8, b + "  TMDS_33", 7.2, "start", fill="#555")
    s.text(350, 252, "CLKDIV = pix_clk 74.25 MHz, CLK = ser_clk 371.25 MHz (same MMCM), LSB first",
           7.6, "middle", fill="#444")
    s.text(350, 284, "Serial rate 10 × 74.25 MHz = 742.5 Mb/s per lane. DVI signalling: no data islands, no audio.",
           8, "middle", "600")
    return s.render()
