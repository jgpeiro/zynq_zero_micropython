#!/usr/bin/env python3
"""Simulate the PL designs with iverilog: both FFT peripherals (checked
against numpy) and the HDMI transmitter (tb_hdmi.v).

The input quantisation and output rescaling below mirror the MicroPython driver
(ports/zynq/modfft.c, fft_hw), so this also checks the driver's arithmetic.

    python3 run_sim.py            # all cases
    python3 run_sim.py --quick    # small sizes only
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.join(HERE, "..", "rtl")
RTL_MY = ["axil_slave.v", "tdp_ram.v", "twiddle_rom.v", "myfft_axil.v"]
RTL_X = ["axil_slave.v", "xfft_ctrl.v"]


def build(name, files, defines):
    exe = os.path.join(tempfile.gettempdir(), f"tb_{name}.vvp")
    srcs = [os.path.join(RTL, f) for f in files] + [os.path.join(HERE, "tb_fft.v")]
    if name == "xfft":
        srcs.append(os.path.join(HERE, "xfft_model.v"))
    subprocess.run(["iverilog", "-g2005", "-Wall", "-Wno-timescale", "-o", exe, *defines, *srcs], check=True)
    return exe


def quantise(x, fmt):
    """Driver: scale complex input into Q1.15, return (packed words, scale)."""
    if fmt == 0:   # own core: halves every stage, needs |x| < 1
        peak = np.max(np.abs(x))
        s = 0.9 * 32767 / peak
    else:          # xfft unscaled: use the full 16-bit range per component
        peak = max(np.max(np.abs(x.real)), np.max(np.abs(x.imag)))
        s = 32767 / peak
    qr = np.clip(np.round(x.real * s), -32768, 32767).astype(np.int64)
    qi = np.clip(np.round(x.imag * s), -32768, 32767).astype(np.int64)
    words = ((qi & 0xFFFF) << 16) | (qr & 0xFFFF)
    return words, s


def rescale(y, s, n, fmt, inverse):
    """Driver: hardware output -> FFT (forward) or IFFT (inverse) in floating point."""
    if fmt == 0:   # hw = FFT/N or IFFT
        return y * n / s if not inverse else y / s
    return y / s if not inverse else y / (s * n)   # hw = unscaled sum


def run(exe, log2n, inverse, x, fmt_expect, workdir):
    n = 1 << log2n
    words, s = quantise(x, fmt_expect)
    with open(os.path.join(workdir, "in.txt"), "w") as f:
        f.write(f"{log2n} {int(inverse)}\n")
        f.writelines(f"{w:08x}\n" for w in words)
    res = subprocess.run(["vvp", "-n", exe], cwd=workdir, capture_output=True, text=True)
    if "ERROR" in res.stdout:
        raise RuntimeError(res.stdout)
    with open(os.path.join(workdir, "out.txt")) as f:
        head = f.readline().split()
        cycles, ovf, fmt, ident = int(head[0]), int(head[1]), int(head[2]), head[3]
        vals = np.array([[int(v) for v in line.split()] for line in f])
    assert fmt == fmt_expect, f"FORMAT {fmt} != {fmt_expect}"
    y = vals[:, 0] + 1j * vals[:, 1]
    got = rescale(y, s, n, fmt, inverse)
    ref = np.fft.ifft(x) if inverse else np.fft.fft(x)
    err = np.max(np.abs(got - ref)) / np.max(np.abs(ref))
    # Same error in units of the hardware output LSB (what fixed point can promise)
    lsb = rescale(np.array([1.0]), s, n, fmt, inverse)[0]
    err_lsb = np.max(np.abs(got - ref)) / lsb
    return cycles, ovf, ident, err, err_lsb


def signals(n, rng):
    t = np.arange(n)
    yield "noise", (rng.uniform(-1, 1, n) + 1j * rng.uniform(-1, 1, n))
    yield "tones", (0.7 * np.cos(2 * np.pi * 3 * t / n) + 0.2 * np.sin(2 * np.pi * (n // 4 - 1) * t / n)
                    + 0j)
    yield "impulse", np.eye(1, n, 1)[0] * (2.5 - 1.5j)
    yield "dc", np.full(n, 0.5 + 0.5j)


def run_hdmi():
    """TMDS encoder + HDMI transmitter testbench (tb_hdmi.v)."""
    exe = os.path.join(tempfile.gettempdir(), "tb_hdmi.vvp")
    srcs = [os.path.join(HERE, "tb_hdmi.v"), os.path.join(HERE, "unisim_stubs.v"),
            os.path.join(RTL, "tmds_encoder.v"), os.path.join(RTL, "hdmi_tx.v")]
    subprocess.run(["iverilog", "-g2005", "-Wno-timescale", "-o", exe, *srcs], check=True)
    out = subprocess.run(["vvp", "-n", exe], capture_output=True, text=True).stdout
    print("== hdmi ==")
    for line in out.splitlines():
        if line.startswith(("A)", "B)", "ALL", "FAILED")):
            print("  " + line)
    return "ALL PASSED" in out


def main():
    quick = "--quick" in sys.argv
    sizes = [3, 5, 6] if quick else [3, 4, 6, 8, 10]
    rng = np.random.default_rng(1)
    work = tempfile.mkdtemp()
    failures = 0
    for name, files, defines, fmt, tol in (
        ("myfft", RTL_MY, [], 0, None),
        ("xfft", RTL_X, ["-DXFFT"], 1, None),
    ):
        exe = build(name, files, defines)
        print(f"== {name} ==")
        for log2n in sizes:
            n = 1 << log2n
            if name == "xfft" and log2n > 8 and quick:
                continue
            for sig, x in signals(n, rng):
                for inverse in (False, True):
                    cycles, ovf, ident, err, err_lsb = run(exe, log2n, inverse, x, fmt, work)
                    # Own core: each stage rounds to 16 bits (<= 0.5 LSB) and halves the
                    # earlier error, plus the input quantisation (0.5 LSB, scaled by N).
                    # xfft model: exact DFT -> only input quantisation (+-0.5 LSB per sample,
                    # a random walk over N samples: worst bin ~1.4*sqrt(N) LSB) and rounding.
                    limit = (0.5 * log2n + 1.0) if name == "myfft" else (1.5 * np.sqrt(n) + 1.0)
                    ok = err_lsb <= limit and not ovf
                    failures += not ok
                    print(f"  N={n:5d} {'inv' if inverse else 'fwd'} {sig:8s} cycles={cycles:6d} "
                          f"ovf={ovf} err={err_lsb:5.2f} LSB (limit {limit:4.1f}) rel={err:.1e} "
                          f"{'ok' if ok else 'FAIL'}")
    failures += not run_hdmi()
    print("ALL PASSED" if failures == 0 else f"{failures} FAILED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
