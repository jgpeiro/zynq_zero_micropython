`timescale 1ns / 1ps
//------------------------------------------------------------------------------
// xfft_model.v - Behavioural stand-in for the Xilinx FFT core (simulation only).
//
// Same AXI4-Stream ports as xfft v9.1 configured like the block design
// (run-time NFFT, FWD_INV, unscaled, natural order). It computes an exact DFT
// in floating point, so it checks the controller's protocol (config word, TLAST,
// back-pressure on both sides, output capture and sign extension), not the
// core's internal rounding. Upper padding bits of each output word are left 0
// to prove that xfft_ctrl sign-extends from OUT_W.
//------------------------------------------------------------------------------
module xfft_model #(
    parameter LOG2N_MAX = 10,
    parameter OUT_W     = 27
) (
    input  wire        aclk,
    input  wire        aresetn,
    input  wire [15:0] s_axis_config_tdata,
    input  wire        s_axis_config_tvalid,
    output reg         s_axis_config_tready,
    input  wire [31:0] s_axis_data_tdata,
    input  wire        s_axis_data_tvalid,
    output reg         s_axis_data_tready,
    input  wire        s_axis_data_tlast,
    output reg  [63:0] m_axis_data_tdata,
    output reg         m_axis_data_tvalid,
    input  wire        m_axis_data_tready,
    output reg         m_axis_data_tlast,
    output reg         event_tlast_unexpected,
    output reg         event_tlast_missing
);
    localparam NMAX = 1 << LOG2N_MAX;
    real xr [0:NMAX-1];
    real xi [0:NMAX-1];
    integer yr [0:NMAX-1];
    integer yi [0:NMAX-1];

    integer n, nfft, fwd, i, k, idx;
    real ar, ai, ang, sr, si, pi;

    function integer sext16(input [15:0] v);
        sext16 = v[15] ? (v - 65536) : v;
    endfunction

    initial begin
        pi = 3.14159265358979323846;
        s_axis_config_tready = 0;
        s_axis_data_tready = 0;
        m_axis_data_tvalid = 0;
        m_axis_data_tlast = 0;
        m_axis_data_tdata = 0;
        event_tlast_unexpected = 0;
        event_tlast_missing = 0;
        forever begin
            // ---- config
            @(posedge aclk);
            s_axis_config_tready <= 1;
            @(posedge aclk);
            while (!(s_axis_config_tvalid && s_axis_config_tready)) @(posedge aclk);
            nfft = s_axis_config_tdata[4:0];
            fwd  = s_axis_config_tdata[8];
            s_axis_config_tready <= 0;
            n = 1 << nfft;
            // ---- input with random back-pressure
            i = 0;
            while (i < n) begin
                s_axis_data_tready <= ($random & 3) != 0;
                @(posedge aclk);
                if (s_axis_data_tvalid && s_axis_data_tready) begin
                    xr[i] = sext16(s_axis_data_tdata[15:0]);
                    xi[i] = sext16(s_axis_data_tdata[31:16]);
                    if (s_axis_data_tlast != (i == n - 1)) begin
                        if (s_axis_data_tlast) event_tlast_unexpected = 1;
                        else                   event_tlast_missing = 1;
                    end
                    i = i + 1;
                end
            end
            s_axis_data_tready <= 0;
            // ---- DFT (unscaled)
            for (k = 0; k < n; k = k + 1) begin
                sr = 0.0; si = 0.0;
                for (i = 0; i < n; i = i + 1) begin
                    idx = (i * k) % n;
                    ang = 2.0 * pi * idx / n;
                    ar = $cos(ang);
                    ai = fwd ? -$sin(ang) : $sin(ang);
                    sr = sr + xr[i] * ar - xi[i] * ai;
                    si = si + xr[i] * ai + xi[i] * ar;
                end
                yr[k] = $rtoi(sr + (sr >= 0 ? 0.5 : -0.5));
                yi[k] = $rtoi(si + (si >= 0 ? 0.5 : -0.5));
            end
            repeat (20) @(posedge aclk);
            // ---- output with random gaps, honouring tready
            k = 0;
            while (k < n) begin
                if (!m_axis_data_tvalid || m_axis_data_tready) begin
                    if (($random & 3) != 0) begin
                        m_axis_data_tdata  <= {{(32-OUT_W){1'b0}}, yi[k][OUT_W-1:0],
                                               {(32-OUT_W){1'b0}}, yr[k][OUT_W-1:0]};
                        m_axis_data_tvalid <= 1;
                        m_axis_data_tlast  <= (k == n - 1);
                        k = k + 1;
                    end else begin
                        m_axis_data_tvalid <= 0;
                    end
                end
                @(posedge aclk);
            end
            while (m_axis_data_tvalid && !m_axis_data_tready) @(posedge aclk);
            m_axis_data_tvalid <= 0;
            m_axis_data_tlast  <= 0;
        end
    end
endmodule
