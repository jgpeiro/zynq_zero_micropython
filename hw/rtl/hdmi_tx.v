`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// hdmi_tx.v - Parallel RGB video -> HDMI/DVI TMDS outputs (7-series, TMDS_33).
//
// Xilinx has no free HDMI transmitter IP for 7-series, so this is the one block
// of the video path written by hand:
//   * vid_data {R[23:16], B[15:8], G[7:0]} (Xilinx AXI4-Stream video RGB order,
//     as produced by v_axi4s_vid_out), DE, HSYNC, VSYNC
//   * 3x TMDS encoder (DVI 1.0): ch0 = blue + {VSYNC, HSYNC}, ch1 = green, ch2 = red
//   * 10:1 serialisation with OSERDESE2 master/slave pairs, DDR on ser_clk
//     (5 x pixel clock), LSB first
//   * clock channel sends 0000011111 -> the pixel clock
//   * OBUFDS outputs; give the pins IOSTANDARD TMDS_33 in the XDC
//
// DVI signalling (video only, no HDMI data islands/audio), which every HDMI sink
// accepts. 720p60: pix_clk 74.25 MHz, ser_clk 371.25 MHz (742.5 Mb/s per lane).
// pix_clk and ser_clk must come from the same MMCM (phase aligned).
//------------------------------------------------------------------------------
module hdmi_tx (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 pix_clk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF vid_in, ASSOCIATED_RESET rst" *)
    input  wire        pix_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ser_clk CLK" *)
    input  wire        ser_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 rst RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
    input  wire        rst,

    (* X_INTERFACE_INFO = "xilinx.com:interface:vid_io:1.0 vid_in DATA" *)
    input  wire [23:0] vid_data,
    (* X_INTERFACE_INFO = "xilinx.com:interface:vid_io:1.0 vid_in ACTIVE_VIDEO" *)
    input  wire        vid_active_video,
    (* X_INTERFACE_INFO = "xilinx.com:interface:vid_io:1.0 vid_in HSYNC" *)
    input  wire        vid_hsync,
    (* X_INTERFACE_INFO = "xilinx.com:interface:vid_io:1.0 vid_in VSYNC" *)
    input  wire        vid_vsync,

    output wire        tmds_clk_p,
    output wire        tmds_clk_n,
    output wire [2:0]  tmds_data_p,
    output wire [2:0]  tmds_data_n
);

    // ---- Reset: hold the serialisers in reset for a few pixel clocks ----------
    reg [3:0] rst_sr = 4'hF;
    always @(posedge pix_clk or posedge rst)
        if (rst) rst_sr <= 4'hF;
        else     rst_sr <= {rst_sr[2:0], 1'b0};
    wire srst = rst_sr[3];

    // ---- Input register ------------------------------------------------------------
    reg [7:0] r, g, b;
    reg       de, hs, vs;
    always @(posedge pix_clk) begin
        r  <= vid_data[23:16];
        b  <= vid_data[15:8];
        g  <= vid_data[7:0];
        de <= vid_active_video;
        hs <= vid_hsync;
        vs <= vid_vsync;
    end

    // ---- TMDS encoding ---------------------------------------------------------------
    wire [9:0] sym [0:3];
    tmds_encoder u_enc_b (.clk(pix_clk), .rst(srst), .d(b), .c({vs, hs}), .de(de), .q(sym[0]));
    tmds_encoder u_enc_g (.clk(pix_clk), .rst(srst), .d(g), .c(2'b00),    .de(de), .q(sym[1]));
    tmds_encoder u_enc_r (.clk(pix_clk), .rst(srst), .d(r), .c(2'b00),    .de(de), .q(sym[2]));
    assign sym[3] = 10'b0000011111;   // clock lane

    // ---- 10:1 serialisers + differential buffers -----------------------------------------
    wire [3:0] ser_out;
    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : g_lane
            wire shift1, shift2;

            OSERDESE2 #(
                .DATA_RATE_OQ("DDR"), .DATA_RATE_TQ("SDR"), .DATA_WIDTH(10),
                .SERDES_MODE("MASTER"), .TRISTATE_WIDTH(1), .TBYTE_CTL("FALSE"),
                .TBYTE_SRC("FALSE"), .INIT_OQ(1'b0), .SRVAL_OQ(1'b0)
            ) u_master (
                .CLK(ser_clk), .CLKDIV(pix_clk), .RST(srst), .OCE(1'b1),
                .D1(sym[i][0]), .D2(sym[i][1]), .D3(sym[i][2]), .D4(sym[i][3]),
                .D5(sym[i][4]), .D6(sym[i][5]), .D7(sym[i][6]), .D8(sym[i][7]),
                .SHIFTIN1(shift1), .SHIFTIN2(shift2),
                .OQ(ser_out[i]), .OFB(), .SHIFTOUT1(), .SHIFTOUT2(),
                .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0), .TCE(1'b0), .TBYTEIN(1'b0),
                .TQ(), .TFB(), .TBYTEOUT()
            );

            OSERDESE2 #(
                .DATA_RATE_OQ("DDR"), .DATA_RATE_TQ("SDR"), .DATA_WIDTH(10),
                .SERDES_MODE("SLAVE"), .TRISTATE_WIDTH(1), .TBYTE_CTL("FALSE"),
                .TBYTE_SRC("FALSE"), .INIT_OQ(1'b0), .SRVAL_OQ(1'b0)
            ) u_slave (
                .CLK(ser_clk), .CLKDIV(pix_clk), .RST(srst), .OCE(1'b1),
                .D1(1'b0), .D2(1'b0), .D3(sym[i][8]), .D4(sym[i][9]),
                .D5(1'b0), .D6(1'b0), .D7(1'b0), .D8(1'b0),
                .SHIFTIN1(1'b0), .SHIFTIN2(1'b0),
                .SHIFTOUT1(shift1), .SHIFTOUT2(shift2),
                .OQ(), .OFB(),
                .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0), .TCE(1'b0), .TBYTEIN(1'b0),
                .TQ(), .TFB(), .TBYTEOUT()
            );
        end
    endgenerate

    OBUFDS u_obuf_c  (.I(ser_out[3]), .O(tmds_clk_p),     .OB(tmds_clk_n));
    OBUFDS u_obuf_d0 (.I(ser_out[0]), .O(tmds_data_p[0]), .OB(tmds_data_n[0]));
    OBUFDS u_obuf_d1 (.I(ser_out[1]), .O(tmds_data_p[1]), .OB(tmds_data_n[1]));
    OBUFDS u_obuf_d2 (.I(ser_out[2]), .O(tmds_data_p[2]), .OB(tmds_data_n[2]));

endmodule
