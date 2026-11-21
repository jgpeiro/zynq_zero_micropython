## zynq_zero_timing.xdc - clock-domain constraints for the block design clocks.
## Implementation only (USED_IN_SYNTHESIS false): the clocks below exist only
## once the block design IP is linked in.
##
## The HDMI clocks come from clk_wiz_hdmi, an MMCM fed by FCLK_CLK0 (clk_fpga_0),
## so Vivado treats them as related and would time every crossing as synchronous.
## The real crossings are the vid_out async FIFO (gray-coded pointers) and the
## status bits into axi_gpio_video, so the domains are asynchronous.
set hdmi_clks [get_clocks -of_objects [get_pins -hierarchical -filter {NAME =~ *clk_wiz_hdmi/clk_out*}]]
set_clock_groups -asynchronous -group [get_clocks clk_fpga_0] -group $hdmi_clks
