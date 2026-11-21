`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// axil_slave.v - AXI4-Lite slave -> simple register bus.
//
//   Write: one-cycle pulse on wr_en with wr_addr / wr_data (full 32-bit words,
//          WSTRB ignored: the FFT peripherals only take whole words).
//   Read:  one-cycle pulse on rd_en with rd_addr; the user logic must present
//          rd_data on the following cycle (1-cycle latency, suits block RAM).
//
// One transaction at a time per direction, which is all an AXI4-Lite master
// behind an interconnect needs.
//------------------------------------------------------------------------------
module axil_slave #(
    parameter ADDR_W = 16
) (
    input  wire              aclk,
    input  wire              aresetn,

    input  wire [ADDR_W-1:0] s_axi_awaddr,
    input  wire              s_axi_awvalid,
    output reg               s_axi_awready,
    input  wire [31:0]       s_axi_wdata,
    input  wire              s_axi_wvalid,
    output reg               s_axi_wready,
    output wire [1:0]        s_axi_bresp,
    output reg               s_axi_bvalid,
    input  wire              s_axi_bready,
    input  wire [ADDR_W-1:0] s_axi_araddr,
    input  wire              s_axi_arvalid,
    output reg               s_axi_arready,
    output reg  [31:0]       s_axi_rdata,
    output wire [1:0]        s_axi_rresp,
    output reg               s_axi_rvalid,
    input  wire              s_axi_rready,

    output reg               wr_en,
    output reg  [ADDR_W-1:0] wr_addr,
    output reg  [31:0]       wr_data,
    output reg               rd_en,
    output reg  [ADDR_W-1:0] rd_addr,
    input  wire [31:0]       rd_data
);

    assign s_axi_bresp = 2'b00;
    assign s_axi_rresp = 2'b00;

    // ---- Write: accept AW and W together ------------------------------------
    always @(posedge aclk) begin
        if (!aresetn) begin
            s_axi_awready <= 1'b0;
            s_axi_wready  <= 1'b0;
            s_axi_bvalid  <= 1'b0;
            wr_en         <= 1'b0;
            wr_addr       <= {ADDR_W{1'b0}};
            wr_data       <= 32'd0;
        end else begin
            wr_en         <= 1'b0;
            s_axi_awready <= 1'b0;
            s_axi_wready  <= 1'b0;
            if (s_axi_bvalid && s_axi_bready)
                s_axi_bvalid <= 1'b0;
            if (s_axi_awvalid && s_axi_wvalid && !s_axi_awready && !s_axi_bvalid) begin
                s_axi_awready <= 1'b1;
                s_axi_wready  <= 1'b1;
                s_axi_bvalid  <= 1'b1;
                wr_en         <= 1'b1;
                wr_addr       <= s_axi_awaddr;
                wr_data       <= s_axi_wdata;
            end
        end
    end

    // ---- Read: address -> rd_en pulse -> data one cycle later ---------------
    reg rd_wait;
    always @(posedge aclk) begin
        if (!aresetn) begin
            s_axi_arready <= 1'b0;
            s_axi_rvalid  <= 1'b0;
            s_axi_rdata   <= 32'd0;
            rd_en         <= 1'b0;
            rd_addr       <= {ADDR_W{1'b0}};
            rd_wait       <= 1'b0;
        end else begin
            rd_en         <= 1'b0;
            s_axi_arready <= 1'b0;
            if (s_axi_rvalid && s_axi_rready)
                s_axi_rvalid <= 1'b0;
            if (s_axi_arvalid && !s_axi_arready && !s_axi_rvalid && !rd_en && !rd_wait) begin
                s_axi_arready <= 1'b1;
                rd_en         <= 1'b1;
                rd_addr       <= s_axi_araddr;
            end
            // rd_en is high this cycle -> user logic registers its output on this
            // edge -> rd_data is valid next cycle
            rd_wait <= rd_en;
            if (rd_wait) begin
                s_axi_rdata  <= rd_data;
                s_axi_rvalid <= 1'b1;
            end
        end
    end

endmodule
