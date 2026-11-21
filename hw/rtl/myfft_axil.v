`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// myfft_axil.v - Radix-2 FFT written from scratch, behind AXI4-Lite.
//
// Algorithm: iterative decimation-in-time Cooley-Tukey, N = 2^LOG2N
// (8 .. 2^LOG2N_MAX points, chosen at run time).
//   * Input samples are stored bit-reversed as they arrive over AXI.
//   * Each stage reads all N points from one block RAM and writes the other
//     (ping-pong), so both RAM ports are free for the butterfly every cycle:
//     one radix-2 butterfly per clock, log2(N) * (N/2 + 6) cycles per FFT.
//   * Butterfly: y0 = (x0 + W*x1) / 2, y1 = (x0 - W*x1) / 2, rounded and
//     saturated to 16 bits. The 1/2 per stage keeps the word length fixed; the
//     result is FFT(x) / N (forward) or IFFT(X) (inverse). No overflow as
//     long as every input |x| < 1 (complex magnitude), which the driver ensures.
//   * W = cos -/+ j sin from a 512-entry 18-bit ROM (twiddle_rom.v), 4 DSP48s.
//
// Data format: Q1.15 complex, packed {im[31:16], re[15:0]}.
//
// Register map (byte offsets; shared with xfft_ctrl.v, see FORMAT):
//   0x0000 ID         RO  0x4D464654 "MFFT"
//   0x0004 CTRL       WO  bit 0: start
//   0x0008 STATUS     RO  bit 0 busy, bit 1 done, bit 2 overflow (saturation)
//   0x000C LOG2N      RW  3 .. LOG2N_MAX
//   0x0010 INVERSE    RW  bit 0: 1 = inverse transform
//   0x0014 CYCLES     RO  clock cycles of the last transform (start -> done)
//   0x0018 LOG2N_MAX  RO
//   0x001C FORMAT     RO  0: output packed Q1.15 at 0x2000, scaled by 1/N
//   0x1000 + 4*i      WO  input sample i (natural order)
//   0x2000 + 4*i      RO  output sample i (natural order)
//------------------------------------------------------------------------------
module myfft_axil #(
    parameter LOG2N_MAX = 10
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET aresetn" *)
    input  wire        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 16" *)
    input  wire [15:0] s_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWPROT" *)
    input  wire [2:0]  s_axi_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWVALID" *)
    input  wire        s_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWREADY" *)
    output wire        s_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WDATA" *)
    input  wire [31:0] s_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WSTRB" *)
    input  wire [3:0]  s_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WVALID" *)
    input  wire        s_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WREADY" *)
    output wire        s_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BRESP" *)
    output wire [1:0]  s_axi_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BVALID" *)
    output wire        s_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BREADY" *)
    input  wire        s_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARADDR" *)
    input  wire [15:0] s_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARPROT" *)
    input  wire [2:0]  s_axi_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARVALID" *)
    input  wire        s_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARREADY" *)
    output wire        s_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RDATA" *)
    output wire [31:0] s_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RRESP" *)
    output wire [1:0]  s_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RVALID" *)
    output wire        s_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RREADY" *)
    input  wire        s_axi_rready
);

    localparam AW  = LOG2N_MAX;          // sample index width
    localparam BW  = LOG2N_MAX - 1;      // butterfly index / twiddle index width
    localparam [31:0] ID = 32'h4D464654; // "MFFT"

    // ---- AXI4-Lite -> register bus -----------------------------------------------
    wire        wr_en, rd_en;
    wire [15:0] wr_addr, rd_addr;
    wire [31:0] wr_data;
    reg  [31:0] rd_data;

    axil_slave #(.ADDR_W(16)) u_axil (
        .aclk(aclk), .aresetn(aresetn),
        .s_axi_awaddr(s_axi_awaddr), .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata), .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
        .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid), .s_axi_bready(s_axi_bready),
        .s_axi_araddr(s_axi_araddr), .s_axi_arvalid(s_axi_arvalid), .s_axi_arready(s_axi_arready),
        .s_axi_rdata(s_axi_rdata), .s_axi_rresp(s_axi_rresp), .s_axi_rvalid(s_axi_rvalid),
        .s_axi_rready(s_axi_rready),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_data)
    );

    // ---- Control registers ----------------------------------------------------------
    reg [3:0]  log2n;
    reg        inverse;
    reg        busy, done, ovf;
    reg [31:0] cycles;

    wire wr_reg   = wr_en && (wr_addr[15:12] == 4'h0);
    wire wr_input = wr_en && (wr_addr[15:12] == 4'h1);
    wire rd_out   = rd_en && (rd_addr[15:12] == 4'h2);
    wire start    = wr_reg && (wr_addr[11:0] == 12'h004) && wr_data[0] && !busy;

    always @(posedge aclk) begin
        if (!aresetn) begin
            log2n   <= LOG2N_MAX[3:0];
            inverse <= 1'b0;
        end else if (wr_reg && !busy) begin
            case (wr_addr[11:0])
                12'h00C: log2n <= (wr_data[3:0] < 4'd3) ? 4'd3 :
                                  (wr_data[3:0] > LOG2N_MAX) ? LOG2N_MAX[3:0] : wr_data[3:0];
                12'h010: inverse <= wr_data[0];
                default: ;
            endcase
        end
    end

    // Bit-reversed input index for the current size
    wire [AW-1:0] in_idx = wr_addr[AW+1:2];
    reg  [AW-1:0] in_idx_rev;
    integer b;
    always @* begin
        for (b = 0; b < AW; b = b + 1)
            in_idx_rev[b] = in_idx[AW-1-b];
        in_idx_rev = in_idx_rev >> (LOG2N_MAX - log2n);
    end

    // ---- Engine state ------------------------------------------------------------------
    reg [3:0]    stage;
    reg [BW-1:0] j;             // butterfly index within the stage
    reg          issuing;
    wire [BW-1:0] j_last = (1 << (log2n - 1)) - 1;
    wire          issue  = busy && issuing;
    wire          src1   = stage[0];   // stage reads ram1 if odd, else ram0
    wire          final1 = log2n[0];   // result lands in ram1 if log2n is odd

    // Butterfly addresses: i0 = group * 2^(s+1) + pos, i1 = i0 + 2^s,
    // twiddle index pos * 2^(LOG2N_MAX-1-s) (independent of N)
    wire [BW-1:0] half_mask = (1 << stage) - 1;
    wire [BW-1:0] pos       = j & half_mask;
    wire [AW-1:0] grp_base  = ({1'b0, j} >> stage) << (stage + 1);
    wire [AW-1:0] i0        = grp_base | pos;
    wire [AW-1:0] i1        = i0 | ({{(AW-1){1'b0}}, 1'b1} << stage);
    wire [BW-1:0] tw_k      = pos << (LOG2N_MAX - 1 - stage);

    // ---- Memories ------------------------------------------------------------------------
    reg           r0_ena, r0_wea, r0_enb, r0_web, r1_ena, r1_wea, r1_enb, r1_web;
    reg  [AW-1:0] r0_addra, r0_addrb, r1_addra, r1_addrb;
    reg  [31:0]   r0_dia, r0_dib, r1_dia, r1_dib;
    wire [31:0]   r0_doa, r0_dob, r1_doa, r1_dob;

    tdp_ram #(.AW(AW), .DW(32)) u_ram0 (
        .clk(aclk),
        .ena(r0_ena), .wea(r0_wea), .addra(r0_addra), .dia(r0_dia), .doa(r0_doa),
        .enb(r0_enb), .web(r0_web), .addrb(r0_addrb), .dib(r0_dib), .dob(r0_dob));
    tdp_ram #(.AW(AW), .DW(32)) u_ram1 (
        .clk(aclk),
        .ena(r1_ena), .wea(r1_wea), .addra(r1_addra), .dia(r1_dia), .doa(r1_doa),
        .enb(r1_enb), .web(r1_web), .addrb(r1_addrb), .dib(r1_dib), .dob(r1_dob));

    wire [35:0] tw_q;
    twiddle_rom u_tw (.clk(aclk), .en(issue), .k(tw_k), .q(tw_q));

    // ---- Butterfly pipeline ------------------------------------------------------------
    // p1: RAM/ROM read in flight   p2: operands   p3: products
    // p4: W*x1                      p5: y0/y1 -> written to the other RAM
    reg [4:0]    v;                 // valid bits p1..p5
    reg [AW-1:0] a0_p1, a1_p1, a0_p2, a1_p2, a0_p3, a1_p3, a0_p4, a1_p4, a0_p5, a1_p5;

    reg signed [15:0] x0r_p2, x0i_p2, x1r_p2, x1i_p2, x0r_p3, x0i_p3, x0r_p4, x0i_p4;
    reg signed [17:0] wr_p2, wi_p2;
    reg signed [33:0] m_rr, m_ii, m_ri, m_ir;
    reg signed [17:0] tr_p4, ti_p4;
    reg        [31:0] y0_p5, y1_p5;

    wire [31:0] x0 = src1 ? r1_doa : r0_doa;
    wire [31:0] x1 = src1 ? r1_dob : r0_dob;
    wire signed [17:0] tw_cos = tw_q[35:18];
    wire signed [17:0] tw_sin = tw_q[17:0];

    wire signed [34:0] t_re = m_rr - m_ii + 35'sd32768;   // + 0.5 LSB, then >>> 16
    wire signed [34:0] t_im = m_ri + m_ir + 35'sd32768;

    wire signed [18:0] s0r = x0r_p4 + tr_p4 + 19'sd1;     // + 0.5 LSB, then >>> 1
    wire signed [18:0] s0i = x0i_p4 + ti_p4 + 19'sd1;
    wire signed [18:0] s1r = x0r_p4 - tr_p4 + 19'sd1;
    wire signed [18:0] s1i = x0i_p4 - ti_p4 + 19'sd1;

    function [16:0] sat16;   // {overflow, value}
        input signed [18:0] s;
        reg   signed [17:0] h;
        begin
            h = s >>> 1;
            if (h > 18'sd32767)       sat16 = {1'b1, 16'h7FFF};
            else if (h < -18'sd32768) sat16 = {1'b1, 16'h8000};
            else                      sat16 = {1'b0, h[15:0]};
        end
    endfunction

    wire [16:0] q0r = sat16(s0r), q0i = sat16(s0i), q1r = sat16(s1r), q1i = sat16(s1i);

    always @(posedge aclk) begin
        if (!aresetn) begin
            v <= 5'd0;
        end else begin
            v <= {v[3:0], issue};
        end
        // p1: addresses of the reads issued this cycle
        a0_p1 <= i0;            a1_p1 <= i1;
        // p2: operands
        a0_p2 <= a0_p1;         a1_p2 <= a1_p1;
        x0r_p2 <= x0[15:0];     x0i_p2 <= x0[31:16];
        x1r_p2 <= x1[15:0];     x1i_p2 <= x1[31:16];
        wr_p2  <= tw_cos;
        wi_p2  <= inverse ? tw_sin : -tw_sin;   // forward: W = cos - j sin
        // p3: products
        a0_p3 <= a0_p2;         a1_p3 <= a1_p2;
        x0r_p3 <= x0r_p2;       x0i_p3 <= x0i_p2;
        m_rr <= wr_p2 * x1r_p2; m_ii <= wi_p2 * x1i_p2;
        m_ri <= wr_p2 * x1i_p2; m_ir <= wi_p2 * x1r_p2;
        // p4: W * x1, back to Q1.15
        a0_p4 <= a0_p3;         a1_p4 <= a1_p3;
        x0r_p4 <= x0r_p3;       x0i_p4 <= x0i_p3;
        tr_p4 <= t_re[33:16];   ti_p4 <= t_im[33:16];
        // p5: butterfly outputs
        a0_p5 <= a0_p4;         a1_p5 <= a1_p4;
        y0_p5 <= {q0i[15:0], q0r[15:0]};
        y1_p5 <= {q1i[15:0], q1r[15:0]};
    end

    wire bfly_ovf = v[3] && (q0r[16] | q0i[16] | q1r[16] | q1i[16]);
    wire wb       = v[4];   // write back p5 this cycle

    // ---- Sequencer -------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (!aresetn) begin
            busy <= 1'b0; done <= 1'b0; ovf <= 1'b0; cycles <= 32'd0;
            stage <= 4'd0; j <= {BW{1'b0}}; issuing <= 1'b0;
        end else if (start) begin
            busy <= 1'b1; done <= 1'b0; ovf <= 1'b0; cycles <= 32'd0;
            stage <= 4'd0; j <= {BW{1'b0}}; issuing <= 1'b1;
        end else if (busy) begin
            cycles <= cycles + 32'd1;
            if (bfly_ovf)
                ovf <= 1'b1;
            if (issuing) begin
                if (j == j_last)
                    issuing <= 1'b0;
                j <= j + 1'b1;
            end else if (v == 5'd0) begin
                // stage drained
                if (stage == log2n - 1) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end else begin
                    stage   <= stage + 1'b1;
                    j       <= {BW{1'b0}};
                    issuing <= 1'b1;
                end
            end
        end
    end

    // ---- RAM port muxing ---------------------------------------------------------------------
    // Busy: source RAM reads (ports A/B = x0/x1), destination RAM writes (y0/y1).
    // Idle: ram0 port A takes input writes; port B of the result RAM serves reads.
    always @* begin
        r0_ena = 1'b0; r0_wea = 1'b0; r0_addra = {AW{1'b0}}; r0_dia = 32'd0;
        r0_enb = 1'b0; r0_web = 1'b0; r0_addrb = {AW{1'b0}}; r0_dib = 32'd0;
        r1_ena = 1'b0; r1_wea = 1'b0; r1_addra = {AW{1'b0}}; r1_dia = 32'd0;
        r1_enb = 1'b0; r1_web = 1'b0; r1_addrb = {AW{1'b0}}; r1_dib = 32'd0;
        if (busy) begin
            if (!src1) begin
                r0_ena = issue; r0_addra = i0;
                r0_enb = issue; r0_addrb = i1;
                r1_ena = wb; r1_wea = wb; r1_addra = a0_p5; r1_dia = y0_p5;
                r1_enb = wb; r1_web = wb; r1_addrb = a1_p5; r1_dib = y1_p5;
            end else begin
                r1_ena = issue; r1_addra = i0;
                r1_enb = issue; r1_addrb = i1;
                r0_ena = wb; r0_wea = wb; r0_addra = a0_p5; r0_dia = y0_p5;
                r0_enb = wb; r0_web = wb; r0_addrb = a1_p5; r0_dib = y1_p5;
            end
        end else begin
            r0_ena = wr_input; r0_wea = wr_input; r0_addra = in_idx_rev; r0_dia = wr_data;
            r0_enb = rd_out && !final1; r0_addrb = rd_addr[AW+1:2];
            r1_enb = rd_out &&  final1; r1_addrb = rd_addr[AW+1:2];
        end
    end

    // ---- Register reads (1-cycle latency) ------------------------------------------------------
    reg        rd_ram;
    reg [31:0] rd_reg;
    always @(posedge aclk) begin
        if (rd_en) begin
            rd_ram <= (rd_addr[15:12] == 4'h2);
            case (rd_addr[11:0])
                12'h000: rd_reg <= ID;
                12'h008: rd_reg <= {29'd0, ovf, done, busy};
                12'h00C: rd_reg <= {28'd0, log2n};
                12'h010: rd_reg <= {31'd0, inverse};
                12'h014: rd_reg <= cycles;
                12'h018: rd_reg <= LOG2N_MAX;
                12'h01C: rd_reg <= 32'd0;               // FORMAT 0
                default: rd_reg <= 32'd0;
            endcase
        end
    end
    always @* rd_data = rd_ram ? (final1 ? r1_dob : r0_dob) : rd_reg;

endmodule
