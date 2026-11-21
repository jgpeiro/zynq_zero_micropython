# ps7_config.tcl - PS7 (Zynq processing system) settings for the ZYNQ ZERO Rev B.
# Sourced by build.tcl and applied to the ps7 cell of the block design.
# Vivado generates ps7_init.tcl (clocks, MIO pin mux, DDR) from these settings;
# program.tcl runs it over JTAG before loading MicroPython.
#
# Board facts (from zynq_zero_pinouts.md):
#   PS_CLK            33.333 MHz (X2)
#   Bank 500 MIO0-15  3.3 V  (strap MIO7 = 0)   LED0 on MIO9
#   Bank 501 MIO16-53 1.8 V  (strap MIO8 = 1)   UART1 on MIO48 (TX) / MIO49 (RX)
#   Bank 502 DDR      1.5 V  DDR3 x16, one MT41J256M16 (512 MB)
#
# PS -> PL: M_AXI_GP0 (0x4000_0000 - 0x7FFF_FFFF) clocked by FCLK_CLK0 = 100 MHz.
# PL -> DDR: S_AXI_HP0 (64-bit), used by the HDMI framebuffer VDMA.
# The MicroPython port relies on: CPU 666.67 MHz, UART ref 100 MHz, DDR at 0x0.
# QSPI (MIO1-6) and SD0 (MIO40-45) are left off; enable them here when needed.

proc ps7_configure {ip} {
    set_property -dict [list \
        CONFIG.PCW_CRYSTAL_PERIPHERAL_FREQMHZ {33.333333} \
        CONFIG.PCW_APU_PERIPHERAL_FREQMHZ     {666.666666} \
        CONFIG.PCW_PRESET_BANK0_VOLTAGE       {LVCMOS 3.3V} \
        CONFIG.PCW_PRESET_BANK1_VOLTAGE       {LVCMOS 1.8V} \
        \
        CONFIG.PCW_UIPARAM_DDR_MEMORY_TYPE    {DDR 3} \
        CONFIG.PCW_UIPARAM_DDR_PARTNO         {MT41J256M16 RE-125} \
        CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH      {16 Bit} \
        \
        CONFIG.PCW_GPIO_MIO_GPIO_ENABLE       {1} \
        CONFIG.PCW_UART1_PERIPHERAL_ENABLE    {1} \
        CONFIG.PCW_UART1_UART1_IO             {MIO 48 .. 49} \
        CONFIG.PCW_UART_PERIPHERAL_FREQMHZ    {100} \
        \
        CONFIG.PCW_USE_M_AXI_GP0              {1} \
        CONFIG.PCW_EN_CLK0_PORT               {1} \
        CONFIG.PCW_EN_RST0_PORT               {1} \
        CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ   {100} \
        \
        CONFIG.PCW_USE_S_AXI_HP0              {1} \
        CONFIG.PCW_S_AXI_HP0_DATA_WIDTH       {64} \
        \
        CONFIG.PCW_QSPI_PERIPHERAL_ENABLE     {0} \
        CONFIG.PCW_SD0_PERIPHERAL_ENABLE      {0} \
        CONFIG.PCW_SD1_PERIPHERAL_ENABLE      {0} \
        CONFIG.PCW_UART0_PERIPHERAL_ENABLE    {0} \
        CONFIG.PCW_ENET0_PERIPHERAL_ENABLE    {0} \
        CONFIG.PCW_ENET1_PERIPHERAL_ENABLE    {0} \
        CONFIG.PCW_USB0_PERIPHERAL_ENABLE     {0} \
        CONFIG.PCW_USB1_PERIPHERAL_ENABLE     {0} \
        CONFIG.PCW_I2C0_PERIPHERAL_ENABLE     {0} \
        CONFIG.PCW_I2C1_PERIPHERAL_ENABLE     {0} \
    ] $ip
}
