# Python modules frozen into the firmware
include("$(MPY_DIR)/extmod/asyncio")
module("fft.py", base_path="modules")
module("hdmi.py", base_path="modules")
module("lvhdmi.py", base_path="modules")
