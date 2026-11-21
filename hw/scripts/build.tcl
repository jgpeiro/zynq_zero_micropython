# build.tcl - Vivado block design for the MicroPython port.
#
#   ps7 M_AXI_GP0 --AXI interconnect--+--> axi_gpio_0   @ 0x4120_0000  LED1..4 out, KEY1 in
#                                     +--> myfft_0      @ 0x43C0_0000  own radix-2 FFT (RTL)
#                                     +--> xfft_ctrl_0  @ 0x43C1_0000  front end for the Xilinx FFT
#                                     |        | AXI4-Stream config / data in / data out
#                                     |        +--> xfft_0 (Xilinx FFT LogiCORE)
#                                     +--> axi_vdma_0   @ 0x4300_0000  framebuffer DMA control
#                                     +--> axi_gpio_video @ 0x4121_0000  video status (in)
#
#   HDMI 720p60: DDR --HP0--> axi_vdma_0 (RGB565) --> rgb565_to_888 (subset converter)
#                --> v_axi4s_vid_out_0 <-- v_tc_0 (720p timing) --> hdmi_tx_0 (own RTL:
#                TMDS encode, OSERDESE2 10:1) --> TMDS_33 pins; clk_wiz_hdmi makes
#                74.25 / 371.25 MHz from FCLK_CLK0.
#
# Outputs in hw/build/: system.bit, ps7_init.tcl (+ .html), system.xsa, reports.
# Usage: vivado -mode batch -source hw/scripts/build.tcl

set script_dir [file dirname [file normalize [info script]]]
set hw         [file normalize "$script_dir/.."]
set out        "$hw/build"
set proj_dir   "$out/proj"
set part       "xc7z010clg400-1"
set jobs       [expr {[info exists ::env(JOBS)] ? $::env(JOBS) : 4}]

# Fixed addresses: the MicroPython port hard-codes them (zynq_regs.h, fft.py)
set addr(axi_gpio_0)  0x41200000
set addr(myfft_0)     0x43C00000
set addr(xfft_ctrl_0) 0x43C10000
set addr(axi_vdma_0)  0x43000000
set addr(axi_gpio_video) 0x41210000

source $script_dir/ps7_config.tcl

file mkdir $out
file delete -force $proj_dir
create_project zynq_mp $proj_dir -part $part
set_property target_language Verilog [current_project]

# RTL used as block design module references
add_files -norecurse [list \
    $hw/rtl/axil_slave.v $hw/rtl/tdp_ram.v $hw/rtl/twiddle_rom.v \
    $hw/rtl/myfft_axil.v $hw/rtl/xfft_ctrl.v \
    $hw/rtl/tmds_encoder.v $hw/rtl/hdmi_tx.v ]
update_compile_order -fileset sources_1

# Latest installed version of a Xilinx IP, e.g. xilinx.com:ip:xfft:9.1
proc ip_vlnv {name} {
    set defs [lsort -dictionary [get_ipdefs -all "xilinx.com:ip:${name}:*"]]
    if {[llength $defs] == 0} { error "IP $name not found in the Vivado IP catalog" }
    return [lindex $defs end]
}

# A block design pin that must exist (clear error if this Vivado names it differently)
proc pin {path} {
    set p [get_bd_pins -quiet $path]
    if {$p eq ""} { error "block design pin $path not found" }
    return $p
}
# Connect a source pin to sinks that are not connected yet
proc wire {src args} {
    foreach dst $args {
        set d [pin $dst]
        if {[llength [get_bd_nets -quiet -of_objects $d]] == 0} {
            connect_bd_net [pin $src] $d
        }
    }
}

# Connect an AXI4-Lite slave to M_AXI_GP0 (reuses the interconnect after the first)
proc connect_gp0 {slave_intf} {
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list \
        Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
        Master {/ps7/M_AXI_GP0} Slave "/$slave_intf" \
        ddr_seg {Auto} intc_ip {Auto} master_apm {0} \
    ] [get_bd_intf_pins $slave_intf]
}

# ---- Block design ------------------------------------------------------------
create_bd_design system

