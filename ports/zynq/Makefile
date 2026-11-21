################################################################################
# MicroPython port for the Zynq-7000 (ZYNQ ZERO board), bare metal on CPU0.
#
# This port lives outside the MicroPython tree:
#   make MICROPY_DIR=/path/to/micropython      (default: ../../micropython)
#
# Options:
#   HEAP_SIZE=16M   GC heap in DDR
#   MMU=0           I-cache only (no MMU / D-cache / L2), for debugging
#   L2=0            leave the 512 KB L2 cache off
#   QEMU=1          build for qemu-system-arm -M xilinx-zynq-a9 (see `make run`)
#   DEBUG=1         -O0 -g
################################################################################

MICROPY_DIR ?= ../../micropython
ifeq ($(wildcard $(MICROPY_DIR)/py/mkenv.mk),)
$(error MicroPython not found at $(MICROPY_DIR); run ./build.sh fw or set MICROPY_DIR)
endif

QEMU ?= 0
ifeq ($(QEMU),1)
BUILD ?= build-qemu
else
BUILD ?= build
endif

include $(MICROPY_DIR)/py/mkenv.mk

CROSS_COMPILE ?= arm-none-eabi-

QSTR_DEFS = qstrdefsport.h

# LVGL v9 + MicroPython binding as user C modules (../../usermods):
#   lv_binding_micropython/ (with lvgl/ inside), lvgl_hdmi/ (display driver), lv_conf.h
# LVGL=0 builds without it.
LVGL ?= 1
ifeq ($(LVGL),1)
USERMODS_DIR ?= $(abspath ../../usermods)
ifeq ($(wildcard $(USERMODS_DIR)/lv_binding_micropython/lvgl/lvgl.h),)
$(error LVGL not found in $(USERMODS_DIR); run ./build.sh fw, or build with LVGL=0)
endif
USER_C_MODULES = $(USERMODS_DIR)
LV_CONF_PATH = $(USERMODS_DIR)/lv_conf.h
endif

# Frozen Python modules (asyncio); builds mpy-cross from the MicroPython tree
FROZEN_MANIFEST ?= manifest.py
MICROPY_ROM_TEXT_COMPRESSION ?= 1

include $(TOP)/py/py.mk
include $(TOP)/extmod/extmod.mk

HEAP_SIZE  ?= 16M
STACK_SIZE ?= 256K
MMU        ?= 1
L2         ?= 1

ARCH = -mcpu=cortex-a9 -marm -mfpu=vfpv3 -mfloat-abi=softfp

INC += -I.
INC += -I$(TOP)
INC += -I$(BUILD)

CFLAGS += $(INC) $(ARCH) -Wall -Wpointer-arith -Wdouble-promotion -Wfloat-conversion -Werror \
	-std=gnu99 $(COPT) -ffunction-sections -fdata-sections -fno-common \
	-mno-unaligned-access -DZYNQ_MMU=$(MMU) -DZYNQ_L2=$(L2)
CFLAGS += $(CFLAGS_EXTRA)

ifeq ($(QEMU),1)
# QEMU's xilinx-zynq-a9 has no PL: point the AXI GPIO at a DDR scratch area so
# the Pin code paths can still be exercised (read back with machine.mem32).
CFLAGS += -DZYNQ_AXI_GPIO_BASE=0x1FF00000u
endif

ifeq ($(LVGL),1)
# LVGL and its generated binding are third-party code: keep their warnings
# visible but not fatal (the port's own sources stay -Werror)
$(BUILD)/lv_binding_micropython/%.o $(BUILD)/$(BUILD)/lvgl/%.o: \
	CFLAGS += -Wno-error -Wno-double-promotion -Wno-float-conversion
endif

ifeq ($(DEBUG), 1)
COPT = -O0 -g
else
COPT = -Os -g -DNDEBUG
endif

AFLAGS = $(ARCH)

LDFLAGS += -nostdlib -T zynq.ld --gc-sections -Map=$(@:.elf=.map) \
	--defsym=HEAP_SIZE=$(HEAP_SIZE) --defsym=STACK_SIZE=$(STACK_SIZE)
LIBS = $(shell $(CC) $(ARCH) -print-libgcc-file-name)

SRC_C = \
	main.c \
	mmu.c \
	uart.c \
	mphalport.c \
	machine_pin.c \
	modfft.c \
	modhdmi.c \
	modzynq.c \
	shared/libc/string0.c \
	shared/readline/readline.c \
	shared/runtime/gchelper_generic.c \
	shared/runtime/interrupt_char.c \
	shared/runtime/pyexec.c \
	shared/runtime/stdout_helpers.c \
	shared/runtime/sys_stdio_mphal.c \

SRC_S = startup.S

LIBM_SRC_C = $(SRC_LIB_LIBM_DBL_C) $(SRC_LIB_LIBM_DBL_SQRT_HW_C)

OBJ += $(PY_O)
OBJ += $(addprefix $(BUILD)/, $(SRC_C:.c=.o))
OBJ += $(addprefix $(BUILD)/, $(SRC_S:.S=.o))
OBJ += $(addprefix $(BUILD)/, $(LIBM_SRC_C:.c=.o))

# Sources scanned for qstrs
SRC_QSTR += $(SRC_C) $(LIBM_SRC_C)

all: $(BUILD)/firmware.elf

$(BUILD)/firmware.elf: zynq.ld $(OBJ)
	$(ECHO) "LINK $@"
	$(Q)$(LD) $(LDFLAGS) -o $@ $(OBJ) $(LIBS)
	$(Q)$(SIZE) $@

# REPL in QEMU (UART1 on this terminal). Quit with Ctrl-A x.
QEMU_ARGS = -M xilinx-zynq-a9 -m 512M -nographic -serial null -serial mon:stdio -no-reboot
run: $(BUILD)/firmware.elf
	qemu-system-arm $(QEMU_ARGS) -kernel $<

.PHONY: run

include $(TOP)/py/mkrules.mk
