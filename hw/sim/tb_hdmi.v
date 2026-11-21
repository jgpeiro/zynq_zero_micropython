`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// tb_hdmi.v - Checks the HDMI transmitter.
//   A) tmds_encoder: random video/control -> reference TMDS decoder; data and
//      control must come back exactly; running disparity stays bounded.
//   B) hdmi_tx: small frames through the serialisers (behavioural stubs),
//      deserialised by locking onto the clock lane, decoded per lane and
//      compared pixel by pixel (R, G, B, DE, HSYNC, VSYNC) with the input.
// Run: iverilog -o tb_hdmi tb_hdmi.v unisim_stubs.v ../rtl/tmds_encoder.v ../rtl/hdmi_tx.v
//------------------------------------------------------------------------------
module tb_hdmi;
    integer errors = 0;

    // ---- TMDS reference decoder -------------------------------------------------
    function [10:0] tmds_decode;    // {is_ctrl, c[1:0], d[7:0]}
        input [9:0] q;
        reg [7:0] dd, d;
        integer i;
        begin
            case (q)
                10'b1101010100: tmds_decode = {1'b1, 2'b00, 8'd0};
                10'b0010101011: tmds_decode = {1'b1, 2'b01, 8'd0};
                10'b0101010100: tmds_decode = {1'b1, 2'b10, 8'd0};
                10'b1010101011: tmds_decode = {1'b1, 2'b11, 8'd0};
                default: begin
                    dd = q[9] ? ~q[7:0] : q[7:0];
                    d[0] = dd[0];
                    for (i = 1; i < 8; i = i + 1)
                        d[i] = q[8] ? (dd[i] ^ dd[i-1]) : ~(dd[i] ^ dd[i-1]);
                    tmds_decode = {1'b0, 2'b00, d};
                end
            endcase
        end
    endfunction

    function integer ones10;
        input [9:0] v;
        integer i;
        begin
            ones10 = 0;
            for (i = 0; i < 10; i = i + 1) ones10 = ones10 + v[i];
        end
    endfunction

    // =========================== A) encoder ======================================
    reg        clk = 0;
    always #5 clk = ~clk;
    reg        rst = 1;
    reg  [7:0] d = 0;
    reg  [1:0] c = 0;
    reg        de = 0;
    wire [9:0] q;
    tmds_encoder dut_enc (.clk(clk), .rst(rst), .d(d), .c(c), .de(de), .q(q));

    // Inputs change 1 ns after a clock edge (no race with the DUT), are registered
    // at the next edge (stage 1) and the one after (stage 2): q, read 1 ns after
    // an edge, belongs to the inputs set two iterations earlier.
    reg  [7:0] d_h [0:2];
    reg  [1:0] c_h [0:2];
    reg        de_h[0:2];
    integer    disp, max_disp, n_checked;
    reg        a_done = 0;

    initial begin : test_a
        integer t;
        disp = 0; max_disp = 0; n_checked = 0;
        repeat (3) @(posedge clk);
        rst = 0;
        for (t = 0; t < 50000; t = t + 1) begin
            @(posedge clk);
            #1;
            // decode what was presented two clocks ago
            if (t > 3) begin
                if (de_h[1]) begin
                    if (tmds_decode(q) !== {1'b0, 2'b00, d_h[1]}) begin
                        errors = errors + 1;
                        if (errors < 10) $display("A: data %h -> %b decoded %h", d_h[1], q, tmds_decode(q));
                    end
                    disp = disp + 2 * ones10(q) - 10;
                    if (disp > max_disp) max_disp = disp;
                    if (-disp > max_disp) max_disp = -disp;
                end else begin
                    if (tmds_decode(q) !== {1'b1, c_h[1], 8'd0}) begin
                        errors = errors + 1;
                        if (errors < 10) $display("A: ctrl %b -> %b", c_h[1], q);
                    end
                    disp = 0;
                end
                n_checked = n_checked + 1;
            end
            de_h[1] = de_h[0]; d_h[1] = d_h[0]; c_h[1] = c_h[0];
            // mix of long data runs, extreme values and control periods
            de = ($random % 64) != 0 ? (t % 300 < 250) : de;
            d  = (t % 1000 < 100) ? 8'h00 : (t % 1000 < 200) ? 8'hFF : $random;
            c  = $random;
            de_h[0] = de; d_h[0] = d; c_h[0] = c;
        end
        $display("A) encoder: %0d symbols checked, max |running disparity| %0d bits, errors %0d",
                 n_checked, max_disp, errors);
        if (max_disp > 20) begin
            $display("A) ERROR: DC balance out of range");
            errors = errors + 1;
        end
        a_done = 1;
    end

    // =========================== B) full transmitter ===============================
    localparam HA = 16, HFP = 3, HS = 4, HBP = 5, HT = HA + HFP + HS + HBP;
    localparam VA = 6,  VFP = 1, VS = 1, VBP = 2, VT = VA + VFP + VS + VBP;
    localparam FRAMES = 3, NPIX = HT * VT * FRAMES + 200;

    // ser_clk 2 ns period (bits on both edges), pix_clk 10 ns: 10 bits per pixel
    reg pclk = 0, sclk = 0;
    integer kdiv = 0;
    always #1 sclk = ~sclk;
    always @(sclk) begin
        kdiv = (kdiv + 1) % 5;
        if (kdiv == 0) pclk = ~pclk;
    end

    reg        trst = 1;
    reg [23:0] vdata = 0;
    reg        vde = 0, vhs = 0, vvs = 0;
    wire       tclk_p, tclk_n;
    wire [2:0] tdat_p, tdat_n;
    hdmi_tx dut_tx (
        .pix_clk(pclk), .ser_clk(sclk), .rst(trst),
        .vid_data(vdata), .vid_active_video(vde), .vid_hsync(vhs), .vid_vsync(vvs),
        .tmds_clk_p(tclk_p), .tmds_clk_n(tclk_n), .tmds_data_p(tdat_p), .tmds_data_n(tdat_n));

    // Stimulus, recorded per pixel clock
    reg [23:0] in_rgb [0:NPIX-1];
    reg [2:0]  in_ctl [0:NPIX-1];    // {de, vs, hs}
    integer    tpix = 0;
    initial begin : stim
        integer f, y, x;
        repeat (10) @(posedge pclk);
        trst = 0;
        repeat (10) @(posedge pclk);
        for (f = 0; f < FRAMES; f = f + 1)
            for (y = 0; y < VT; y = y + 1)
                for (x = 0; x < HT; x = x + 1) begin
                    @(posedge pclk);
                    vde   <= (x < HA) && (y < VA);
                    vhs   <= (x >= HA + HFP) && (x < HA + HFP + HS);
                    vvs   <= (y >= VA + VFP) && (y < VA + VFP + VS);
                    vdata <= {$random} % (1 << 24);
                end
    end
    always @(posedge pclk) begin
        in_rgb[tpix] <= vdata;
        in_ctl[tpix] <= {vde, vvs, vhs};
        tpix <= tpix + 1;
    end

    // Receiver: sample every serial edge, lock to the clock lane, decode
    reg [9:0] sr [0:3];
    integer   bitn = 0, phase = -1, nsym = 0, clk_slips = 0;
    reg [23:0] rx_rgb [0:NPIX-1];
    reg [2:0]  rx_ctl [0:NPIX-1];
    integer    rx_t   [0:NPIX-1];
    always @(sclk) begin : rx
        integer l;
        reg [10:0] dec0, dec1, dec2;
        #0.5;
        for (l = 0; l < 3; l = l + 1) sr[l] = {tdat_p[l], sr[l][9:1]};
        sr[3] = {tclk_p, sr[3][9:1]};
        bitn = bitn + 1;
        if (phase < 0 && bitn > 20 && sr[3] == 10'b0000011111)
            phase = bitn % 10;
        if (phase >= 0 && bitn % 10 == phase && nsym < NPIX) begin
            dec0 = tmds_decode(sr[0]);
            dec1 = tmds_decode(sr[1]);
            dec2 = tmds_decode(sr[2]);
            rx_rgb[nsym] = {dec2[7:0], dec0[7:0], dec1[7:0]};    // {R, B, G}
            rx_ctl[nsym] = dec0[10] ? {1'b0, dec0[9], dec0[8]} : 3'b100;
            rx_t[nsym]   = tpix;
            if (sr[3] !== 10'b0000011111) clk_slips = clk_slips + 1;
            nsym = nsym + 1;
        end
    end

    initial begin : check_b
        integer s, t0, lat, cmp, i, berr, k;
        berr = 0;
        wait (tpix > HT * VT * FRAMES + 30);
        // Latency: start of the first active line, sent vs received. (The first
        // received symbols come from encoders still in reset: all zeros, which
        // decodes as data, so the first DE can't be trusted.)
        t0 = -1; k = 0;
        for (i = 1; i < NPIX && t0 < 0; i = i + 1)
            if (in_ctl[i][2] && !in_ctl[i-1][2]) begin k = k + 1; if (k == 1) t0 = i; end
        lat = -1; k = 0;
        s = 0;
        while (s < nsym && rx_ctl[s][2]) s = s + 1;      // skip the reset garbage
        for (s = s + 1; s < nsym && lat < 0; s = s + 1)
            if (rx_ctl[s][2] && !rx_ctl[s-1][2]) begin k = k + 1; if (k == 1) lat = rx_t[s] - t0; end
        cmp = 0;
        for (s = 0; s < nsym; s = s + 1) begin
            i = rx_t[s] - lat;
            if (i >= t0 && i < HT * VT * FRAMES) begin
                if (rx_ctl[s] !== in_ctl[i] || (in_ctl[i][2] && rx_rgb[s] !== in_rgb[i])) begin
                    berr = berr + 1;
                    if (berr < 8) $display("B: pixel %0d sent ctl=%b rgb=%h got ctl=%b rgb=%h",
                                           i, in_ctl[i], in_rgb[i], rx_ctl[s], rx_rgb[s]);
                end
                cmp = cmp + 1;
            end
        end
        $display("B) hdmi_tx: lane phase %0d, latency %0d pixel clocks, %0d pixel periods compared, errors %0d, clock-lane slips %0d",
                 phase, lat, cmp, berr, clk_slips);
        wait (a_done);
        if (cmp < HT * VT * (FRAMES - 1)) begin
            $display("B) ERROR: too few pixels compared");
            berr = berr + 1;
        end
        errors = errors + berr;
        if (errors == 0) $display("ALL PASSED");
        else             $display("FAILED (%0d errors)", errors);
        $finish;
    end
endmodule
