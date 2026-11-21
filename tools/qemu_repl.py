"""Drive the MicroPython REPL in qemu-system-arm (xilinx-zynq-a9) over a pty."""
import os, pty, subprocess, sys, time, select

elf = sys.argv[1]
script = sys.argv[2]
master, slave = pty.openpty()
p = subprocess.Popen(["qemu-system-arm", "-M", "xilinx-zynq-a9", "-m", "512M", "-nographic",
                      "-monitor", "none", "-serial", "null", "-serial", f"/dev/{os.ttyname(slave).split('/dev/')[1]}",
                      "-no-reboot", "-kernel", elf], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = bytearray()
def pump(t):
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.05)
        if r:
            out.extend(os.read(master, 4096))
pump(3)
for line in open(script).read().split("\n"):
    if line.startswith("#SLEEP "):
        pump(float(line.split()[1])); continue
    if line == "#CTRLC":
        os.write(master, b"\x03"); pump(1); continue
    if line == "#CTRLD":
        os.write(master, b"\x04"); pump(2); continue
    if line == "#CTRLE":
        os.write(master, b"\x05"); pump(0.5); continue
    os.write(master, line.encode() + b"\r")
    pump(0.6)
pump(1)
p.kill()
sys.stdout.write(out.decode(errors="replace").replace("\r", ""))
