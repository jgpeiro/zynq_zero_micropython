# FFT four ways: compare Python, C, the Xilinx FFT IP and the own Verilog core.
# Run with:  mpremote connect <port> run examples/fft_demo.py
import math
import fft

fft.info()
print()

# A 64-point signal with tones at bins 5 and 12: every method should find them
n = 64
x = [math.cos(2 * math.pi * 5 * i / n) + 0.5 * math.sin(2 * math.pi * 12 * i / n) for i in range(n)]
for method in fft.METHODS:
    if not fft.available(method):
        print("%-8s not available" % method)
        continue
    X = fft.fft(x, method)
    mags = [abs(v) for v in X[: n // 2]]
    peaks = sorted(range(len(mags)), key=lambda k: -mags[k])[:2]
    back = fft.ifft(X, method)
    err = max(abs(a - b) for a, b in zip(back, x))
    print("%-8s peaks at bins %s  (|X|=%.1f, %.1f)  round-trip err %.1e"
          % (method, sorted(peaks), mags[peaks[0]], mags[peaks[1]], err))
print()

# Speed and accuracy at 1024 points
fft.benchmark(1024)
