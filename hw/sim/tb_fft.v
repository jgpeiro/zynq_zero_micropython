`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// tb_fft.v - Drives myfft_axil (default) or xfft_ctrl + xfft_model (-DXFFT)
// over AXI4-Lite exactly like the MicroPython driver does.
//
//   in.txt : log2n inverse, then N packed input words (hex)
//   out.txt: cycles overflow format, then N lines "re im" (decimal)
// Run through run_sim.py.
//------------------------------------------------------------------------------
module tb_fft;
    reg clk = 0, rstn = 0;
    always #5 clk = ~clk;   // 100 MHz

    reg  [15:0] awaddr, araddr;
    reg         awvalid = 0, wvalid = 0, bready = 0, arvalid = 0, rready = 0;
    reg  [31:0] wdata;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [31:0] rdata;
    wire [1:0]  bresp, rresp;

`ifdef XFFT
    wire [15:0] cfg_tdata;  wire cfg_tvalid, cfg_tready;
    wire [31:0] din_tdata;  wire din_tvalid, din_tready, din_tlast;
    wire [63:0] dout_tdata; wire dout_tvalid, dout_tready, dout_tlast;
    wire ev_unexp, ev_missing;

    xfft_ctrl dut (
        .aclk(clk), .aresetn(rstn),
        .s_axi_awaddr(awaddr), .s_axi_awprot(3'd0), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(4'hF), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arprot(3'd0), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready),
        .m_axis_config_tdata(cfg_tdata), .m_axis_config_tvalid(cfg_tvalid), .m_axis_config_tready(cfg_tready),
        .m_axis_data_tdata(din_tdata), .m_axis_data_tvalid(din_tvalid), .m_axis_data_tready(din_tready),
        .m_axis_data_tlast(din_tlast),
        .s_axis_data_tdata(dout_tdata), .s_axis_data_tvalid(dout_tvalid), .s_axis_data_tready(dout_tready),
        .s_axis_data_tlast(dout_tlast));

    xfft_model core (
        .aclk(clk), .aresetn(rstn),
        .s_axis_config_tdata(cfg_tdata), .s_axis_config_tvalid(cfg_tvalid), .s_axis_config_tready(cfg_tready),
        .s_axis_data_tdata(din_tdata), .s_axis_data_tvalid(din_tvalid), .s_axis_data_tready(din_tready),
        .s_axis_data_tlast(din_tlast),
        .m_axis_data_tdata(dout_tdata), .m_axis_data_tvalid(dout_tvalid), .m_axis_data_tready(dout_tready),
        .m_axis_data_tlast(dout_tlast),
        .event_tlast_unexpected(ev_unexp), .event_tlast_missing(ev_missing));
`else
    myfft_axil dut (
        .aclk(clk), .aresetn(rstn),
        .s_axi_awaddr(awaddr), .s_axi_awprot(3'd0), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(4'hF), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arprot(3'd0), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready));
`endif

    // ---- AXI4-Lite master (AW and W in random order, random B/R ready) ---------
    task axi_write(input [15:0] a, input [31:0] d);
        begin
            @(posedge clk);
            awaddr <= a; wdata <= d;
            if ($random & 1) begin awvalid <= 1; @(posedge clk); wvalid <= 1; end
            else             begin wvalid <= 1; @(posedge clk); awvalid <= 1; end
            while (!(awready)) @(posedge clk);   // AW and W accepted together
            awvalid <= 0; wvalid <= 0;
            repeat ($random & 1) @(posedge clk);
            bready <= 1;
            @(posedge clk);
            while (!bvalid) @(posedge clk);
            bready <= 0;
        end
    endtask

    task axi_read(input [15:0] a, output [31:0] d);
        begin
            @(posedge clk);
            araddr <= a; arvalid <= 1;
            @(posedge clk);
            while (!arready) @(posedge clk);
            arvalid <= 0;
            repeat ($random & 1) @(posedge clk);
            rready <= 1;
            @(posedge clk);
            while (!rvalid) @(posedge clk);
            d = rdata;
            rready <= 0;
        end
    endtask

    integer fin, fout, log2n, inverse, n, i, r;
    reg [31:0] word, status, cycles, fmt, re, im, id;

    initial begin
        fin = $fopen("in.txt", "r");
        r = $fscanf(fin, "%d %d\n", log2n, inverse);
        n = 1 << log2n;
        repeat (5) @(posedge clk);
        rstn <= 1;

        axi_read(16'h0000, id);
        axi_write(16'h000C, log2n);
        axi_write(16'h0010, inverse);
        for (i = 0; i < n; i = i + 1) begin
            r = $fscanf(fin, "%h\n", word);
            axi_write(16'h1000 + 4 * i, word);
        end
        $fclose(fin);
        axi_write(16'h0004, 1);
        status = 1;
        while (!status[1]) axi_read(16'h0008, status);
        axi_read(16'h0014, cycles);
        axi_read(16'h001C, fmt);

        fout = $fopen("out.txt", "w");
        $fwrite(fout, "%0d %0d %0d %h\n", cycles, status[2], fmt, id);
        for (i = 0; i < n; i = i + 1) begin
            if (fmt == 0) begin
                axi_read(16'h2000 + 4 * i, word);
                $fwrite(fout, "%0d %0d\n", $signed(word[15:0]), $signed(word[31:16]));
            end else begin
                axi_read(16'h2000 + 4 * i, re);
                axi_read(16'h3000 + 4 * i, im);
                $fwrite(fout, "%0d %0d\n", $signed(re), $signed(im));
            end
        end
        $fclose(fout);
`ifdef XFFT
        if (ev_unexp || ev_missing) $display("ERROR: TLAST event unexpected=%0d missing=%0d", ev_unexp, ev_missing);
`endif
        $finish;
    end

    initial begin
        #200_000_000;
        $display("ERROR: timeout");
        $finish;
    end
endmodule
