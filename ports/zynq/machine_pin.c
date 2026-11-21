/*
 * machine_pin.c - machine.Pin for the ZYNQ ZERO.
 *
 *   "LED1".."LED4"  PL, AXI GPIO channel 1 bits 0..3   output only
 *   "KEY1"          PL, AXI GPIO channel 2 bit 0       input only (0 = pressed)
 *   "LED0"          PS, MIO9 through the PS GPIO       input or output
 *
 * The PL pins are reached over M_AXI_GP0 -> AXI4-Lite (see hw/scripts/build.tcl).
 *
 *   from machine import Pin
 *   led = Pin("LED1", Pin.OUT)
 *   led.on(); led.off(); led.toggle(); led(1); led.value()
 *   Pin("KEY1", Pin.IN).value()
 *
 * Pins also implement the virtual pin protocol, so machine.Signal works:
 *   machine.Signal(Pin("KEY1", Pin.IN), invert=True).value()  # 1 when pressed
 *
 * SPDX-License-Identifier: MIT
 */
#include "py/runtime.h"
#include "py/mphal.h"
#include "extmod/modmachine.h"
#include "extmod/virtpin.h"
#include "zynq_regs.h"

enum {
    PIN_MODE_IN = 0,
    PIN_MODE_OUT = 1,
};

typedef enum {
    PIN_PS_MIO,         // PS GPIO, bit = MIO number (bank 0)
    PIN_PL_OUT,         // AXI GPIO channel 1 bit
    PIN_PL_IN,          // AXI GPIO channel 2 bit
} pin_kind_t;

typedef struct _machine_pin_obj_t {
    mp_obj_base_t base;
    qstr name;
    uint8_t kind;
    uint8_t bit;
} machine_pin_obj_t;

static const machine_pin_obj_t machine_pin_obj[] = {
    {{&machine_pin_type}, MP_QSTR_LED0, PIN_PS_MIO, 9},
    {{&machine_pin_type}, MP_QSTR_LED1, PIN_PL_OUT, 0},
    {{&machine_pin_type}, MP_QSTR_LED2, PIN_PL_OUT, 1},
    {{&machine_pin_type}, MP_QSTR_LED3, PIN_PL_OUT, 2},
    {{&machine_pin_type}, MP_QSTR_LED4, PIN_PL_OUT, 3},
    {{&machine_pin_type}, MP_QSTR_KEY1, PIN_PL_IN, 0},
};

// AXI GPIO channel 1 is write-only from our point of view: keep a shadow copy
// so single LEDs can change without a read-modify-write on the bus. It starts at
// 0, which matches C_DOUT_DEFAULT after the bitstream loads.
static uint32_t axi_gpio_out_shadow;

// ---- Low level -------------------------------------------------------------------------
static void mio_mux_gpio(uint32_t mio) {
    SLCR_UNLOCK = SLCR_UNLOCK_KEY;
    SLCR_APER_CLK_CTRL |= APER_GPIO_CLKACT;
    SLCR_MIO_PIN(mio) = MIO_IO_LVCMOS33;   // L0..L3 sel = 0 -> GPIO; bank 500 is 3.3 V
    SLCR_LOCK = SLCR_LOCK_KEY;
}

static bool pin_is_output(const machine_pin_obj_t *self) {
    switch (self->kind) {
        case PIN_PS_MIO:
            return (GPIO_DIRM_0 >> self->bit) & 1;
        case PIN_PL_OUT:
            return true;
        default:
            return false;
    }
}

static int pin_get(const machine_pin_obj_t *self) {
    switch (self->kind) {
        case PIN_PS_MIO:
            if (pin_is_output(self)) {
                return (GPIO_DATA_0 >> self->bit) & 1;
            }
            return (GPIO_DATA_0_RO >> self->bit) & 1;
        case PIN_PL_OUT:
            return (axi_gpio_out_shadow >> self->bit) & 1;
        default:
            return (AXI_GPIO2_DATA >> self->bit) & 1;
    }
}

