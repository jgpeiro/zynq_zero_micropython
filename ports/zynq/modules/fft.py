"""fft - Fast Fourier transform on the ZYNQ ZERO, four ways.

    method      where                        how
    "python"    Cortex-A9, MicroPython       radix-2 in Python (this file), double
    "c"         Cortex-A9, C                 radix-2 in C (modfft.c), double, VFP
    "xilinx"    PL, Xilinx FFT LogiCORE      xfft v9.1 radix-2 burst, 16-bit in,
                                             unscaled 27-bit out (xfft_ctrl.v)
    "verilog"   PL, own Verilog              radix-2 DIT, 1 butterfly/clock, 16-bit,
                                             scaled 1/2 per stage (myfft_axil.v)

All methods use the same convention as numpy:
    forward  X[k] = sum x[n] e^(-2j pi n k / N)
    inverse  x[n] = (1/N) sum X[k] e^(+2j pi n k / N)

    import fft
    X = fft.fft([1, 0, 0, 0, 0, 0, 0, 0], "verilog")   # list of complex
    x = fft.ifft(X, "xilinx")
    fft.info()           # which PL engines are present
    fft.benchmark(1024)  # time and accuracy of all four

The hardware methods take N = 8 .. 1024 and work in 16-bit fixed point: the
driver scales the input to full range and the result back, so expect about
1e-4 relative error (Xilinx) to 1e-3 (own core, which keeps 16 bits per
stage). Python and C take any power of two (C up to 65536).

For speed, run() works in place on two array('d') (real, imaginary) and
skips the list conversions.
"""
from micropython import const
import array
import math
import time

import _fft

VERILOG_BASE = const(0x43C00000)  # myfft_0 (hw/rtl/myfft_axil.v)
XILINX_BASE = const(0x43C10000)  # xfft_ctrl_0 + xfft_0 (hw/rtl/xfft_ctrl.v)
PL_CLOCK_HZ = const(100_000_000)  # FCLK_CLK0

METHODS = ("python", "c", "xilinx", "verilog")
_BASE = {"xilinx": XILINX_BASE, "verilog": VERILOG_BASE}


def fft_python(re, im, inverse=False):
    """Pure Python in-place radix-2 FFT of two float sequences (any power of 2)."""
    n = len(re)
    if n == 0 or n & (n - 1):
        raise ValueError("length must be a power of 2")
    # bit-reversal permutation
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            re[i], re[j] = re[j], re[i]
            im[i], im[j] = im[j], im[i]
    # butterflies
    sign = 1.0 if inverse else -1.0
    half = 1
    while half < n:
        step = math.pi / half * sign
        for k in range(half):
            wr = math.cos(step * k)
            wi = math.sin(step * k)
            for a in range(k, n, 2 * half):
                b = a + half
                tr = wr * re[b] - wi * im[b]
                ti = wr * im[b] + wi * re[b]
                re[b] = re[a] - tr
                im[b] = im[a] - ti
                re[a] += tr
                im[a] += ti
        half *= 2
    if inverse:
        for i in range(n):
            re[i] /= n
            im[i] /= n


def run(re, im, method="c", inverse=False):
    """In-place transform of array('d') re/im. Returns PL clock cycles of the
    transform itself for the hardware methods, None otherwise."""
    if method == "python":
        fft_python(re, im, inverse)
        return None
    if method == "c":
        _fft.c(re, im, inverse)
        return None
    base = _BASE.get(method)
    if base is None:
        raise ValueError("method must be one of " + ", ".join(METHODS))
    cycles, overflow = _fft.hw(base, re, im, inverse)
    if overflow:
        raise RuntimeError("FFT overflow in the PL")
    return cycles


def to_arrays(x):
    """Sequence of numbers (real or complex) -> (array('d') re, array('d') im)."""
    n = len(x)
    re = array.array("d", bytearray(8 * n))
    im = array.array("d", bytearray(8 * n))
    for i in range(n):
        v = x[i]
        if isinstance(v, complex):
            re[i] = v.real
            im[i] = v.imag
        else:
            re[i] = v
    return re, im


def from_arrays(re, im):
    return [complex(re[i], im[i]) for i in range(len(re))]


def fft(x, method="c"):
    """Forward FFT of a sequence of numbers; returns a list of complex."""
    re, im = to_arrays(x)
    run(re, im, method)
    return from_arrays(re, im)


def ifft(X, method="c"):
    """Inverse FFT (with 1/N); returns a list of complex."""
    re, im = to_arrays(X)
    run(re, im, method, True)
    return from_arrays(re, im)


def available(method):
    if method in ("python", "c"):
        return True
    return _fft.probe(_BASE[method]) is not None


def info():
    """Print which FFT engines are present in the PL."""
    for m in ("xilinx", "verilog"):
        ident = _fft.probe(_BASE[m])
        state = ("engine %s" % ident) if ident else "not found (bitstream loaded?)"
        print("%-8s 0x%08x  %s" % (m, _BASE[m], state))


def _test_signal(n):
    """Two tones, a DC offset and a little deterministic 'noise'."""
    re = array.array("d", bytearray(8 * n))
    im = array.array("d", bytearray(8 * n))
    seed = 12345
    for i in range(n):
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        noise = (seed / 0x7FFFFFFF - 0.5) * 0.05
        re[i] = 0.1 + 0.6 * math.cos(2 * math.pi * 5 * i / n) + noise
        im[i] = 0.3 * math.sin(2 * math.pi * (n // 8) * i / n)
    return re, im


def benchmark(n=1024, methods=METHODS, repeat=5, inverse=False):
    """Time all methods on the same n-point signal and compare with the C result.

    'total' is the whole call as seen from Python (for the PL engines that
    includes moving the samples over AXI4-Lite); 'PL' is the transform alone,
    from the engine's cycle counter."""
    ref_re, ref_im = _test_signal(n)
    _fft.c(ref_re, ref_im, inverse)
    peak = max(math.sqrt(ref_re[i] ** 2 + ref_im[i] ** 2) for i in range(n))

    print("FFT benchmark: N = %d, %s, best of %d" % (n, "inverse" if inverse else "forward", repeat))
    print("%-8s %12s %12s %12s" % ("method", "total [us]", "PL [us]", "max rel err"))
    results = {}
    for m in methods:
        if not available(m):
            print("%-8s %12s" % (m, "not available"))
            continue
        best = None
        cycles = None
        reps = 1 if m == "python" and n >= 256 else repeat
        for _ in range(reps):
            re, im = _test_signal(n)
            t0 = time.ticks_us()
            cycles = run(re, im, m, inverse)
            dt = time.ticks_diff(time.ticks_us(), t0)
            best = dt if best is None or dt < best else best
        err = max(abs(complex(re[i] - ref_re[i], im[i] - ref_im[i])) for i in range(n)) / peak
        pl_us = cycles * 1_000_000 / PL_CLOCK_HZ if cycles is not None else None
        results[m] = (best, pl_us, err)
        print("%-8s %12d %12s %12.1e" % (m, best, "-" if pl_us is None else "%.1f" % pl_us, err))
    return results
