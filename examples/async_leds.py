# Each PL LED blinks at its own rate, using asyncio tasks.
import asyncio
from machine import Pin

async def blink(name, period_ms):
    led = Pin(name, Pin.OUT)
    while True:
        led.toggle()
        await asyncio.sleep_ms(period_ms // 2)

async def main():
    for name, period in (("LED1", 100), ("LED2", 250), ("LED3", 500), ("LED4", 1000)):
        asyncio.create_task(blink(name, period))
    await asyncio.sleep(3600)

asyncio.run(main())
