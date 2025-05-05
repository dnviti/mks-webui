import asyncio
import time
from pathlib import Path
from core.driver.mkswifi import MKSPrinter


async def main():
    async with MKSPrinter("192.168.128.67") as p:
        await p.poll()
        print(p.latest)
        
        #await p.upload_gcode(path=Path("~/Downloads/bowl-shape_PLA_8h24m.gcode"))
        #await p.send(gcode=GC.TEMP_QUERY)
        #await p._exec(MKSPrinter.GCodes.SD_START)   # begin printing
        time.sleep(1)

asyncio.run(main())
