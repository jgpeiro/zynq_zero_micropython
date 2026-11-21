# program.tcl - Load PL bitstream, initialise the PS and run MicroPython on CPU0
# over JTAG (xsdb). Everything is volatile: lost on power-off.
# Usage: loader -exec rdi_xsdb scripts/program.tcl <system.bit> <ps7_init.tcl> <firmware.elf>

set bit      [file normalize [lindex $argv 0]]
set ps7_init [file normalize [lindex $argv 1]]
set elf      [file normalize [lindex $argv 2]]

# Select the first target whose name matches $pattern, polling up to ~10 s
# (hw_server needs a moment to scan the cable, and again after a reset).
proc select_target {pattern} {
    for {set i 0} {$i < 20} {incr i} {
        if {![catch {targets -set -nocase -filter "name =~ \"$pattern\""}]} { return }
        after 500
    }
    puts "ERROR: no JTAG target matching '$pattern'. Targets seen:\n[targets]"
    exit 1
}

connect      ;# starts a local hw_server

# ---- Reset the PS ------------------------------------------------------------
select_target "APU*"
rst -system
after 1500

# ---- PL: bitstream (AXI GPIO -> LED1..LED4, KEY1) ---------------------------
select_target "xc7z010*"
puts "Programming PL: $bit"
fpga -file $bit

# ---- PS: clocks, MIO, DDR, then enable PS-PL level shifters -----------------
select_target "APU*"
puts "Initialising PS: $ps7_init"
source $ps7_init
ps7_init
ps7_post_config

# ---- MicroPython on CPU0 --------------------------------------------------------
select_target "*Cortex-A9*#0"
catch {stop}
puts "Downloading: $elf"
dow $elf
con

puts "Done - MicroPython REPL on UART1 (CH340), 115200 8N1."
disconnect
exit 0
