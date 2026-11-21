`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// unisim_stubs.v - Minimal behavioural OSERDESE2 / OBUFDS for iverilog.
// Simulation only (Vivado uses the real primitives). Models only what
// hdmi_tx.v uses: 10:1 DDR, master/slave, D1 sent first.
//------------------------------------------------------------------------------
module OSERDESE2 #(
    parameter DATA_RATE_OQ = "DDR", parameter DATA_RATE_TQ = "SDR",
    parameter integer DATA_WIDTH = 10, parameter SERDES_MODE = "MASTER",
    parameter integer TRISTATE_WIDTH = 1, parameter TBYTE_CTL = "FALSE",
    parameter TBYTE_SRC = "FALSE", parameter [0:0] INIT_OQ = 1'b0,
    parameter [0:0] SRVAL_OQ = 1'b0
) (
    input  CLK, input CLKDIV, input RST, input OCE,
    input  D1, input D2, input D3, input D4, input D5, input D6, input D7, input D8,
    input  SHIFTIN1, input SHIFTIN2,
    output reg OQ, output OFB, output SHIFTOUT1, output SHIFTOUT2,
    input  T1, input T2, input T3, input T4, input TCE, input TBYTEIN,
    output TQ, output TFB, output TBYTEOUT
);
    // Slave: hand D3/D4 (bits 9 and 10) to the master
    assign SHIFTOUT1 = D3;
    assign SHIFTOUT2 = D4;
    assign OFB = OQ;
    assign TQ = 1'b0;
    assign TFB = 1'b0;
    assign TBYTEOUT = 1'b0;

    reg [9:0] word, shreg;
    reg [3:0] cnt;
    always @(posedge CLKDIV)
        word <= {SHIFTIN2, SHIFTIN1, D8, D7, D6, D5, D4, D3, D2, D1};

    // Load on the first CLK edge after the CLKDIV edge, then shift out on both edges
    reg load_req = 0;
    always @(posedge CLKDIV) load_req <= 1'b1;
    always @(CLK) begin
        if (RST) begin
            OQ <= INIT_OQ; cnt <= 0;
        end else if (cnt == 0 && load_req) begin
            OQ <= word[0]; shreg <= word >> 1; cnt <= 9; load_req <= 1'b0;
        end else if (cnt != 0) begin
            OQ <= shreg[0]; shreg <= shreg >> 1; cnt <= cnt - 1'b1;
        end
    end
endmodule

module OBUFDS (input I, output O, output OB);
    assign O = I;
    assign OB = ~I;
endmodule
