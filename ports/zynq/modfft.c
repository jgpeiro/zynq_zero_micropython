/*
 * modfft.c - _fft: the C parts of the fft module (see modules/fft.py).
 *
 *   _fft.c(re, im, inverse=False)       radix-2 FFT on the Cortex-A9, in place,
 *                                       double precision, N = 1 .. 65536
 *   _fft.hw(base, re, im, inverse=False) run a PL FFT engine at `base`, in place.
 *                                       Returns (pl_cycles, overflow).
 *   _fft.probe(base)                     engine ID string ("MFFT"/"XFFT") or None
 *
 * re and im are array('d') of the same power-of-two length.
 *
 * PL engines (hw/rtl/myfft_axil.v, hw/rtl/xfft_ctrl.v) share one register map:
 *   0x00 ID  0x04 CTRL  0x08 STATUS  0x0C LOG2N  0x10 INVERSE  0x14 CYCLES
 *   0x18 LOG2N_MAX  0x1C FORMAT  0x1000 input  0x2000 output (re)  0x3000 output (im)
 * FORMAT 0 (own core): packed Q1.15 output = FFT/N (forward) or IFFT (inverse);
 *                      needs every input |x| < 1.
 * FORMAT 1 (Xilinx):   unscaled 32-bit re/im = sum x[n] e^(-/+j...), no 1/N.
 * The driver scales the input into 16 bits, then scales the result back to
 * the same convention as _fft.c: forward = sum, inverse = sum / N.
 *
 * SPDX-License-Identifier: MIT
 */
#include <math.h>
#include <stdint.h>

#include "py/runtime.h"
#include "py/mphal.h"
#include "py/mperrno.h"

// ---- Helpers -----------------------------------------------------------------------
static size_t get_re_im(mp_obj_t re_obj, mp_obj_t im_obj, double **re, double **im) {
    mp_buffer_info_t bre, bim;
    mp_get_buffer_raise(re_obj, &bre, MP_BUFFER_RW);
    mp_get_buffer_raise(im_obj, &bim, MP_BUFFER_RW);
    if (bre.typecode != 'd' || bim.typecode != 'd') {
        mp_raise_TypeError(MP_ERROR_TEXT("re and im must be array('d')"));
    }
    if (bre.len != bim.len) {
        mp_raise_ValueError(MP_ERROR_TEXT("re and im differ in length"));
    }
    *re = bre.buf;
    *im = bim.buf;
    return bre.len / sizeof(double);
}

static int log2_exact(size_t n) {
    if (n == 0 || (n & (n - 1)) != 0) {
        return -1;
    }
    int l = 0;
    while ((1u << l) < n) {
        l++;
    }
    return l;
}

// ---- C FFT -------------------------------------------------------------------------
#define FFT_C_LOG2N_MAX (16)

// cos/sin(2*pi*k/N) for the most recent N, k < N/2 (512 KB, in DDR)
static double tw_cos[1 << (FFT_C_LOG2N_MAX - 1)];
static double tw_sin[1 << (FFT_C_LOG2N_MAX - 1)];
static size_t tw_n;

static void fft_c_inplace(double *re, double *im, size_t n, bool inverse) {
    // Bit-reversal permutation
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) {
            j ^= bit;
        }
        j |= bit;
        if (i < j) {
            double t = re[i];
            re[i] = re[j];
            re[j] = t;
            t = im[i];
            im[i] = im[j];
            im[j] = t;
        }
    }

    if (tw_n != n) {
        for (size_t k = 0; k < n / 2; k++) {
            double a = 2.0 * M_PI * (double)k / (double)n;
            tw_cos[k] = cos(a);
            tw_sin[k] = sin(a);
        }
        tw_n = n;
    }

    // Butterflies: X[a] = x[a] + W x[b], X[b] = x[a] - W x[b], W = e^(-/+ j 2 pi k / size)
    const double sign = inverse ? 1.0 : -1.0;
    for (size_t half = 1; half < n; half <<= 1) {
        size_t step = n / (2 * half);
        for (size_t start = 0; start < n; start += 2 * half) {
            for (size_t k = 0; k < half; k++) {
                double wr = tw_cos[k * step];
                double wi = sign * tw_sin[k * step];
                size_t a = start + k, b = a + half;
                double tr = wr * re[b] - wi * im[b];
                double ti = wr * im[b] + wi * re[b];
                re[b] = re[a] - tr;
                im[b] = im[a] - ti;
                re[a] += tr;
                im[a] += ti;
            }
        }
    }

    if (inverse) {
        double s = 1.0 / (double)n;
        for (size_t i = 0; i < n; i++) {
            re[i] *= s;
            im[i] *= s;
        }
    }
}

