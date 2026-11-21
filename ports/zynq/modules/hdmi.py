"""hdmi - 1280x720 @ 60 Hz HDMI output, drawn with framebuf.

    import hdmi
    disp = hdmi.Display()
    fb = disp.fb                       # a framebuf.FrameBuffer, RGB565
    fb.fill(hdmi.BLACK)
    fb.fill_rect(100, 100, 300, 200, hdmi.rgb(255, 128, 0))
    fb.ellipse(640, 360, 200, 120, hdmi.CYAN, True)
    hdmi.text(fb, "Hello HDMI", 100, 400, hdmi.WHITE, scale=4)
    disp.show()                        # make it visible

Everything framebuf offers works on disp.fb: fill, pixel, hline, vline, line,
rect, ellipse, poly, text, scroll, blit.

show() is needed after drawing: the CPU draws through its data cache and the
video DMA reads DDR directly, so show() writes the cache back.

Display(double_buffer=True) draws into a hidden buffer and show() swaps it
onto the screen at the next frame (no tearing); disp.fb then points at the
other buffer, which still holds the picture from two show() calls ago, so
redraw it completely each frame.

Display(hardware=False) gives the same framebuffers without touching the PL,
e.g. to run drawing code in QEMU.

Hardware path: framebuffer in DDR -> AXI VDMA (HP0) -> RGB565 to RGB888 ->
AXI4-Stream to Video Out + Video Timing Controller (720p) -> hdmi_tx (TMDS
encoder + OSERDESE2, own Verilog) -> HDMI connector. DVI signalling, no audio.
"""
from micropython import const
import framebuf
import _hdmi

WIDTH = const(1280)
HEIGHT = const(720)

BLACK = const(0x0000)
WHITE = const(0xFFFF)
RED = const(0xF800)
GREEN = const(0x07E0)
BLUE = const(0x001F)
YELLOW = const(0xFFE0)
CYAN = const(0x07FF)
MAGENTA = const(0xF81F)
ORANGE = const(0xFD20)
GREY = const(0x8410)
DARK_GREY = const(0x4208)


def rgb(r, g, b):
    """8-bit R, G, B -> RGB565 colour for framebuf."""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def available():
    """True if the HDMI hardware (VDMA) is in the loaded bitstream."""
    return _hdmi.available()


class Display:
    def __init__(self, double_buffer=False, hardware=True):
        self._fbs = [framebuf.FrameBuffer(_hdmi.buffer(i), WIDTH, HEIGHT, framebuf.RGB565)
                     for i in range(2)]
        self.double_buffer = double_buffer
        self.hardware = hardware
        self._back = 1 if double_buffer else 0
        self.fb = self._fbs[self._back]
        self.width = WIDTH
        self.height = HEIGHT
        if hardware:
            _hdmi.init()           # clears both buffers, shows buffer 0
        else:
            for f in self._fbs:
                f.fill(BLACK)

    def show(self):
        """Put what was drawn on screen."""
        if self.hardware:
            _hdmi.show(self._back, self.double_buffer)
        if self.double_buffer:
            self._back ^= 1
            self.fb = self._fbs[self._back]

    def buffer(self, i=None):
        """Raw bytearray of a framebuffer (default: the one being drawn)."""
        return _hdmi.buffer(self._back if i is None else i)

    def status(self):
        return _hdmi.status()

    def off(self):
        _hdmi.stop()


_glyph_buf = bytearray(8)


def text(fb, s, x, y, color, scale=1):
    """framebuf.text with an integer scale factor (the font is 8x8 pixels)."""
    if scale <= 1:
        fb.text(s, x, y, color)
        return
    glyph = framebuf.FrameBuffer(_glyph_buf, 8, 8, framebuf.MONO_HLSB)
    for ch in s:
        glyph.fill(0)
        glyph.text(ch, 0, 0, 1)
        for gy in range(8):
            row = _glyph_buf[gy]
            gx = 0
            while gx < 8:                      # draw runs of set pixels as one rect
                if row & (0x80 >> gx):
                    start = gx
                    while gx < 8 and row & (0x80 >> gx):
                        gx += 1
                    fb.fill_rect(x + start * scale, y + gy * scale,
                                 (gx - start) * scale, scale, color)
                else:
                    gx += 1
        x += 8 * scale


def text_width(s, scale=1):
    return 8 * scale * len(s)