static void pin_set(const machine_pin_obj_t *self, int value) {
    uint32_t mask = 1u << self->bit;
    switch (self->kind) {
        case PIN_PS_MIO:
            // Masked write: only this bit changes
            GPIO_MASK_DATA_0_LSW = ((~mask & 0xFFFFu) << 16) | (value ? mask : 0);
            break;
        case PIN_PL_OUT:
            if (value) {
                axi_gpio_out_shadow |= mask;
            } else {
                axi_gpio_out_shadow &= ~mask;
            }
            AXI_GPIO_DATA = axi_gpio_out_shadow;
            break;
        default:
            mp_raise_ValueError(MP_ERROR_TEXT("pin is input-only"));
    }
}

static void pin_set_mode(const machine_pin_obj_t *self, int mode) {
    switch (self->kind) {
        case PIN_PS_MIO:
            mio_mux_gpio(self->bit);
            if (mode == PIN_MODE_OUT) {
                GPIO_DIRM_0 |= 1u << self->bit;
                GPIO_OEN_0 |= 1u << self->bit;
            } else {
                GPIO_OEN_0 &= ~(1u << self->bit);
                GPIO_DIRM_0 &= ~(1u << self->bit);
            }
            break;
        case PIN_PL_OUT:
            if (mode != PIN_MODE_OUT) {
                mp_raise_ValueError(MP_ERROR_TEXT("pin is output-only"));
            }
            break;
        default:
            if (mode != PIN_MODE_IN) {
                mp_raise_ValueError(MP_ERROR_TEXT("pin is input-only"));
            }
            break;
    }
}

static bool name_eq_nocase(const char *a, const char *b, size_t len) {
    for (size_t i = 0; i < len; i++) {
        char ca = a[i], cb = b[i];
        if (ca >= 'a' && ca <= 'z') {
            ca -= 'a' - 'A';
        }
        if (cb >= 'a' && cb <= 'z') {
            cb -= 'a' - 'A';
        }
        if (ca != cb) {
            return false;
        }
    }
    return true;
}

static const machine_pin_obj_t *pin_find(mp_obj_t id) {
    if (mp_obj_is_type(id, &machine_pin_type)) {
        return MP_OBJ_TO_PTR(id);
    }
    if (mp_obj_is_str(id)) {
        size_t len;
        const char *name = mp_obj_str_get_data(id, &len);
        for (size_t i = 0; i < MP_ARRAY_SIZE(machine_pin_obj); i++) {
            size_t qlen;
            const char *qname = (const char *)qstr_data(machine_pin_obj[i].name, &qlen);
            if (len == qlen && name_eq_nocase(name, qname, len)) {
                return &machine_pin_obj[i];
            }
        }
    }
    mp_raise_ValueError(MP_ERROR_TEXT("unknown pin, use LED0..LED4 or KEY1"));
}

// ---- Python API --------------------------------------------------------------------------
static void machine_pin_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    (void)kind;
    const machine_pin_obj_t *self = MP_OBJ_TO_PTR(self_in);
    static const char *const where[] = {"PS MIO9", "PL AXI GPIO", "PL AXI GPIO2"};
    mp_printf(print, "Pin(%q, mode=%s)  # %s bit %u", self->name,
        pin_is_output(self) ? "OUT" : "IN", where[self->kind], self->bit);
}

// pin.init(mode=-1, value=None)
static mp_obj_t machine_pin_obj_init_helper(const machine_pin_obj_t *self, size_t n_args,
    const mp_obj_t *pos_args, mp_map_t *kw_args) {
    enum { ARG_mode, ARG_value };
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_mode, MP_ARG_INT, {.u_int = -1} },
        { MP_QSTR_value, MP_ARG_KW_ONLY | MP_ARG_OBJ, {.u_rom_obj = MP_ROM_NONE} },
    };
    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args, MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    int mode = args[ARG_mode].u_int;
    if (mode != -1 && mode != PIN_MODE_IN && mode != PIN_MODE_OUT) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid pin mode"));
    }
    // Set the level before switching to output, to avoid a glitch
    if (args[ARG_value].u_obj != mp_const_none && (mode == PIN_MODE_OUT || pin_is_output(self))) {
        pin_set(self, mp_obj_is_true(args[ARG_value].u_obj));
    }
    if (mode != -1) {
        pin_set_mode(self, mode);
    }
    return mp_const_none;
}