# Zynq PS: DDR and FIXED_IO (MIO, PS_CLK, PS_PORB, PS_SRSTB) become top-level ports
create_bd_cell -type ip -vlnv [ip_vlnv processing_system7] ps7
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "0" Master "Disable" Slave "Disable"} \
    [get_bd_cells ps7]
ps7_configure [get_bd_cells ps7]

# AXI GPIO: channel 1 = LEDs (outputs), channel 2 = KEY1 (input)
create_bd_cell -type ip -vlnv [ip_vlnv axi_gpio] axi_gpio_0
set_property -dict [list \
    CONFIG.C_GPIO_WIDTH   {4} \
    CONFIG.C_ALL_OUTPUTS  {1} \
    CONFIG.C_DOUT_DEFAULT {0x00000000} \
    CONFIG.C_IS_DUAL      {1} \
    CONFIG.C_GPIO2_WIDTH  {1} \
    CONFIG.C_ALL_INPUTS_2 {1} \
] [get_bd_cells axi_gpio_0]
connect_gp0 axi_gpio_0/S_AXI

# External GPIO ports -> wrapper ports leds_tri_o[3:0] and keys_tri_i[0:0]
create_bd_intf_port -mode Master -vlnv xilinx.com:interface:gpio_rtl:1.0 leds
create_bd_intf_port -mode Master -vlnv xilinx.com:interface:gpio_rtl:1.0 keys
connect_bd_intf_net [get_bd_intf_pins axi_gpio_0/GPIO]  [get_bd_intf_ports leds]
connect_bd_intf_net [get_bd_intf_pins axi_gpio_0/GPIO2] [get_bd_intf_ports keys]

# ---- FFT 1: own radix-2 core (hw/rtl/myfft_axil.v) ------------------------------
create_bd_cell -type module -reference myfft_axil myfft_0
connect_gp0 myfft_0/s_axi

# ---- FFT 2: Xilinx FFT LogiCORE + AXI4-Lite front end (hw/rtl/xfft_ctrl.v) -------
create_bd_cell -type ip -vlnv [ip_vlnv xfft] xfft_0
set_property -dict [list \
    CONFIG.transform_length                       {1024} \
    CONFIG.implementation_options                 {radix_2_burst_io} \
    CONFIG.run_time_configurable_transform_length {true} \
    CONFIG.target_clock_frequency                 {100} \
    CONFIG.input_width                            {16} \
    CONFIG.phase_factor_width                     {16} \
    CONFIG.scaling_options                        {unscaled} \
    CONFIG.output_ordering                        {natural_order} \
    CONFIG.throttle_scheme                        {nonrealtime} \
    CONFIG.aresetn                                {true} \
] [get_bd_cells xfft_0]

# Stream widths the front end was written for: config 16 bits, data out 64 bits
set cfg_bytes [get_property CONFIG.TDATA_NUM_BYTES [get_bd_intf_pins xfft_0/S_AXIS_CONFIG]]
set out_bytes [get_property CONFIG.TDATA_NUM_BYTES [get_bd_intf_pins xfft_0/M_AXIS_DATA]]
puts "INFO: xfft_0 config tdata $cfg_bytes bytes, output tdata $out_bytes bytes"
if {$cfg_bytes != 2 || $out_bytes != 8} {
    error "xfft_0 stream widths ($cfg_bytes, $out_bytes bytes) don't match xfft_ctrl.v (2, 8)"
}

create_bd_cell -type module -reference xfft_ctrl xfft_ctrl_0
# Output word width per component (27 for 1024 points, 16-bit input, unscaled)
if {![catch {get_property CONFIG.output_width [get_bd_cells xfft_0]} out_w] && $out_w ne ""} {
    puts "INFO: xfft_0 output width $out_w bits"
    set_property CONFIG.OUT_W $out_w [get_bd_cells xfft_ctrl_0]
}
connect_bd_intf_net [get_bd_intf_pins xfft_ctrl_0/m_axis_config] [get_bd_intf_pins xfft_0/S_AXIS_CONFIG]
connect_bd_intf_net [get_bd_intf_pins xfft_ctrl_0/m_axis_data]   [get_bd_intf_pins xfft_0/S_AXIS_DATA]
connect_bd_intf_net [get_bd_intf_pins xfft_0/M_AXIS_DATA]        [get_bd_intf_pins xfft_ctrl_0/s_axis_data]
connect_gp0 xfft_ctrl_0/s_axi

