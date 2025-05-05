"""
Async driver for MKS Robin Wi-Fi module (Marlin 2.x)
---------------------------------------------------
A fully-asynchronous, high-level Python client that communicates with the
MKS Wi-Fi module over its raw TCP socket (default port 8080).

Fixes & improvements over the earlier prototype
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Properly consumes the **two-stage** MKS protocol reply: the module sends an
  initial `ok` line **followed by the payload line** (if any). The original
  implementation returned only the first line, which meant diagnostic
  queries (`M27`, `M991`, `M992`, `M997`, …) never reached the caller.
* Added context-manager support (`async with MKSPrinter(...) as p:`) so that
  connections are closed automatically.
* Extended **G-code enum** with additional commands (`PAUSE`, `ABORT`,
  `SWITCH_FS`) and made it inherit from `str` so that enum values can be
  passed directly to `send()`.
* Improved regular expressions to cope with floating-point temperatures and
  optional whitespace.
* Streaming file upload (`upload_gcode`) now reads the file **line-by-line**
  instead of loading the entire file in memory and stops cleanly on error.
* Added helper methods for starting, pausing and aborting prints.
* All public methods raise meaningful exceptions and write structured debug
  output via `logging`.

The protocol reference used is Renzo Mischianti's article *“MKS WiFi for
Makerbase Robin: communication protocol and Cura plugin”* (see
https://mischianti.org), which confirms that every G-code request is echoed
with `ok` first, followed by an optional information line.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
import time
from enum import Enum
from pathlib import Path
from typing import Final, Optional

__all__ = [
    "MKSPrinter",
]

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# Pre‑compiled regular expressions for parsing Wi‑Fi replies
# ---------------------------------------------------------------------------

TEMP_RE: Final = re.compile(
    r"T:\s*(\d+\.?\d*)/(\d+\.?\d*).*B:\s*(\d+\.?\d*)/(\d+\.?\d*)"
)
PROG_RE: Final = re.compile(r"M27\s+(\d+)")
TIME_RE: Final = re.compile(r"M992\s+([\d:]+)")
STATE_RE: Final = re.compile(r"M997\s+(\w+)")


class MKSPrinter:
    """Async client for the MKS Wi-Fi (TCP) protocol."""

    def __init__(self, host: str, port: int = 8080, *, read_timeout: float = 5.0):
        self.host, self.port = host, port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.read_timeout = read_timeout
        self.latest: dict[str, object] = {}

    class GCodes(str, Enum):
        """Minimal set of G-codes understood by the MKS Wi-Fi firmware."""

        TEMP_QUERY = "M991"  # Like Marlin M105
        PROGRESS = "M27"  # SD/USB print progress (percentage)
        ELAPSED = "M992"  # Elapsed print time (hh:mm:ss)
        STATE = "M997"  # IDLE / PRINTING / PAUSE

        # SD/USB file management
        SD_BEGIN = "M28 {name}"  # Start upload (open file for write)
        SD_END = "M29"  # Finish upload (close file)
        SD_SELECT = "M23 {name}"  # Select file for printing
        SD_START = "M24"  # Start/Resume print
        SD_PAUSE = "M25"  # Pause print
        SD_ABORT = "M26"  # Abort print (MKS re‑uses 26 instead of Marlin M524)

        SWITCH_FS = "M998"  # Toggle SD ⟷ USB

    # ---------------------------------------------------------------------
    # Async context manager helpers
    # ---------------------------------------------------------------------

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    # ---------------------------------------------------------------------
    # Connection management
    # ---------------------------------------------------------------------

    async def connect(self) -> None:
        """Open a TCP connection to the Wi-Fi module."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        logger.debug("Connected to %s:%s", self.host, self.port)

    async def close(self) -> None:
        """Close the TCP connection (if open)."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            logger.debug("Connection closed")

    # ---------------------------------------------------------------------
    # Low‑level I/O helpers
    # ---------------------------------------------------------------------

    async def _send_raw(self, gcode: GCodes) -> None:
        if not self.writer:
            raise RuntimeError("Not connected")
        logger.debug(">> %s", gcode.strip())
        self.writer.write(f"{gcode.strip()}\r\n".encode())
        await self.writer.drain()

    async def _read_raw(self) -> str:
        if not self.reader:
            raise RuntimeError("Not connected")
        raw = await asyncio.wait_for(self.reader.readline(), self.read_timeout)
        text = raw.decode(errors="ignore").strip()
        logger.debug("<< %s", text)
        return text

    async def _read_response(self) -> str:
        """Return the first payload line (skipping leading 'ok')."""
        first = await self._read_raw()
        if first.lower().startswith("error"):
            raise RuntimeError(first)

        if first == "ok":
            # A normal MKS response has an extra payload line after *ok*
            try:
                second = await self._read_raw()
                if second and second != "ok":
                    return second
                return ""  # Command with no additional payload
            except asyncio.TimeoutError:
                return ""
        return first  # Some commands may reply without the leading ok

    async def send(self, gcode: GCodes) -> str:
        """Send *gcode* and return the payload line (empty if none)."""
        await self._send_raw(gcode)
        try:
            return await self._read_response()
        except asyncio.TimeoutError:
            logger.warning("Timeout while waiting for reply to %s", gcode)
            return ""

    # ---------------------------------------------------------------------
    # High‑level helpers
    # ---------------------------------------------------------------------

    async def poll(self, seconds: float = 0.5) -> dict[str, object]:
        """Retrieve temperatures, progress, elapsed time and state."""
        fresh: dict[str, object] = {}

        if m := TEMP_RE.search(await self.send(self.GCodes.TEMP_QUERY)):
            fresh["temps"] = {
                "T": float(m[1]),
                "Tset": float(m[2]),
                "B": float(m[3]),
                "Bset": float(m[4]),
            }

        if m := PROG_RE.search(await self.send(self.GCodes.PROGRESS)):
            fresh["progress"] = int(m[1])

        if m := TIME_RE.search(await self.send(self.GCodes.ELAPSED)):
            fresh["elapsed"] = m[1]

        if m := STATE_RE.search(await self.send(self.GCodes.STATE)):
            fresh["state"] = m[1]

        if fresh:
            fresh["stamp"] = dt.datetime.now().isoformat(timespec="seconds")
            self.latest = fresh

        time.sleep(seconds)

        return fresh

    # ---------------------------------------------------------------------
    # SD/USB file helpers
    # ---------------------------------------------------------------------

    async def upload_gcode(self, path: Path) -> None:
        """Upload *path* to the printer via M28/M29."""
        if not path.is_file():
            raise FileNotFoundError(path)

        # Open file on printer for writing
        ack = await self.send(self.GCodes.SD_BEGIN.format(name=path.name))
        if ack.lower().startswith("error"):
            raise RuntimeError(ack)

        # Stream file line‑by‑line
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    # Firmware limit ≈128 chars
                    resp = await self.send(line.rstrip()[:127])
                    if resp.lower().startswith("error"):
                        raise RuntimeError(resp)
        finally:
            await self.send(self.GCodes.SD_END)

    # ---------------------------------------------------------------------
    # Print‑control helpers
    # ---------------------------------------------------------------------

    async def start_print(self, filename: str) -> None:
        """Select *filename* and begin (or resume) printing it.

        This helper folds the two-step Marlin/MKS SD‑print sequence into one
        call:

        1. ``M23 <filename>`` - select the file on the active storage
           (SD or USB, depending on the last ``M998``).
        2. ``M24`` - start or resume printing the selected file.

        Parameters
        ----------
        filename : str
            Name (or relative path) of the G-code file to print.  The file must
            already exist on the printer's storage (e.g. uploaded via
            :pymeth:`upload_gcode`).

        Raises
        ------
        RuntimeError
            If the printer reports an error in response to either command.
        """
        await self.send(self.GCodes.SD_SELECT.format(name=filename))
        await self.send(self.GCodes.SD_START)

    async def pause(self) -> None:
        """Pause the current SD/USB print (Marlin ``M25``).

        If no print is running the firmware ignores the command and simply
        returns ``ok``.
        """
        await self.send(self.GCodes.SD_PAUSE)

    async def abort(self) -> None:
        """Cancel the active SD/USB print immediately (MKS ``M26``).

        The printer stops motion, flushes the job, and changes its state to
        ``IDLE``.  Heater shutdown behaviour follows the firmware's
        configuration (typically heaters are turned off).
        ```
        """
        await self.send(self.GCodes.SD_ABORT)
