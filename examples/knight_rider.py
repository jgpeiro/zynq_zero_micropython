# Sweep LED1..LED4 back and forth; hold KEY1 to pause.
import time
from machine import Pin, Signal

leds = [Pin("LED%d" % i, Pin.OUT, value=0) for i in range(1, 5)]
key = Signal(Pin("KEY1", Pin.IN), invert=True)   # KEY1 reads 0 when pressed

order = [0, 1, 2, 3, 2, 1]
i = 0
while True:
    if not key.value():
        for n, led in enumerate(leds):
            led.value(n == order[i])
        i = (i + 1) % len(order)
    time.sleep_ms(80)