mp_obj_t mp_pin_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    (void)type;
    mp_arg_check_num(n_args, n_kw, 1, MP_OBJ_FUN_ARGS_MAX, true);
    const machine_pin_obj_t *self = pin_find(args[0]);
    if (n_args > 1 || n_kw > 0) {
        mp_map_t kw_args;
        mp_map_init_fixed_table(&kw_args, n_kw, args + n_args);
        machine_pin_obj_init_helper(self, n_args - 1, args + 1, &kw_args);
    }
    return MP_OBJ_FROM_PTR(self);
}

// pin() / pin(x)
static mp_obj_t machine_pin_call(mp_obj_t self_in, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 0, 1, false);
    const machine_pin_obj_t *self = MP_OBJ_TO_PTR(self_in);
    if (n_args == 0) {
        return MP_OBJ_NEW_SMALL_INT(pin_get(self));
    }
    pin_set(self, mp_obj_is_true(args[0]));
    return mp_const_none;
}

static mp_obj_t machine_pin_obj_init(size_t n_args, const mp_obj_t *args, mp_map_t *kw_args) {
    return machine_pin_obj_init_helper(MP_OBJ_TO_PTR(args[0]), n_args - 1, args + 1, kw_args);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(machine_pin_init_obj, 1, machine_pin_obj_init);

static mp_obj_t machine_pin_value(size_t n_args, const mp_obj_t *args) {
    return machine_pin_call(args[0], n_args - 1, 0, args + 1);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(machine_pin_value_obj, 1, 2, machine_pin_value);

static mp_obj_t machine_pin_on(mp_obj_t self_in) {
    pin_set(MP_OBJ_TO_PTR(self_in), 1);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(machine_pin_on_obj, machine_pin_on);

static mp_obj_t machine_pin_off(mp_obj_t self_in) {
    pin_set(MP_OBJ_TO_PTR(self_in), 0);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(machine_pin_off_obj, machine_pin_off);

static mp_obj_t machine_pin_toggle(mp_obj_t self_in) {
    const machine_pin_obj_t *self = MP_OBJ_TO_PTR(self_in);
    pin_set(self, !pin_get(self));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(machine_pin_toggle_obj, machine_pin_toggle);

static const mp_rom_map_elem_t machine_pin_locals_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&machine_pin_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_value), MP_ROM_PTR(&machine_pin_value_obj) },
    { MP_ROM_QSTR(MP_QSTR_on), MP_ROM_PTR(&machine_pin_on_obj) },
    { MP_ROM_QSTR(MP_QSTR_off), MP_ROM_PTR(&machine_pin_off_obj) },
    { MP_ROM_QSTR(MP_QSTR_toggle), MP_ROM_PTR(&machine_pin_toggle_obj) },
    { MP_ROM_QSTR(MP_QSTR_IN), MP_ROM_INT(PIN_MODE_IN) },
    { MP_ROM_QSTR(MP_QSTR_OUT), MP_ROM_INT(PIN_MODE_OUT) },
};
static MP_DEFINE_CONST_DICT(machine_pin_locals_dict, machine_pin_locals_dict_table);

// Virtual pin protocol, used by machine.Signal
static mp_uint_t machine_pin_ioctl(mp_obj_t self_in, mp_uint_t request, uintptr_t arg, int *errcode) {
    (void)errcode;
    const machine_pin_obj_t *self = MP_OBJ_TO_PTR(self_in);
    switch (request) {
        case MP_PIN_READ:
            return pin_get(self);
        case MP_PIN_WRITE:
            pin_set(self, arg);
            return 0;
    }
    return -1;
}

static const mp_pin_p_t machine_pin_pin_p = {
    .ioctl = machine_pin_ioctl,
};

MP_DEFINE_CONST_OBJ_TYPE(
    machine_pin_type,
    MP_QSTR_Pin,
    MP_TYPE_FLAG_NONE,
    make_new, mp_pin_make_new,
    print, machine_pin_print,
    call, machine_pin_call,
    protocol, &machine_pin_pin_p,
    locals_dict, &machine_pin_locals_dict
    );
