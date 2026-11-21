# HDMI 720p demo: draws a test screen with framebuf primitives, then animates.
# Run with:  mpremote connect <port> run examples/hdmi_demo.py
# Without the HDMI bitstream it still draws (into memory), e.g. in QEMU.
import array
import math
import time

import framebuf
import hdmi
from hdmi import rgb, text, text_width, WIDTH, HEIGHT

BG_TOP = (8, 16, 48)
BG_BOTTOM = (0, 0, 0)
PANEL_BG = rgb(16, 24, 56)
ACCENT = rgb(255, 170, 0)


def background(fb):
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        fb.hline(0, y, WIDTH, rgb(*[int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)]))


def panel(fb, x, y, w, h, title):
    fb.fill_rect(x, y, w, h, PANEL_BG)
    fb.rect(x, y, w, h, ACCENT)
    fb.fill_rect(x, y, w, 26, rgb(40, 56, 110))
    text(fb, title, x + 10, y + 5, hdmi.WHITE, scale=2)
    return x + 10, y + 36, w - 20, h - 46      # drawing area inside the panel


def colour_bars(fb, x, y, w, h):
    bars = (rgb(191, 191, 191), rgb(191, 191, 0), rgb(0, 191, 191), rgb(0, 191, 0),
            rgb(191, 0, 191), rgb(191, 0, 0), rgb(0, 0, 191))
    bw = w // len(bars)
    bh = h * 55 // 100
    for i, c in enumerate(bars):
        fb.fill_rect(x + i * bw, y, bw, bh, c)
    # R, G, B and grey ramps, one vline per column
    rh = (h - bh - 8) // 4
    for i in range(w):
        v = i * 255 // (w - 1)
        for k, c in enumerate((rgb(v, 0, 0), rgb(0, v, 0), rgb(0, 0, v), rgb(v, v, v))):
            fb.vline(x + i, y + bh + 8 + k * rh, rh, c)