static mp_obj_t fft_c(size_t n_args, const mp_obj_t *args) {
    double *re, *im;
    size_t n = get_re_im(args[0], args[1], &re, &im);
    int l = log2_exact(n);
    if (l < 0 || l > FFT_C_LOG2N_MAX) {
        mp_raise_ValueError(MP_ERROR_TEXT("length must be a power of 2 up to 65536"));
    }
    fft_c_inplace(re, im, n, n_args > 2 && mp_obj_is_true(args[2]));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(fft_c_obj, 2, 3, fft_c);

// ---- PL engines --------------------------------------------------------------------
#define ENG_ID          (0x0000)
#define ENG_CTRL        (0x0004)
#define ENG_STATUS      (0x0008)
#define ENG_LOG2N       (0x000C)
#define ENG_INVERSE     (0x0010)
#define ENG_CYCLES      (0x0014)
#define ENG_LOG2N_MAX   (0x0018)
#define ENG_FORMAT      (0x001C)
#define ENG_IN          (0x1000)
#define ENG_OUT_RE      (0x2000)
#define ENG_OUT_IM      (0x3000)

#define STATUS_BUSY     (1u << 0)
#define STATUS_DONE     (1u << 1)
#define STATUS_OVF      (1u << 2)

#define ID_MFFT         (0x4D464654u)
#define ID_XFFT         (0x58464654u)

#define ENG(base, off)  (*(volatile uint32_t *)((base) + (off)))

static inline int32_t round_clamp16(double v) {
    v = v < 0 ? v - 0.5 : v + 0.5;
    if (v > 32767.0) {
        return 32767;
    }
    if (v < -32768.0) {
        return -32768;
    }
    return (int32_t)v;
}

static bool engine_present(uintptr_t base) {
    uint32_t id = ENG(base, ENG_ID);
    return id == ID_MFFT || id == ID_XFFT;
}

static mp_obj_t fft_probe(mp_obj_t base_in) {
    uintptr_t base = mp_obj_get_int_truncated(base_in);
    if (!engine_present(base)) {
        return mp_const_none;
    }
    uint32_t id = ENG(base, ENG_ID);
    char s[4] = { id >> 24, id >> 16, id >> 8, id };
    return mp_obj_new_str(s, 4);
}
static MP_DEFINE_CONST_FUN_OBJ_1(fft_probe_obj, fft_probe);

static mp_obj_t fft_hw(size_t n_args, const mp_obj_t *args) {
    uintptr_t base = mp_obj_get_int_truncated(args[0]);
    double *re, *im;
    size_t n = get_re_im(args[1], args[2], &re, &im);
    bool inverse = n_args > 3 && mp_obj_is_true(args[3]);

    if (!engine_present(base)) {
        mp_raise_msg_varg(&mp_type_OSError,
            MP_ERROR_TEXT("no FFT engine at 0x%08x (is the bitstream loaded?)"), (unsigned)base);
    }
    int l = log2_exact(n);
    int lmax = ENG(base, ENG_LOG2N_MAX);
    if (l < 3 || l > lmax) {
        mp_raise_msg_varg(&mp_type_ValueError,
            MP_ERROR_TEXT("hardware FFT length must be a power of 2 from 8 to %d"), 1 << lmax);
    }
    if (ENG(base, ENG_STATUS) & STATUS_BUSY) {
        mp_raise_OSError(MP_EBUSY);
    }
    uint32_t format = ENG(base, ENG_FORMAT);

    // Scale into 16 bits. Own core (FORMAT 0) halves every stage, which can't
    // overflow if every |x| < 1: bound the complex magnitude, with 10% margin
    // for rounding. Xilinx core (FORMAT 1) is unscaled: use the full range.
    double peak = 0.0, s;
    if (format == 0) {
        for (size_t i = 0; i < n; i++) {
            double m = re[i] * re[i] + im[i] * im[i];
            if (m > peak) {
                peak = m;
            }
        }
        peak = sqrt(peak);
        s = 0.9 * 32767.0 / peak;
    } else {
        for (size_t i = 0; i < n; i++) {
            double a = fabs(re[i]), b = fabs(im[i]);
            if (a > peak) {
                peak = a;
            }
            if (b > peak) {
                peak = b;
            }
        }
        s = 32767.0 / peak;
    }
    if (peak == 0.0 || !isfinite(peak)) {
        if (peak == 0.0) {
            return mp_obj_new_tuple(2, (mp_obj_t[]) {MP_OBJ_NEW_SMALL_INT(0), mp_const_false});
        }
        mp_raise_ValueError(MP_ERROR_TEXT("input contains inf or nan"));
    }

    for (size_t i = 0; i < n; i++) {
        uint32_t qr = (uint32_t)round_clamp16(re[i] * s) & 0xFFFF;
        uint32_t qi = (uint32_t)round_clamp16(im[i] * s) & 0xFFFF;
        ENG(base, ENG_IN + 4 * i) = (qi << 16) | qr;
    }
    ENG(base, ENG_LOG2N) = l;
    ENG(base, ENG_INVERSE) = inverse;
    ENG(base, ENG_CTRL) = 1;
    __asm volatile ("dsb" ::: "memory");

    mp_uint_t t0 = mp_hal_ticks_ms();
    uint32_t status;
    while (!((status = ENG(base, ENG_STATUS)) & STATUS_DONE)) {
        if (mp_hal_ticks_ms() - t0 > 1000) {
            mp_raise_OSError(MP_ETIMEDOUT);
        }
    }
    uint32_t cycles = ENG(base, ENG_CYCLES);

    // Back to: forward = sum x e^-j.., inverse = (1/N) sum X e^+j..
    if (format == 0) {
        double k = inverse ? 1.0 / s : (double)n / s;   // hw = FFT/N or IFFT
        for (size_t i = 0; i < n; i++) {
            uint32_t w = ENG(base, ENG_OUT_RE + 4 * i);
            re[i] = (int16_t)(w & 0xFFFF) * k;
            im[i] = (int16_t)(w >> 16) * k;
        }
    } else {
        double k = inverse ? 1.0 / (s * (double)n) : 1.0 / s;   // hw = unscaled sum
        for (size_t i = 0; i < n; i++) {
            re[i] = (int32_t)ENG(base, ENG_OUT_RE + 4 * i) * k;
            im[i] = (int32_t)ENG(base, ENG_OUT_IM + 4 * i) * k;
        }
    }

    mp_obj_t ret[2] = {
        mp_obj_new_int_from_uint(cycles),
        mp_obj_new_bool(status & STATUS_OVF),
    };
    return mp_obj_new_tuple(2, ret);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(fft_hw_obj, 3, 4, fft_hw);

static const mp_rom_map_elem_t fft_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__fft) },
    { MP_ROM_QSTR(MP_QSTR_c), MP_ROM_PTR(&fft_c_obj) },
    { MP_ROM_QSTR(MP_QSTR_hw), MP_ROM_PTR(&fft_hw_obj) },
    { MP_ROM_QSTR(MP_QSTR_probe), MP_ROM_PTR(&fft_probe_obj) },
    { MP_ROM_QSTR(MP_QSTR_C_LOG2N_MAX), MP_ROM_INT(FFT_C_LOG2N_MAX) },
};
static MP_DEFINE_CONST_DICT(fft_module_globals, fft_module_globals_table);

const mp_obj_module_t mp_module__fft = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&fft_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR__fft, mp_module__fft);
