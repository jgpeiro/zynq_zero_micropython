"""Chapter 3: programmable logic."""
import figs_pl as P


def reglist(d, caption, rows, label=None):
    d.table(caption, ["Offset", "Name", "Info"], rows, label=label, mono=(0,), widths=[13, 20, 67])


def regfields(d, title, offset, desc, rows):
    d.h4(title)
    d.hold(f"<p>Offset: <code>{offset}</code></p>")
    d.table(f"{title}.", ["Bits", "Name", "Description", "Type", "Reset"], rows,
            mono=(0, 4), widths=[10, 15, 53, 8, 14], small=True)


def build(d):
    d.chapter("Programmable Logic")
    d.p("The PL design is a Vivado block design built entirely by `hw/scripts/build.tcl`. It mixes Xilinx "
        "IP with seven Verilog modules of the project's own; the Verilog enters the block design as "
        "module references, with `X_INTERFACE_INFO` attributes so that Vivado recognises their AXI, "
        "AXI4-Stream, video, clock and reset interfaces and can run connection automation on them.")

    d.section("Block design", label="sec-bd")
    d.figure("The block design. Five AXI4-Lite slaves hang off M_AXI_GP0; the VDMA reads DDR through "
             "S_AXI_HP0 and feeds the video chain along the bottom.", P.fig_bd(), label="fig-bd")
    d.p("{ref:fig-bd} has three parts. The control plane is the AXI interconnect that Vivado's "
        "connection automation inserts behind M_AXI_GP0 (one master, five slaves, plus the "
        "`rst_ps7_0_100M` reset block). The FFT plane is the two engines; the Xilinx core talks "
        "AXI4-Stream to its front end `xfft_ctrl_0`. The video plane starts at the VDMA's memory-mapped "
        "read port on S_AXI_HP0 and ends at the HDMI connector.")

    d.section("AXI address map", label="sec-gp0")
    d.p("`build.tcl` assigns fixed addresses, each with a 64 KB range, because the firmware hard-codes "
        "them (`zynq_regs.h`, `fft.py`, `modhdmi.c`).")
    reglist(d, "PL slaves on M_AXI_GP0.", [
        ["0x4120_0000", "axi_gpio_0", "AXI GPIO, dual channel: LED1-LED4 (out), KEY1 (in)"],
        ["0x4121_0000", "axi_gpio_video", "AXI GPIO, 3 inputs: MMCM locked, video locked, underflow"],
        ["0x4300_0000", "axi_vdma_0", "AXI VDMA register space (S_AXI_LITE)"],
        ["0x43C0_0000", "myfft_0", "own FFT engine: registers + sample buffers"],
        ["0x43C1_0000", "xfft_ctrl_0", "front end for the Xilinx FFT: registers + sample buffers"],
    ], label="tab-gp0")
    d.p("All five run on clk_fpga_0 (100 MHz) and are 32-bit AXI4-Lite. Because the MMU maps the GP0 "
        "window strongly-ordered, every register access completes in program order, and a read that "
        "follows a write to the same peripheral always sees its effect.")

    d.section("Clocks and resets")
    d.table("PL clock domains and resets.", ["Domain", "Clock", "Reset", "Blocks"], [
        ["control / stream", "clk_fpga_0, 100 MHz", "`rst_ps7_0_100M` (from FCLK_RESET0_N)",
         "interconnects, GPIOs, FFT engines, xfft, VDMA, subset converter, video out (aclk)"],
        ["pixel", "clk_wiz_hdmi CLKOUT0, 74.25 MHz", "`rst_pixel`, released when the MMCM locks",
         "VTC, video out (vid_io_out_clk), hdmi_tx encoders, OSERDESE2 CLKDIV"],
        ["serial", "clk_wiz_hdmi CLKOUT1, 371.25 MHz", "(hdmi_tx internal)", "OSERDESE2 CLK"],
    ], widths=[16, 22, 26, 36])
    d.p("The MMCM is fed from FCLK_CLK0, so Vivado would treat the HDMI clocks as related to clk_fpga_0 "
        "and time every crossing as synchronous. The only real crossings are the video-out IP's "
        "asynchronous FIFO (gray-coded pointers) and the status bits sampled by `axi_gpio_video`, so "
        "`zynq_zero_timing.xdc` declares the two groups asynchronous. The bitstream is only written if "
        "the worst negative slack is not negative.")

    d.section("GPIO")
    d.p("`axi_gpio_0` is a dual-channel Xilinx AXI GPIO: channel 1 is four outputs (`C_ALL_OUTPUTS`, "
        "default 0) wired to LED1-LED4; channel 2 is one input wired to KEY1.")
    reglist(d, "axi_gpio_0 registers used (PG144).", [
        ["0x0000", "GPIO_DATA", "channel 1 data: bits 3:0 = LED4..LED1, 1 = on"],
        ["0x0004", "GPIO_TRI", "channel 1 tri-state (outputs only in this build)"],
        ["0x0008", "GPIO2_DATA", "channel 2 data: bit 0 = KEY1, 0 = pressed"],
        ["0x000C", "GPIO2_TRI", "channel 2 tri-state (input)"],
    ])
    d.p("The firmware keeps a shadow copy of GPIO_DATA, so `Pin(\"LED2\").on()` is a single bus write "
        "rather than a read-modify-write.")

    d.section("FFT engines", label="sec-fft")
    d.p("Two PL engines compute complex FFTs of 8 to 1024 points. They share one register map and one "
        "driver (`_fft.hw` in `modfft.c`); the FORMAT register tells the driver how to read the result.")
    d.subsection("Register map")
    reglist(d, "FFT engine registers (both engines).", [
        ["0x0000", "ID", "0x4D46_4654 “MFFT” (own core) or 0x5846_4654 “XFFT” (Xilinx)"],
        ["0x0004", "CTRL", "write bit 0 = 1 to start"],
        ["0x0008", "STATUS", "busy, done, overflow"],
        ["0x000C", "LOG2N", "transform size, log2(N)"],
        ["0x0010", "INVERSE", "bit 0: 1 = inverse transform"],
        ["0x0014", "CYCLES", "clock cycles of the last transform, start to done"],
        ["0x0018", "LOG2N_MAX", "10 (1024 points)"],
        ["0x001C", "FORMAT", "0: packed Q1.15, scaled; 1: unscaled 32-bit re / im"],
        ["0x1000 + 4i", "IN[i]", "input sample i, natural order, {im[31:16], re[15:0]} Q1.15"],
        ["0x2000 + 4i", "OUT[i] / OUT_RE[i]", "FORMAT 0: {im, re} Q1.15. FORMAT 1: real part, sign-extended"],
        ["0x3000 + 4i", "OUT_IM[i]", "FORMAT 1 only: imaginary part, sign-extended"],
    ], label="tab-fftregs")
    regfields(d, "FFT: STATUS Register", "0x008", "", [
        ["31:3", "-", "Reserved", "-", "-"],
        ["2", "OVERFLOW", "A butterfly output saturated during the last transform (own core only; always 0 for XFFT)", "RO", "0x0"],
        ["1", "DONE", "The last transform finished; cleared by the next start", "RO", "0x0"],
        ["0", "BUSY", "A transform is running; LOG2N and INVERSE writes are ignored", "RO", "0x0"],
    ])
    regfields(d, "FFT: LOG2N Register", "0x00C", "", [
        ["31:4", "-", "Reserved", "-", "-"],
        ["3:0", "LOG2N", "Transform size log2(N). Values below 3 or above LOG2N_MAX are clamped", "RW", "0xA"],
    ])

    d.subsection("Own radix-2 engine (myfft_axil)", label="sec-myfft")
    d.figure("myfft_axil datapath: ping-pong block RAMs around a five-stage butterfly pipeline.",
             P.fig_myfft(), label="fig-myfft")
    d.p("The engine is an iterative decimation-in-time Cooley-Tukey FFT. Input samples are written "
        "through AXI in natural order and stored at their bit-reversed index, so the first stage can "
        "start straight away. Each stage reads all N points from one block RAM and writes the other; "
        "with both ports of both RAMs free, the pipeline issues one butterfly every clock and a "
        "transform takes log2(N) × (N/2 + 6) cycles, the 6 being the pipeline drain per stage.")
    d.p("Each butterfly computes y0 = (x0 + W·x1) / 2 and y1 = (x0 − W·x1) / 2 with rounding and "
        "saturation to 16 bits. Halving at every stage keeps the word length fixed: the result is "
        "FFT(x) / N forward, or IFFT(X) inverse, and cannot overflow as long as every input has "
        "|x| < 1, which the driver guarantees by scaling to 0.9 of full scale. The complex "
        "multiplication uses four 18 × 16 multipliers (DSP48E1). Twiddle factors come from a 512-entry "
        "ROM of 18-bit cosine and sine, generated by `gen_twiddle.py`; the index pos · 2^(9−s) is "
        "the same for every N.")
    d.table("Butterfly pipeline stages.", ["Stage", "Work"], [
        ["p1", "read x0 and x1 from the source RAM (both ports), twiddle from the ROM"],
        ["p2", "register operands; W = cos ∓ j sin (sign chosen by INVERSE)"],
        ["p3", "four products: Wr·x1r, Wi·x1i, Wr·x1i, Wi·x1r"],
        ["p4", "W·x1 = (rr − ii) + j(ri + ir), rounded back to Q1.15"],
        ["p5", "x0 ± W·x1, halved, rounded, saturated; both results written to the other RAM"],
    ], widths=[10, 90])

    d.subsection("Xilinx FFT engine (xfft_ctrl + xfft)")
    d.figure("xfft_ctrl: AXI4-Lite buffers and a small stream sequencer in front of the Xilinx FFT core.",
             P.fig_xfft(), label="fig-xfft")
    d.p("`xfft_ctrl.v` gives the Xilinx FFT LogiCORE the same register map as the own engine. On start it "
        "sends one configuration word ({FWD_INV, NFFT}) on S_AXIS_CONFIG, streams the N input samples "
        "with TLAST on the last, and stores the N results from M_AXIS_DATA in two output RAMs. "
        "`build.tcl` checks the stream widths the core actually generated (2-byte config, 8-byte "
        "output) and passes its output width to the front end as `OUT_W`.")
    d.table("xfft_0 configuration.", ["Parameter", "Value"], [
        ["Implementation", "radix-2 burst I/O"],
        ["Transform length", "1024, run-time configurable (8..1024)"],
        ["Input / phase factor width", "16 / 16 bits"],
        ["Scaling", "unscaled: full precision, 27-bit output at 1024 points, no overflow possible"],
        ["Output ordering", "natural order"],
        ["Throttle scheme", "non-real-time"],
        ["Target clock", "100 MHz"],
    ], widths=[34, 66])

    d.section("HDMI video pipeline", label="sec-hdmi")
    d.figure("Video path from DDR to the HDMI connector, with its two clock domains.",
             P.fig_hdmi(), label="fig-hdmi")
    d.p("Xilinx has no free HDMI transmitter for the 7 series, so the pipeline uses Xilinx IP up to "
        "parallel video and the project's own Verilog for TMDS. The output is DVI signalling: video "
        "only, no data islands, no audio. Every HDMI sink accepts it.")
    d.table("720p60 video timing (CEA-861 VIC 4), generated by v_tc_0.", ["", "Active", "Front porch", "Sync", "Back porch", "Total"], [
        ["Horizontal (pixels)", "1280", "110", "40", "220", "1650"],
        ["Vertical (lines)", "720", "5", "5", "20", "750"],
    ], widths=[24, 15, 16, 14, 16, 15])
    d.p("At 74.25 MHz that is 45 kHz line rate and exactly 60 frames per second. Scan-out reads "
        "1280 × 720 × 2 bytes × 60 = 110.6 MB/s from DDR over HP0.")

    d.subsection("AXI VDMA")
    d.p("`axi_vdma_0` has only its read channel (MM2S), a 16-bit stream, a 2048-pixel line buffer, "
        "bursts of 32 and two frame stores. The firmware runs it in park mode: it scans the frame "
        "store named in PARK_PTR, and a new value takes effect at the next frame boundary, which makes "
        "double buffering tear-free.")
    reglist(d, "VDMA registers used (PG020).", [
        ["0x00", "MM2S_VDMACR", "bit 0 RS (run), bit 1 circular (0 = park), bit 2 reset"],
        ["0x04", "MM2S_VDMASR", "bit 0 halted, bits 6:4 internal / slave / decode errors"],
        ["0x28", "PARK_PTR_REG", "bits 4:0 read frame to park on; bits 20:16 frame being read now"],
        ["0x2C", "VDMA_VERSION", "non-zero when the VDMA is present (bitstream check)"],
        ["0x50", "MM2S_VSIZE", "720 lines; writing it starts the channel"],
        ["0x54", "MM2S_HSIZE", "2560 bytes per line"],
        ["0x58", "MM2S_FRMDLY_STRIDE", "stride 2560 bytes"],
        ["0x5C, 0x60", "MM2S_START_ADDRESS1/2", "framebuffer 0 and 1 (0x01C0_0000, 0x01E1_C000)"],
    ])

    d.subsection("Colour conversion")
    d.figure("RGB565 to the 24-bit {R, B, G} order of Xilinx AXI4-Stream video, by bit remapping in "
             "an AXI4-Stream subset converter.", P.fig_rgb(), label="fig-rgb")
    d.p("The VDMA delivers 16-bit RGB565 pixels; the video IP expects 24 bits in Xilinx's RGB stream "
        "order, red in the top byte, then blue, then green. `rgb565_to_888` is an "
        "`axis_subset_converter` that only rewires bits: each channel's top bits are repeated into "
        "its low bits, so full intensity maps to 0xFF. Its TKEEP, TUSER (start of frame) and TLAST "
        "(end of line) remaps carry the stream framing through.")

    d.subsection("Stream to video and timing")
    d.p("`v_axi4s_vid_out_0` crosses from the 100 MHz stream domain to the pixel clock through its "
        "asynchronous FIFO and runs as timing slave (`C_VTG_MASTER_SLAVE` = 1): it gates the VTC's "
        "generator through `vtg_ce` → `gen_clken` until the stream's start of frame lines up with the "
        "timing, then reports locked. `v_tc_0` is a fixed 720p generator without an AXI4-Lite port.")

    d.subsection("TMDS transmitter (hdmi_tx)", label="sec-hdmitx")
    d.figure("hdmi_tx: three TMDS encoders and four 10:1 serialisers.", P.fig_hdmitx(), label="fig-hdmitx")
    d.p("`hdmi_tx` registers the parallel video, encodes each colour with a `tmds_encoder` and "
        "serialises the 10-bit symbols. The encoder is the DVI 1.0 algorithm in two pipeline stages: "
        "stage 1 picks the XOR or XNOR chain that minimises transitions; stage 2 keeps the running "
        "disparity balanced by optionally inverting the symbol. During blanking it sends the four "
        "control symbols, carrying HSYNC and VSYNC on the blue channel. Each lane uses a master and a "
        "slave OSERDESE2 cascaded for 10:1 DDR serialisation, least significant bit first; the clock "
        "lane sends 0000011111, which reproduces the pixel clock. Outputs are OBUFDS with "
        "IOSTANDARD TMDS_33.")

    d.subsection("Video status")
    regfields(d, "axi_gpio_video: GPIO_DATA Register", "0x000", "", [
        ["31:3", "-", "Reserved", "-", "-"],
        ["2", "UNDERFLOW", "Video out FIFO ran empty: the VDMA could not keep up", "RO", "-"],
        ["1", "VID_LOCKED", "Video out locked to the VTC timing", "RO", "-"],
        ["0", "MMCM_LOCKED", "clk_wiz_hdmi locked, pixel and serial clocks valid", "RO", "-"],
    ])

    d.section("Pins")
    d.table("PL pin assignment (`zynq_zero.xdc`).", ["Port", "Ball", "Bank", "I/O standard", "Board net"], [
        ["leds_tri_o[0..3]", "W13, V12, U12, T12", "34", "LVCMOS33", "LED1-LED4 (active high)"],
        ["keys_tri_i[0]", "Y16", "34", "LVCMOS33", "KEY1, 4.7 kΩ pull-up"],
        ["hdmi_clk_p / _n", "H16 / H17", "35", "TMDS_33", "HDMI clock"],
        ["hdmi_d_p / _n[0]", "D19 / D20", "35", "TMDS_33", "HDMI data 0 (blue + sync)"],
        ["hdmi_d_p / _n[1]", "C20 / B20", "35", "TMDS_33", "HDMI data 1 (green)"],
        ["hdmi_d_p / _n[2]", "B19 / A20", "35", "TMDS_33", "HDMI data 2 (red)"],
    ], mono=(0, 1), widths=[22, 22, 8, 16, 32])
    d.p("LEDs and the key are asynchronous and carry `set_false_path` constraints. PS pins (MIO, DDR, "
        "PS_CLK) are placed by the PS7 IP and need no constraints.")

    d.section("Verilog modules", label="sec-rtl")
    d.table("Verilog in `hw/rtl/`.", ["Module", "Lines", "Function"], [
        ["`axil_slave`", "103", "AXI4-Lite slave → simple register bus: one-cycle write strobe, read strobe with one-cycle data latency (suits block RAM)"],
        ["`tdp_ram`", "37", "true dual-port block RAM, read-first, inferred from the UG901 template"],
        ["`twiddle_rom`", "529", "512 × 36-bit {cos, sin} ROM, generated by `gen_twiddle.py`"],
        ["`myfft_axil`", "322", "own radix-2 FFT engine: registers, bit reversal, ping-pong RAMs, butterfly pipeline, sequencer"],
        ["`xfft_ctrl`", "269", "AXI4-Lite front end for xfft: input RAM, stream FSM, output RAMs"],
        ["`tmds_encoder`", "86", "DVI 1.0 8b/10b TMDS encoder, two-stage pipeline"],
        ["`hdmi_tx`", "113", "three encoders, four OSERDESE2 pairs, OBUFDS"],
    ], widths=[17, 8, 75])
    d.p("`build.sh sim` runs the testbenches in `hw/sim/` with Icarus Verilog. `tb_fft.v` drives both "
        "engine wrappers over their register interface (the Xilinx core replaced by a behavioural "
        "model, `xfft_model.v`) at 8 to 1024 points, and `run_sim.py` checks the results against "
        "numpy. `tb_hdmi.v` checks the TMDS encoder against a reference decoder, then sends small "
        "frames through `hdmi_tx` with behavioural OSERDESE2 and OBUFDS models (`unisim_stubs.v`), "
        "deserialises the lanes and compares every pixel and sync bit.")

    d.section("Xilinx IP")
    d.table("Xilinx IP in the block design. `build.tcl` picks the newest version in the installed "
            "catalog; the versions shown are those of Vivado 2021.1.", ["IP", "Version", "Instances", "Configuration"], [
        ["processing_system7", "5.5", "ps7", "see {ref:tab-ps7}"],
        ["axi_interconnect", "2.1", "2 (automation)", "GP0 → 5 slaves; VDMA → HP0"],
        ["proc_sys_reset", "5.0", "2", "100 MHz domain (automation), `rst_pixel`"],
        ["axi_gpio", "2.0", "2", "`axi_gpio_0` 4 out + 1 in; `axi_gpio_video` 3 in"],
        ["xfft", "9.1", "xfft_0", "radix-2 burst, 1024, unscaled"],
        ["axi_vdma", "6.3", "axi_vdma_0", "MM2S only, 16-bit, 2 frame stores"],
        ["axis_subset_converter", "1.1", "rgb565_to_888", "2 → 3 bytes, bit remap"],
        ["v_axi4s_vid_out", "4.0", "v_axi4s_vid_out_0", "async clock, VTG slave"],
        ["v_tc", "6.2", "v_tc_0", "720p, generator only, no AXI4-Lite"],
        ["clk_wiz", "6.0", "clk_wiz_hdmi", "MMCM, 74.25 + 371.25 MHz"],
        ["xlconcat", "2.1", "video_status", "3 status bits → GPIO"],
    ], widths=[23, 9, 20, 48])
