"""Tiny SVG builder for the architecture document's block diagrams."""
from html import escape

FONT = "Inter"

# Fills by role (shared by every figure, see the legend helper)
PS = "#d7e7f6"      # processing system
PL = "#e3f1da"      # programmable logic region
XIP = "#fde4c9"     # Xilinx IP
RTL = "#f7d6e0"     # own Verilog
MEM = "#fff1bf"     # memory
EXT = "#ececec"     # off-chip / external
SW = "#e5def3"      # software
SWC = "#d9ecec"     # software, C level
WHITE = "#ffffff"
INK = "#2b2b2b"
ACCENT = "#c51a4a"
GREY = "#8a8a8a"


class Svg:
    def __init__(self, w, h, ident):
        self.w, self.h, self.id = w, h, ident
        self.el = []

    # ---- primitives -------------------------------------------------------------
    def rect(self, x, y, w, h, fill=WHITE, stroke=INK, lw=1, rx=2, dash=False, opacity=None):
        d = ' stroke-dasharray="4 3"' if dash else ""
        o = f' fill-opacity="{opacity}"' if opacity is not None else ""
        self.el.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                       f'fill="{fill}"{o} stroke="{stroke}" stroke-width="{lw}"{d}/>')

    def text(self, x, y, s, fs=10, anchor="middle", weight="normal", fill=INK,
             italic=False, mono=False, lh=1.25):
        fam = "DejaVu Sans Mono" if mono else FONT
        st = ' font-style="italic"' if italic else ""
        lines = str(s).split("\n")
        y0 = y - (len(lines) - 1) * fs * lh / 2
        for i, ln in enumerate(lines):
            self.el.append(f'<text x="{x}" y="{y0 + i * fs * lh + fs * 0.35:.1f}" font-family="{fam}" '
                           f'font-size="{fs}" text-anchor="{anchor}" font-weight="{weight}" '
                           f'fill="{fill}"{st}>{escape(ln)}</text>')

    def box(self, x, y, w, h, label="", fill=WHITE, sub=None, fs=10.5, sfs=8.5, bold=True,
            stroke=INK, lw=1, dash=False, rx=2, title_top=False, mono_sub=False, color=INK):
        self.rect(x, y, w, h, fill, stroke, lw, rx, dash)
        wt = "600" if bold else "normal"
        if title_top:
            self.text(x + 6, y + 10, label, fs, "start", wt, color)
            return
        if sub:
            nl = label.count("\n") + 1
            ns = sub.count("\n") + 1
            tot = nl * fs * 1.25 + ns * sfs * 1.25
            ty = y + h / 2 - tot / 2 + nl * fs * 1.25 / 2
            self.text(x + w / 2, ty, label, fs, "middle", wt, color)
            self.text(x + w / 2, ty + nl * fs * 1.25 / 2 + ns * sfs * 1.25 / 2 + 1, sub, sfs,
                      "middle", "normal", "#444", mono=mono_sub)
        else:
            self.text(x + w / 2, y + h / 2, label, fs, "middle", wt, color)

    def line(self, pts, arrow="end", color=INK, lw=1.1, dash=False, label=None, lpos=None,
             lfs=8.5, lanchor="middle", lcolor=None):
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        m = ""
        mid = f"{self.id}-ah-{color.strip('#')}"
        self._marker(mid, color)
        if arrow in ("end", "both"):
            m += f' marker-end="url(#{mid})"'
        if arrow in ("start", "both"):
            m += f' marker-start="url(#{mid}-s)"'
        dd = ' stroke-dasharray="4 3"' if dash else ""
        self.el.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{lw}"{dd}{m}/>')
        if label:
            if lpos is None:
                (x1, y1), (x2, y2) = pts[0], pts[1]
                lpos = ((x1 + x2) / 2, (y1 + y2) / 2 - 6)
            self.text(lpos[0], lpos[1], label, lfs, lanchor, "normal", lcolor or "#444")

    def bus(self, pts, label=None, lpos=None, color="#5a5a5a", lw=4, arrow="end", lfs=8.5):
        """Thick bus arrow."""
        mid = f"{self.id}-bh-{color.strip('#')}"
        self._marker(mid, color, size=2.4)
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        m = ""
        if arrow in ("end", "both"):
            m += f' marker-end="url(#{mid})"'
        if arrow in ("start", "both"):
            m += f' marker-start="url(#{mid}-s)"'
        self.el.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{lw}"{m}/>')
        if label:
            if lpos is None:
                (x1, y1), (x2, y2) = pts[0], pts[1]
                lpos = ((x1 + x2) / 2, (y1 + y2) / 2 - 8)
            self.text(lpos[0], lpos[1], label, lfs, "middle", "normal", "#333")

    _markers = None

    def _marker(self, mid, color, size=6.5):
        if self._markers is None:
            self._markers = {}
        if mid in self._markers:
            return
        if size < 4:   # bus: marker scaled by stroke width
            path = "M0,0 L4,2 L0,4 z"
            mk = (f'<marker id="{mid}" viewBox="0 0 4 4" refX="2.2" refY="2" markerWidth="{size}" '
                  f'markerHeight="{size}" orient="auto"><path d="{path}" fill="{color}"/></marker>'
                  f'<marker id="{mid}-s" viewBox="0 0 4 4" refX="1.8" refY="2" markerWidth="{size}" '
                  f'markerHeight="{size}" orient="auto-start-reverse"><path d="{path}" fill="{color}"/></marker>')
        else:
            path = "M0,0 L10,5 L0,10 z"
            mk = (f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="{size}" '
                  f'markerHeight="{size}" markerUnits="userSpaceOnUse" orient="auto">'
                  f'<path d="{path}" fill="{color}"/></marker>'
                  f'<marker id="{mid}-s" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="{size}" '
                  f'markerHeight="{size}" markerUnits="userSpaceOnUse" orient="auto-start-reverse">'
                  f'<path d="{path}" fill="{color}"/></marker>')
        self._markers[mid] = mk

    def circle(self, x, y, r, fill=WHITE, stroke=INK, lw=1):
        self.el.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{lw}"/>')

    def poly(self, pts, fill=WHITE, stroke=INK, lw=1):
        p = " ".join(f"{x},{y}" for x, y in pts)
        self.el.append(f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{lw}"/>')

    def raw(self, s):
        self.el.append(s)

    def legend(self, x, y, items, fs=8.5):
        """items: [(fill, label, dash?)]"""
        cx = x
        for it in items:
            fill, label = it[0], it[1]
            dash = len(it) > 2 and it[2]
            self.rect(cx, y - 5, 14, 10, fill, INK, 0.8, 1.5, dash)
            self.text(cx + 18, y, label, fs, "start")
            cx += 30 + len(label) * fs * 0.6

    def render(self):
        defs = "".join((self._markers or {}).values())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="100%" preserveAspectRatio="xMidYMid meet">'
                f'<defs>{defs}</defs>{"".join(self.el)}</svg>')
