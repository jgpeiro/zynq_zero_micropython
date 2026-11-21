`timescale 1ns / 1ps
// tdp_ram.v - True dual-port block RAM, read-first, 1-cycle read latency
// (Vivado UG901 "dual-port block RAM with two write ports" template).
module tdp_ram #(
    parameter AW = 10,
    parameter DW = 32
) (
    input  wire          clk,
    input  wire          ena,
    input  wire          wea,
    input  wire [AW-1:0] addra,
    input  wire [DW-1:0] dia,
    output reg  [DW-1:0] doa,
    input  wire          enb,
    input  wire          web,
    input  wire [AW-1:0] addrb,
    input  wire [DW-1:0] dib,
    output reg  [DW-1:0] dob
);
    reg [DW-1:0] ram [0:(1<<AW)-1];

    always @(posedge clk) begin
        if (ena) begin
            if (wea)
                ram[addra] <= dia;
            doa <= ram[addra];
        end
    end

    always @(posedge clk) begin
        if (enb) begin
            if (web)
                ram[addrb] <= dib;
            dob <= ram[addrb];
        end
    end
endmodule