# xfft_0 runs on the same clock and reset as its front end
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins xfft_0/aclk]
set rst_src [get_bd_pins -of_objects [get_bd_nets -of_objects [get_bd_pins xfft_ctrl_0/aresetn]] -filter {DIR == O}]
connect_bd_net $rst_src [get_bd_pins xfft_0/aresetn]

# ---- HDMI output, 1280x720 @ 60 Hz ------------------------------------------------------
# Clocks: 74.25 MHz pixel and 371.25 MHz (5x) serial clock from FCLK_CLK0 (100 MHz):
# VCO = 100 / 5 * 37.125 = 742.5 MHz, /10 and /2.
create_bd_cell -type ip -vlnv [ip_vlnv clk_wiz] clk_wiz_hdmi
set_property -dict [list \
    CONFIG.PRIM_IN_FREQ               {100.000} \
    CONFIG.PRIM_SOURCE                {No_buffer} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {74.25} \
    CONFIG.CLKOUT2_USED               {true} \
    CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {371.25} \
    CONFIG.USE_RESET                  {false} \
    CONFIG.MMCM_DIVCLK_DIVIDE         {5} \
    CONFIG.MMCM_CLKFBOUT_MULT_F       {37.125} \
    CONFIG.MMCM_CLKOUT0_DIVIDE_F      {10.000} \
    CONFIG.MMCM_CLKOUT1_DIVIDE        {2} \
] [get_bd_cells clk_wiz_hdmi]
wire ps7/FCLK_CLK0 clk_wiz_hdmi/clk_in1

# Reset for the pixel clock domain, released once the MMCM is locked
create_bd_cell -type ip -vlnv [ip_vlnv proc_sys_reset] rst_pixel
wire clk_wiz_hdmi/clk_out1 rst_pixel/slowest_sync_clk
connect_bd_net [pin ps7/FCLK_RESET0_N] [pin rst_pixel/ext_reset_in]
wire clk_wiz_hdmi/locked rst_pixel/dcm_locked

# Framebuffer reader: DDR -> HP0 -> AXI4-Stream, 16-bit RGB565 pixels, 2 frame stores
create_bd_cell -type ip -vlnv [ip_vlnv axi_vdma] axi_vdma_0
set_property -dict [list \
    CONFIG.c_include_s2mm             {0} \
    CONFIG.c_num_fstores              {2} \
    CONFIG.c_m_axis_mm2s_tdata_width  {16} \
    CONFIG.c_mm2s_linebuffer_depth    {2048} \
    CONFIG.c_mm2s_max_burst_length    {32} \
] [get_bd_cells axi_vdma_0]
connect_gp0 axi_vdma_0/S_AXI_LITE
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/axi_vdma_0/M_AXI_MM2S} Slave {/ps7/S_AXI_HP0} \
    ddr_seg {Auto} intc_ip {Auto} master_apm {0} \
] [get_bd_intf_pins ps7/S_AXI_HP0]
wire ps7/FCLK_CLK0 axi_vdma_0/m_axis_mm2s_aclk

# The 100 MHz domain's reset (made by the GP0 automation)
set rst100 [get_bd_pins -of_objects [get_bd_nets -of_objects [pin myfft_0/aresetn]] -filter {DIR == O}]