def shapes(fb, x, y, w, h):
    # nested rectangles
    for i in range(6):
        c = rgb(255 - i * 40, 80 + i * 30, 60 + i * 35)
        if i % 2:
            fb.rect(x + i * 10, y + i * 10, 140 - i * 20, h - i * 20, c)
        else:
            fb.fill_rect(x + i * 10, y + i * 10, 140 - i * 20, h - i * 20, c)
    # ellipses: filled, then outlines
    cx, cy = x + 250, y + h // 2
    fb.ellipse(cx, cy, 80, h // 2 - 4, rgb(0, 120, 255), True)
    for r in range(10, 80, 14):
        fb.ellipse(cx, cy, r, r * (h // 2 - 4) // 80, hdmi.WHITE)
    # 5-point star with poly()
    sx, sy, ro, ri = x + 405, y + h // 2, h // 2 - 4, (h // 2 - 4) * 2 // 5
    pts = array.array("h")
    for k in range(10):
        r = ro if k % 2 == 0 else ri
        a = -math.pi / 2 + k * math.pi / 5
        pts.append(int(r * math.cos(a)))
        pts.append(int(r * math.sin(a)))
    fb.poly(sx, sy, pts, hdmi.YELLOW, True)
    fb.poly(sx, sy, pts, ACCENT)
    # line fan
    fx, fy = x + w - 10, y + h - 2
    for k in range(19):
        a = math.pi + k * (math.pi / 2) / 18
        fb.line(fx, fy, fx + int(80 * math.cos(a)), fy + int(80 * math.sin(a)),
                rgb(80 + k * 9, 255 - k * 10, 120))


def plot(fb, x, y, w, h):
    mid = y + h // 2
    for gx in range(x, x + w + 1, w // 8):
        fb.vline(gx, y, h, hdmi.DARK_GREY)
    for gy in range(y, y + h + 1, h // 4):
        fb.hline(x, gy, w, hdmi.DARK_GREY)
    fb.hline(x, mid, w, hdmi.GREY)
    for f, c in ((math.sin, hdmi.CYAN), (math.cos, hdmi.MAGENTA),
                 (lambda t: math.sin(3 * t) * math.exp(-t / 6), hdmi.YELLOW)):
        px = py = None
        for i in range(w):
            t = i * 4 * math.pi / w
            yy = mid - int(f(t) * (h // 2 - 4))
            if px is not None:
                fb.line(x + px, py, x + i, yy, c)
            px, py = i, yy
    fb.text("sin", x + 6, y + 4, hdmi.CYAN)
    fb.text("cos", x + 40, y + 4, hdmi.MAGENTA)
    fb.text("damped sin(3t)", x + 74, y + 4, hdmi.YELLOW)


@micropython.viper
def _mandel(buf, stride: int, x0: int, y0: int, w: int, h: int,
            cr0: int, ci0: int, step: int, palette, max_it: int):
    # Fixed point, 12 fractional bits; writes RGB565 straight into the framebuffer
    fbp = ptr16(buf)
    pal = ptr16(palette)
    for py in range(h):
        ci = ci0 + py * step
        row = (y0 + py) * stride + x0
        for px in range(w):
            cr = cr0 + px * step
            zr = 0
            zi = 0
            it = 0
            while it < max_it:
                zr2 = (zr * zr) >> 12
                zi2 = (zi * zi) >> 12
                if zr2 + zi2 > 16384:          # |z|^2 > 4
                    break
                zi = ((zr * zi) >> 11) + ci
                zr = zr2 - zi2 + cr
                it += 1
            fbp[row + px] = pal[it]


def mandelbrot(disp, x, y, w, h, max_it=64):
    # navy -> blue -> white -> orange by escape time, black inside the set
    stops = ((10, 16, 60), (30, 90, 230), (230, 240, 255), (255, 160, 0), (120, 30, 0))
    palette = array.array("H", [0] * (max_it + 1))
    for i in range(max_it):
        t = math.sqrt(i / max_it) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        f = t - k
        palette[i] = rgb(*[int(a + (b - a) * f) for a, b in zip(stops[k], stops[k + 1])])
    palette[max_it] = hdmi.BLACK
    # whole set: imaginary axis -1.0 .. 1.0, centred on re = -0.65
    step = int(2.0 / h * 4096)
    cr0 = int(-0.65 * 4096) - (step * w) // 2
    ci0 = -(step * h) // 2
    _mandel(disp.buffer(), WIDTH, x, y, w, h, cr0, ci0, step, palette, max_it)


def test_screen(disp):
    fb = disp.fb
    t0 = time.ticks_ms()
    background(fb)
    title = "MicroPython on ZYNQ ZERO"
    text(fb, title, (WIDTH - text_width(title, 5)) // 2, 24, hdmi.WHITE, scale=5)
    sub = "1280x720 @ 60 Hz  |  framebuf RGB565  |  AXI VDMA + TMDS in Verilog"
    text(fb, sub, (WIDTH - text_width(sub, 2)) // 2, 82, ACCENT, scale=2)

    colour_bars(fb, *panel(fb, 30, 120, 600, 270, "Colour bars"))
    shapes(fb, *panel(fb, 650, 120, 600, 270, "rect  ellipse  poly  line"))
    plot(fb, *panel(fb, 30, 410, 600, 270, "Plot"))
    mx, my, mw, mh = panel(fb, 650, 410, 600, 270, "Mandelbrot (@micropython.viper)")
    t1 = time.ticks_ms()
    mandelbrot(disp, mx, my, mw, mh)
    t2 = time.ticks_ms()

    info = "drawn in %d ms (Mandelbrot %d ms)" % (time.ticks_diff(t2, t0), time.ticks_diff(t2, t1))
    fb.text(info, 30, HEIGHT - 22, hdmi.GREY)
    disp.show()
    print(info)


def animate(seconds=20, hardware=True):
    """Bouncing balls, double buffered: full redraw every frame, no tearing."""
    disp = hdmi.Display(double_buffer=True, hardware=hardware)
    balls = []
    for i in range(8):
        balls.append([100 + i * 130, 100 + (i * 70) % 500, 7 - i, 5 + (i % 3),
                      30 + 6 * i, rgb(255 - i * 25, 80 + i * 20, 60 + i * 24)])
    frames = 0
    fps = 0
    t_start = t_fps = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t_start) < seconds * 1000:
        fb = disp.fb
        fb.fill(rgb(6, 10, 30))
        for gx in range(0, WIDTH, 80):
            fb.vline(gx, 0, HEIGHT, rgb(20, 30, 70))
        for gy in range(0, HEIGHT, 80):
            fb.hline(0, gy, WIDTH, rgb(20, 30, 70))
        for b in balls:
            b[0] += b[2]
            b[1] += b[3]
            r = b[4]
            if b[0] < r or b[0] > WIDTH - r:
                b[2] = -b[2]
            if b[1] < r or b[1] > HEIGHT - r:
                b[3] = -b[3]
            fb.ellipse(b[0], b[1], r, r, b[5], True)
            fb.ellipse(b[0] - r // 3, b[1] - r // 3, r // 4, r // 4, hdmi.WHITE, True)
        text(fb, "%d fps" % fps, 30, 30, hdmi.WHITE, scale=3)
        disp.show()
        frames += 1
        now = time.ticks_ms()
        if time.ticks_diff(now, t_fps) >= 1000:
            fps = frames * 1000 // time.ticks_diff(now, t_fps)
            frames = 0
            t_fps = now
    return disp


def main(anim_seconds=20):
    hw = hdmi.available()
    if not hw:
        print("HDMI hardware not found: drawing into memory only")
    disp = hdmi.Display(hardware=hw)
    test_screen(disp)
    if anim_seconds:
        time.sleep(5)
        animate(anim_seconds, hw)
        test_screen(hdmi.Display(hardware=hw))


main()
