## ZYNQ ZERO (Rev B) - xc7z010clg400 - PL pins of the MicroPython design
## Pin info from ZYNQ_ZERO_SCH_REVB (U5E bank 34). Bank 34 is 3.3 V -> LVCMOS33.
## PS pins (MIO, DDR, PS_CLK, ...) are placed by the ps7 IP, not here.

## AXI GPIO channel 1 (outputs) -> user LEDs, active-high (4.7k + LED to GND)
## leds_tri_o[0..3] = LED1 W13, LED2 V12, LED3 U12, LED4 T12
set_property -dict { PACKAGE_PIN W13  IOSTANDARD LVCMOS33 } [get_ports {leds_tri_o[0]}]
set_property -dict { PACKAGE_PIN V12  IOSTANDARD LVCMOS33 } [get_ports {leds_tri_o[1]}]
set_property -dict { PACKAGE_PIN U12  IOSTANDARD LVCMOS33 } [get_ports {leds_tri_o[2]}]
set_property -dict { PACKAGE_PIN T12  IOSTANDARD LVCMOS33 } [get_ports {leds_tri_o[3]}]

## AXI GPIO channel 2 (input) <- KEY1 Y16 (R37 4.7k pull-up, reads 0 when pressed)
set_property -dict { PACKAGE_PIN Y16  IOSTANDARD LVCMOS33 } [get_ports {keys_tri_i[0]}]

## Slow, asynchronous I/O: no timing requirement
set_false_path -to   [get_ports {leds_tri_o[*]}]
set_false_path -from [get_ports {keys_tri_i[*]}]

## HDMI out (J1), bank 35 at 3.3 V -> TMDS_33, driven by hdmi_tx (OSERDESE2 + OBUFDS)
## D0 = blue + sync, D1 = green, D2 = red. The DDC (U15) isn't fitted: no EDID.
set_property -dict { PACKAGE_PIN H16  IOSTANDARD TMDS_33 } [get_ports hdmi_clk_p]
set_property -dict { PACKAGE_PIN H17  IOSTANDARD TMDS_33 } [get_ports hdmi_clk_n]
set_property -dict { PACKAGE_PIN D19  IOSTANDARD TMDS_33 } [get_ports {hdmi_d_p[0]}]
set_property -dict { PACKAGE_PIN D20  IOSTANDARD TMDS_33 } [get_ports {hdmi_d_n[0]}]
set_property -dict { PACKAGE_PIN C20  IOSTANDARD TMDS_33 } [get_ports {hdmi_d_p[1]}]
set_property -dict { PACKAGE_PIN B20  IOSTANDARD TMDS_33 } [get_ports {hdmi_d_n[1]}]
set_property -dict { PACKAGE_PIN B19  IOSTANDARD TMDS_33 } [get_ports {hdmi_d_p[2]}]
set_property -dict { PACKAGE_PIN A20  IOSTANDARD TMDS_33 } [get_ports {hdmi_d_n[2]}]
