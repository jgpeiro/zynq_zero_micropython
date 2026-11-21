"""Run a MicroPython script in QEMU (paste mode) and dump the HDMI framebuffer to PNG.

usage: qemu_fb.py firmware.elf script.py out.png [fb_index|lv] [extra_wait_s]
fb_index "lv": the framebuffer LVGL presented last (_lvhdmi.frames()).
QEMU_EXTRA="-icount shift=1" adds QEMU options: -icount ties guest time to
instructions (shift=1: 2 ns each, about a 666 MHz Cortex-A9), so FPS and
timings come out close to the real board, minus cache and DDR effects.
"""
import os, pty, select, socket, subprocess, sys, time
from PIL import Image

elf, script, png = sys.argv[1:4]
fb_index = sys.argv[4] if len(sys.argv) > 4 else "0"
fb_expr = "(_lvhdmi.frames() - 1) % 2" if fb_index == "lv" else str(int(fb_index))
extra = float(sys.argv[5]) if len(sys.argv) > 5 else 0
mon = "/tmp/qemu_mon_%d.sock" % os.getpid()
if os.path.exists(mon):
    os.unlink(mon)
master, slave = pty.openpty()
p = subprocess.Popen(["qemu-system-arm", "-M", "xilinx-zynq-a9", "-m", "512M", "-nographic",
                      "-monitor", f"unix:{mon},server,nowait", "-serial", "null",
                      "-serial", os.ttyname(slave), "-no-reboot", "-kernel", elf]
                     + os.environ.get("QEMU_EXTRA", "").split(),
                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = bytearray()

def pump(t, until=None):
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([master], [], [], 0.05)
        if r:
            out.extend(os.read(master, 65536))
            if until and out.endswith(until):
                return True
    return False

pump(2)
os.write(master, b"\x05")                      # paste mode
pump(0.3)
src = open(script).read().replace("\n", "\r")
for i in range(0, len(src), 256):
    os.write(master, src[i:i + 256].encode())
    pump(0.02)
os.write(master, b"\x04")
ok = pump(600, until=b">>> ")
pump(extra)
os.write(master, ("import _hdmi\r" + ("import _lvhdmi\r" if fb_index == "lv" else "")
                  + "print('FBADDR', hex(_hdmi.address(%s)))\r" % fb_expr).encode())
pump(2)
text = out.decode(errors="replace").replace("\r", "")
addr = int(text.rsplit("FBADDR ", 1)[1].split()[0], 16)
s = socket.socket(socket.AF_UNIX)
s.connect(mon)
time.sleep(0.2)
s.recv(4096)
raw = "/tmp/fb_dump.raw"
s.sendall(f"pmemsave {addr} {1280 * 720 * 2} \"{raw}\"\n".encode())
time.sleep(2)
s.sendall(b"quit\n")                            # clean exit: lets -plugin reports print
try:
    qemu_out = p.communicate(timeout=60)[0].decode(errors="replace")
except subprocess.TimeoutExpired:
    p.kill()
    qemu_out = ""
if os.environ.get("QEMU_OUT"):
    open(os.environ["QEMU_OUT"], "w").write(qemu_out)
data = open(raw, "rb").read()
img = Image.new("RGB", (1280, 720))
px = []
for i in range(0, len(data), 2):
    v = data[i] | (data[i + 1] << 8)
    px.append((((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31))
img.putdata(px)
img.save(png)
print(text[-1500:])
print("framebuffer at", hex(addr), "->", png, "finished" if ok else "TIMEOUT")