# RGB565 -> RGB888 in Xilinx AXI4-Stream video order {R, B, G}, bits replicated
create_bd_cell -type ip -vlnv [ip_vlnv axis_subset_converter] rgb565_to_888
connect_bd_intf_net [get_bd_intf_pins axi_vdma_0/M_AXIS_MM2S] [get_bd_intf_pins rgb565_to_888/S_AXIS]
# Both sides set explicitly: the VDMA's widths only propagate at validation,
# and the remap strings are checked against them right away.
set_property -dict [list \
    CONFIG.S_TDATA_NUM_BYTES {2} \
    CONFIG.S_HAS_TKEEP       {1} \
    CONFIG.S_HAS_TLAST       {1} \
    CONFIG.S_TUSER_WIDTH     {1} \
    CONFIG.M_TDATA_NUM_BYTES {3} \
    CONFIG.M_HAS_TKEEP       {1} \
    CONFIG.M_HAS_TLAST       {1} \
    CONFIG.M_TUSER_WIDTH     {1} \
    CONFIG.TDATA_REMAP       {tdata[15:11],tdata[15:13],tdata[4:0],tdata[4:2],tdata[10:5],tdata[10:9]} \
    CONFIG.TKEEP_REMAP       {tkeep[1:0],tkeep[1]} \
    CONFIG.TUSER_REMAP       {tuser[0:0]} \
    CONFIG.TLAST_REMAP       {tlast[0]} \
] [get_bd_cells rgb565_to_888]
wire ps7/FCLK_CLK0 rgb565_to_888/aclk
connect_bd_net $rst100 [pin rgb565_to_888/aresetn]

# Stream -> timed parallel video (async FIFO 100 MHz -> 74.25 MHz), timing from the VTC
create_bd_cell -type ip -vlnv [ip_vlnv v_axi4s_vid_out] v_axi4s_vid_out_0
set_property -dict [list \
    CONFIG.C_ADDR_WIDTH       {12} \
    CONFIG.C_HAS_ASYNC_CLK    {1} \
    CONFIG.C_VTG_MASTER_SLAVE {1} \
] [get_bd_cells v_axi4s_vid_out_0]
connect_bd_intf_net [get_bd_intf_pins rgb565_to_888/M_AXIS] [get_bd_intf_pins v_axi4s_vid_out_0/video_in]
wire ps7/FCLK_CLK0 v_axi4s_vid_out_0/aclk
connect_bd_net $rst100 [pin v_axi4s_vid_out_0/aresetn]
wire clk_wiz_hdmi/clk_out1 v_axi4s_vid_out_0/vid_io_out_clk
if {[get_bd_pins -quiet v_axi4s_vid_out_0/vid_io_out_reset] ne ""} {
    wire rst_pixel/peripheral_reset v_axi4s_vid_out_0/vid_io_out_reset
}

create_bd_cell -type ip -vlnv [ip_vlnv v_tc] v_tc_0
set_property -dict [list \
    CONFIG.HAS_AXI4_LITE    {false} \
    CONFIG.VIDEO_MODE       {720p} \
    CONFIG.enable_detection {false} \
] [get_bd_cells v_tc_0]
connect_bd_intf_net [get_bd_intf_pins v_tc_0/vtiming_out] [get_bd_intf_pins v_axi4s_vid_out_0/vtiming_in]
wire v_axi4s_vid_out_0/vtg_ce v_tc_0/gen_clken
wire clk_wiz_hdmi/clk_out1 v_tc_0/clk
wire rst_pixel/peripheral_aresetn v_tc_0/resetn

# Own RTL: TMDS encoding and serialisation -> pins
create_bd_cell -type module -reference hdmi_tx hdmi_tx_0
connect_bd_intf_net [get_bd_intf_pins v_axi4s_vid_out_0/vid_io_out] [get_bd_intf_pins hdmi_tx_0/vid_in]
wire clk_wiz_hdmi/clk_out1 hdmi_tx_0/pix_clk
wire clk_wiz_hdmi/clk_out2 hdmi_tx_0/ser_clk
wire rst_pixel/peripheral_reset hdmi_tx_0/rst
create_bd_port -dir O hdmi_clk_p
create_bd_port -dir O hdmi_clk_n
create_bd_port -dir O -from 2 -to 0 hdmi_d_p
create_bd_port -dir O -from 2 -to 0 hdmi_d_n
connect_bd_net [pin hdmi_tx_0/tmds_clk_p]  [get_bd_ports hdmi_clk_p]
connect_bd_net [pin hdmi_tx_0/tmds_clk_n]  [get_bd_ports hdmi_clk_n]
connect_bd_net [pin hdmi_tx_0/tmds_data_p] [get_bd_ports hdmi_d_p]
connect_bd_net [pin hdmi_tx_0/tmds_data_n] [get_bd_ports hdmi_d_n]

