import asyncio
from pathlib import Path
from core.driver.mkswifi import MKSPrinter


async def main():
    async with MKSPrinter("192.168.128.67") as p:
        while True:
            await p.poll()
            print(p.latest)

        # await p.upload_gcode(path=Path("~/Downloads/bowl-shape_PLA_8h24m.gcode"))
        # await p._exec(MKSPrinter.GCodes.SD_START)   # begin printing

asyncio.run(main())
