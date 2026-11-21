`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// xfft_ctrl.v - AXI4-Lite front end for the Xilinx FFT LogiCORE (xfft v9.1).
//
// The xfft core sits next to this module in the block design and talks
// AXI4-Stream. A transform is:
//   1. config word on m_axis_config: {7'b0, FWD_INV, 3'b0, NFFT[4:0]}
//   2. N input samples from the input RAM on m_axis_data (TLAST on the last)
//   3. N output samples from s_axis_data stored in the output RAMs
//
// xfft is set up as radix-2 burst I/O, run-time length 8..1024, 16-bit input,
// UNSCALED (full precision, no overflow possible), natural-order output.
// Output words are OUT_W-bit signed (27 for 1024 points), re in tdata[31:0],
// im in tdata[63:32]: the result is sum x[n] e^(-/+ j..) with no 1/N.
//
// Register map: same as myfft_axil.v, with
//   0x0000 ID      0x58464654 "XFFT"
//   0x001C FORMAT  1: output re at 0x2000 + 4*i, im at 0x3000 + 4*i,
//                  each a sign-extended 32-bit integer, unscaled.
//   0x0008 STATUS  bit 2 (overflow) is always 0 here.
//------------------------------------------------------------------------------
module xfft_ctrl #(
    parameter LOG2N_MAX = 10,
    parameter OUT_W     = 27        // xfft output width per component
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi:m_axis_config:m_axis_data:s_axis_data, ASSOCIATED_RESET aresetn" *)
    input  wire        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    // AXI4-Lite slave (registers + sample buffers)
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
    input  wire        s_axi_rready,

    // -> xfft S_AXIS_CONFIG
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis_config TDATA" *)
    output wire [15:0] m_axis_config_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis_config TVALID" *)
    output reg         m_axis_config_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis_config TREADY" *)
    input  wire        m_axis_config_tready,

    // -> xfft S_AXIS_DATA
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis_data TDATA" *)
    output wire [31:0] m_axis_data_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis_data TVALID" *)
    output wire        m_axis_data_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis_data TREADY" *)
    input  wire        m_axis_data_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis_data TLAST" *)
    output wire        m_axis_data_tlast,

    // <- xfft M_AXIS_DATA
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis_data TDATA" *)
    input  wire [63:0] s_axis_data_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis_data TVALID" *)
    input  wire        s_axis_data_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis_data TREADY" *)
    output wire        s_axis_data_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis_data TLAST" *)
    input  wire        s_axis_data_tlast
);

    localparam AW = LOG2N_MAX;
    localparam [31:0] ID = 32'h58464654; // "XFFT"

    // ---- AXI4-Lite -> register bus ------------------------------------------------
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

    // ---- Registers ----------------------------------------------------------------------
    reg [3:0]  log2n;
    reg        inverse;
    reg        busy, done;
    reg [31:0] cycles;

    wire wr_reg   = wr_en && (wr_addr[15:12] == 4'h0);
    wire wr_input = wr_en && (wr_addr[15:12] == 4'h1);
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

    // xfft config: NFFT in [4:0], FWD_INV (1 = forward) in [8]
    assign m_axis_config_tdata = {7'd0, ~inverse, 3'd0, 1'b0, log2n};

    wire [AW:0] n_pts = {{AW{1'b0}}, 1'b1} << log2n;

    // ---- Input RAM: written over AXI, streamed to the core --------------------------------
    reg  [31:0] in_ram [0:(1<<AW)-1];
    reg  [31:0] in_q;
    always @(posedge aclk)
        if (wr_input)
            in_ram[wr_addr[AW+1:2]] <= wr_data;

    // Stream state
    localparam S_IDLE = 2'd0, S_CFG = 2'd1, S_RUN = 2'd2;
    reg [1:0]  state;
    reg [AW:0] rd_idx;      // next sample to read from the RAM
    reg [AW:0] q_idx;       // sample held in in_q
    reg        q_valid;     // in_q holds a sample not yet accepted
    reg [AW:0] out_idx;     // output samples received

    wire take  = q_valid && m_axis_data_tready;
    wire fetch = (state == S_RUN) && (rd_idx != n_pts) && (!q_valid || take);

    always @(posedge aclk)
        if (fetch)
            in_q <= in_ram[rd_idx[AW-1:0]];

    assign m_axis_data_tdata  = in_q;
    assign m_axis_data_tvalid = q_valid;
    assign m_axis_data_tlast  = q_valid && (q_idx == n_pts - 1'b1);

    // ---- Output RAMs: written from the core, read over AXI -------------------------------
    reg [31:0] out_re [0:(1<<AW)-1];
    reg [31:0] out_im [0:(1<<AW)-1];
    reg [31:0] out_re_q, out_im_q;

    assign s_axis_data_tready = (state == S_RUN);
    wire   out_take = s_axis_data_tvalid && s_axis_data_tready;

    wire [31:0] y_re = {{(32-OUT_W){s_axis_data_tdata[OUT_W-1]}},    s_axis_data_tdata[OUT_W-1:0]};
    wire [31:0] y_im = {{(32-OUT_W){s_axis_data_tdata[32+OUT_W-1]}}, s_axis_data_tdata[32+OUT_W-1:32]};

    always @(posedge aclk) begin
        if (out_take) begin
            out_re[out_idx[AW-1:0]] <= y_re;
            out_im[out_idx[AW-1:0]] <= y_im;
        end
    end
    always @(posedge aclk) begin
        if (rd_en) begin
            out_re_q <= out_re[rd_addr[AW+1:2]];
            out_im_q <= out_im[rd_addr[AW+1:2]];
        end
    end

    // ---- Sequencer ---------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (!aresetn) begin
            state <= S_IDLE; busy <= 1'b0; done <= 1'b0; cycles <= 32'd0;
            m_axis_config_tvalid <= 1'b0;
            rd_idx <= 0; q_idx <= 0; q_valid <= 1'b0; out_idx <= 0;
        end else begin
            if (busy)
                cycles <= cycles + 32'd1;
            case (state)
                S_IDLE: begin
                    if (start) begin
                        busy <= 1'b1; done <= 1'b0; cycles <= 32'd0;
                        m_axis_config_tvalid <= 1'b1;
                        rd_idx <= 0; q_valid <= 1'b0; out_idx <= 0;
                        state <= S_CFG;
                    end
                end
                S_CFG: begin
                    if (m_axis_config_tready) begin
                        m_axis_config_tvalid <= 1'b0;
                        state <= S_RUN;
                    end
                end
                S_RUN: begin
                    if (fetch) begin
                        q_idx   <= rd_idx;
                        rd_idx  <= rd_idx + 1'b1;
                        q_valid <= 1'b1;
                    end else if (take) begin
                        q_valid <= 1'b0;
                    end
                    if (out_take) begin
                        out_idx <= out_idx + 1'b1;
                        if (out_idx == n_pts - 1'b1) begin
                            busy  <= 1'b0;
                            done  <= 1'b1;
                            state <= S_IDLE;
                        end
                    end
                end
                default: state <= S_IDLE;
            endcase
        end
    end

    // ---- Register / buffer reads (1-cycle latency) ---------------------------------------------
    reg [1:0]  rd_sel;      // 0 reg, 2 out_re, 3 out_im
    reg [31:0] rd_reg;
    always @(posedge aclk) begin
        if (rd_en) begin
            rd_sel <= rd_addr[15:12] == 4'h2 ? 2'd2 : rd_addr[15:12] == 4'h3 ? 2'd3 : 2'd0;
            case (rd_addr[11:0])
                12'h000: rd_reg <= ID;
                12'h008: rd_reg <= {29'd0, 1'b0, done, busy};
                12'h00C: rd_reg <= {28'd0, log2n};
                12'h010: rd_reg <= {31'd0, inverse};
                12'h014: rd_reg <= cycles;
                12'h018: rd_reg <= LOG2N_MAX;
                12'h01C: rd_reg <= 32'd1;               // FORMAT 1
                default: rd_reg <= 32'd0;
            endcase
        end
    end
    always @* rd_data = (rd_sel == 2'd2) ? out_re_q : (rd_sel == 2'd3) ? out_im_q : rd_reg;

endmodule
