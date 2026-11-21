`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// tmds_encoder.v - DVI 1.0 TMDS 8b/10b encoder (one channel), 2-stage pipeline.
//
//   de = 1: video data d -> transition-minimised, DC-balanced 10-bit symbol
//   de = 0: control symbol for c = {C1, C0}
//            (blue channel: C0 = HSYNC, C1 = VSYNC; red/green: 00)
// q is valid two clocks after d/c/de.
//------------------------------------------------------------------------------
module tmds_encoder (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] d,
    input  wire [1:0] c,
    input  wire       de,
    output reg  [9:0] q
);

    function [3:0] ones8;
        input [7:0] v;
        integer i;
        begin
            ones8 = 4'd0;
            for (i = 0; i < 8; i = i + 1)
                ones8 = ones8 + v[i];
        end
    endfunction

    // ---- Stage 1: transition minimisation (XOR or XNOR chain) ----------------
    wire [3:0] n1_d    = ones8(d);
    wire       use_xnor = (n1_d > 4'd4) || (n1_d == 4'd4 && d[0] == 1'b0);
    wire [8:0] q_m;
    assign q_m[0] = d[0];
    genvar g;
    generate
        for (g = 1; g < 8; g = g + 1) begin : g_chain
            assign q_m[g] = use_xnor ? ~(q_m[g-1] ^ d[g]) : (q_m[g-1] ^ d[g]);
        end
    endgenerate
    assign q_m[8] = ~use_xnor;

    reg [8:0] q_m_r;
    reg [1:0] c_r;
    reg       de_r;
    always @(posedge clk) begin
        q_m_r <= q_m;
        c_r   <= c;
        de_r  <= de;
    end

    // ---- Stage 2: DC balance against the running disparity ----------------------
    wire [3:0]        n1_q = ones8(q_m_r[7:0]);
    wire signed [5:0] diff = $signed({2'b00, n1_q}) - $signed(6'd4);   // (#1 - #0) / 2
    reg  signed [5:0] cnt;                                             // running disparity

    // Disparity is tracked in units of bits (#1 - #0), as in the DVI spec.
    wire signed [5:0] n1_minus_n0 = diff <<< 1;

    always @(posedge clk) begin
        if (rst) begin
            q   <= 10'd0;
            cnt <= 6'sd0;
        end else if (!de_r) begin
            case (c_r)
                2'b00:   q <= 10'b1101010100;
                2'b01:   q <= 10'b0010101011;
                2'b10:   q <= 10'b0101010100;
                default: q <= 10'b1010101011;
            endcase
            cnt <= 6'sd0;
        end else if (cnt == 0 || n1_minus_n0 == 0) begin
            q <= {~q_m_r[8], q_m_r[8], q_m_r[8] ? q_m_r[7:0] : ~q_m_r[7:0]};
            if (q_m_r[8])
                cnt <= cnt + n1_minus_n0;
            else
                cnt <= cnt - n1_minus_n0;
        end else if ((cnt > 0 && n1_minus_n0 > 0) || (cnt < 0 && n1_minus_n0 < 0)) begin
            q   <= {1'b1, q_m_r[8], ~q_m_r[7:0]};
            cnt <= cnt + $signed({4'd0, q_m_r[8], 1'b0}) - n1_minus_n0;
        end else begin
            q   <= {1'b0, q_m_r[8], q_m_r[7:0]};
            cnt <= cnt - $signed({4'd0, ~q_m_r[8], 1'b0}) + n1_minus_n0;
        end
    end

endmodule
