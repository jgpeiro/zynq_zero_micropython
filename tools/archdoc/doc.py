"""Build the ZYNQ ZERO MicroPython architecture document (HTML → PDF with WeasyPrint)."""
import sys
import weasyprint

from docbase import Doc
import content1
import content2
import content3


def cover_art():
    """Abstract chip: PS and PL halves, buses, pins. Own artwork."""
    W, H = 1050, 640
    e = []
    cx, cy, cw, ch = 300, 70, 520, 470
    # pins around the package
    for i in range(16):
        x = cx + 30 + i * 30
        e.append(f'<rect x="{x}" y="{cy - 22}" width="14" height="22" fill="#d9d9d9"/>')
        e.append(f'<rect x="{x}" y="{cy + ch}" width="14" height="22" fill="#d9d9d9"/>')
    for i in range(14):
        y = cy + 30 + i * 30
        e.append(f'<rect x="{cx - 22}" y="{y}" width="22" height="14" fill="#d9d9d9"/>')
        e.append(f'<rect x="{cx + cw}" y="{y}" width="22" height="14" fill="#d9d9d9"/>')
    # traces leaving the pins
    import random
    rnd = random.Random(7)
    for i in range(14):
        y = cy + 37 + i * 30
        L = rnd.randint(60, 260)
        e.append(f'<path d="M{cx - 22},{y} H{cx - 22 - L}" stroke="#e2e2e2" stroke-width="3" fill="none"/>')
        e.append(f'<circle cx="{cx - 22 - L}" cy="{y}" r="5" fill="#e2e2e2"/>')
        L = rnd.randint(60, 200)
        e.append(f'<path d="M{cx + cw + 22},{y} H{cx + cw + 22 + L}" stroke="#e2e2e2" stroke-width="3" fill="none"/>')
        e.append(f'<circle cx="{cx + cw + 22 + L}" cy="{y}" r="5" fill="#e2e2e2"/>')
    e.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="14" fill="#2b2b2b"/>')
    # PS half
    e.append(f'<rect x="{cx + 26}" y="{cy + 26}" width="214" height="{ch - 52}" rx="6" fill="#d7e7f6"/>')
    for r in range(3):
        e.append(f'<rect x="{cx + 46}" y="{cy + 50 + r * 80}" width="174" height="60" rx="4" fill="#ffffff" opacity="0.85"/>')
    e.append(f'<rect x="{cx + 46}" y="{cy + 300}" width="80" height="90" rx="4" fill="#fff1bf"/>')
    e.append(f'<rect x="{cx + 140}" y="{cy + 300}" width="80" height="90" rx="4" fill="#fff1bf"/>')
    # PL half: fabric grid
    px = cx + 262
    e.append(f'<rect x="{px}" y="{cy + 26}" width="232" height="{ch - 52}" rx="6" fill="#e3f1da"/>')
    for r in range(9):
        for c in range(5):
            fill = "#f7d6e0" if (r, c) in ((1, 1), (1, 2), (2, 1), (2, 2), (6, 3), (7, 3)) else \
                   "#fde4c9" if (r, c) in ((4, 0), (4, 1), (4, 2), (4, 3), (4, 4)) else "#ffffff"
            e.append(f'<rect x="{px + 18 + c * 42}" y="{cy + 46 + r * 44}" width="32" height="32" rx="3" fill="{fill}" opacity="0.9"/>')
    # buses between halves
    e.append(f'<rect x="{cx + 238}" y="{cy + 120}" width="26" height="12" fill="#8a8a8a"/>')
    e.append(f'<rect x="{cx + 238}" y="{cy + 330}" width="26" height="12" fill="#c51a4a"/>')
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" width="100%">' + "".join(e) + "</svg>")


MARK = ('<svg width="11mm" height="11mm" viewBox="0 0 40 40"><rect x="4" y="4" width="32" height="32" rx="5" '
        'fill="#2b2b2b"/><rect x="9" y="9" width="10" height="22" rx="2" fill="#d7e7f6"/>'
        '<rect x="21" y="9" width="10" height="22" rx="2" fill="#e3f1da"/>'
        '<rect x="17" y="24" width="6" height="3" fill="#c51a4a"/></svg>')


def main(out_pdf):
    d = Doc()
    content1.build(d)
    content2.build(d)
    content3.build(d)
    body = d.resolve("\n".join(d.out))

    cover = f"""
<section class="cover">
  <div class="mark">{MARK}<span class="name">ZYNQ ZERO MicroPython</span></div>
  <div class="art">{cover_art()}</div>
  <div class="title">ZYNQ ZERO MicroPython<br/>Architecture</div>
  <div class="rule"></div>
  <div class="subtitle">MicroPython, FFT engines, HDMI and LVGL on the Zynq-7010</div>
  <div class="foot">Architecture reference, 16 November 2026</div>
</section>"""

    colophon = """
<section class="front colophon">
  <div class="front-title">Colophon</div>
  <p>This document describes the ZYNQ ZERO MicroPython project: the Vivado hardware design for the
     ZYNQ ZERO board, the bare-metal MicroPython port, its drivers and the LVGL integration.</p>
  <p>The project's own sources (Verilog, Tcl, C, Python) are released under the MIT licence, as marked by
     the SPDX identifiers in each file. MicroPython and LVGL are MIT-licensed projects of their respective
     authors. The Xilinx IP cores used in the block design are subject to Xilinx's licence terms.</p>
  <p>Zynq, Vivado, Vitis and LogiCORE are trademarks of Advanced Micro Devices, Inc. Arm and Cortex are
     trademarks of Arm Limited. All other names are the property of their owners.</p>
  <p>Figures and numbers were taken from the project sources and from the firmware built from them;
     performance figures are QEMU measurements unless stated otherwise.</p>
  <div class="meta">build-date: 2026-11-16<br/>build-version: zynq_zero_micropython, LVGL build<br/>
     MicroPython v1.29.0, LVGL v9.6.0, lv_binding_micropython 032dda4b, Vivado 2021.1</div>
</section>"""

    toc = f"""
<section class="front" style="break-before: page">
  <div class="front-title">Table of Contents</div>
  {d.toc_html()}
</section>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>ZYNQ ZERO MicroPython Architecture</title>
<meta name="author" content="ZYNQ ZERO MicroPython project"/>
<meta name="description" content="Architecture of the ZYNQ ZERO MicroPython system"/>
<link rel="stylesheet" href="style.css"/></head><body>
{cover}{colophon}{toc}{body}
</body></html>"""
    open("doc.html", "w").write(html)
    weasyprint.HTML("doc.html", base_url=".").write_pdf(out_pdf)
    print("figures", d.fig, "tables", d.tab)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "zynq_zero_micropython_architecture.pdf")