# Video status for software: bit 0 MMCM locked, bit 1 vid_out locked, bit 2 underflow
create_bd_cell -type ip -vlnv [ip_vlnv xlconcat] video_status
set_property CONFIG.NUM_PORTS {3} [get_bd_cells video_status]
wire clk_wiz_hdmi/locked video_status/In0
wire v_axi4s_vid_out_0/locked video_status/In1
wire v_axi4s_vid_out_0/underflow video_status/In2
create_bd_cell -type ip -vlnv [ip_vlnv axi_gpio] axi_gpio_video
set_property -dict [list CONFIG.C_GPIO_WIDTH {3} CONFIG.C_ALL_INPUTS {1}] [get_bd_cells axi_gpio_video]
wire video_status/dout axi_gpio_video/gpio_io_i
connect_gp0 axi_gpio_video/S_AXI

# ---- Addresses ---------------------------------------------------------------------
assign_bd_address
foreach cell [array names addr] {
    set seg [get_bd_addr_segs -of_objects [get_bd_addr_spaces ps7/Data] -filter "NAME =~ *${cell}*"]
    if {[llength $seg] != 1} { error "address segment for $cell not found (got '$seg')" }
    set_property range  64K          $seg
    set_property offset $addr($cell) $seg
    puts "INFO: $cell at [get_property offset $seg], range [get_property range $seg]"
}

validate_bd_design
save_bd_design

# ---- Wrapper, constraints ------------------------------------------------------
set bd_file [get_files system.bd]
generate_target all $bd_file
set wrapper [make_wrapper -files $bd_file -top]
add_files -norecurse $wrapper
set_property top system_wrapper [current_fileset]
add_files -fileset constrs_1 -norecurse $hw/constraints/zynq_zero.xdc
# Clock-domain constraints that name block design clocks: implementation only
add_files -fileset constrs_1 -norecurse $hw/constraints/zynq_zero_timing.xdc
set_property USED_IN_SYNTHESIS false [get_files zynq_zero_timing.xdc]

# ---- ps7_init.tcl ----------------------------------------------------------------
proc find_file {dir name} {
    foreach f [glob -nocomplain -directory $dir *] {
        if {[file isdirectory $f]} {
            set hit [find_file $f $name]
            if {$hit ne ""} { return $hit }
        } elseif {[file tail $f] eq $name} {
            return $f
        }
    }
    return ""
}
foreach name {ps7_init.tcl ps7_init.html ps7_init.c ps7_init.h} {
    set f [find_file $proj_dir $name]
    if {$f eq ""} {
        if {$name eq "ps7_init.tcl"} { error "ps7_init.tcl was not generated under $proj_dir" }
        continue
    }
    file copy -force $f $out/$name
}
puts "INFO: PS init script written to $out/ps7_init.tcl"

# ---- Synthesis, implementation, bitstream ---------------------------------------
launch_runs synth_1 -jobs $jobs
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Synthesis failed, see $proj_dir/zynq_mp.runs/synth_1/runme.log" }

launch_runs impl_1 -to_step write_bitstream -jobs $jobs
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "Implementation failed, see $proj_dir/zynq_mp.runs/impl_1/runme.log" }

open_run impl_1
report_utilization    -file $out/utilization.rpt
report_timing_summary -file $out/timing_summary.rpt
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
puts "INFO: Worst negative slack (setup) = $wns ns"
if {$wns ne "" && $wns < 0} {
    error "Timing NOT met (WNS = $wns ns). See $out/timing_summary.rpt"
}

set bit [glob $proj_dir/zynq_mp.runs/impl_1/*.bit]
file copy -force $bit $out/system.bit
puts "INFO: Bitstream written to $out/system.bit"

# Hardware handoff for Vitis/PetaLinux later (not needed by this flow)
if {[catch {write_hw_platform -fixed -include_bit -force -file $out/system.xsa} msg]} {
    puts "WARNING: write_hw_platform failed: $msg"
}
