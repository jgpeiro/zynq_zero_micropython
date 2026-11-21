# LED1 (PL, AXI GPIO) and LED0 (PS, MIO9) blinking at different rates.
# Run with:  mpremote connect <port> run examples/blink.py   (Ctrl-C to stop)
import time
from machine import Pin

led0 = Pin("LED0", Pin.OUT)
led1 = Pin("LED1", Pin.OUT)

t = 0
while True:
    led1.toggle()                 # every 50 ms -> 10 Hz
    if t % 10 == 0:
        led0.toggle()             # every 500 ms -> 1 Hz
    t += 1
    time.sleep_ms(50)
