"""Unpack, patch and repack the WorldEye main application image.

Flash layout of the image (all offsets are flash offsets):

  0x20000  header: u32 src (0x20080), u32 RAM base (0x200000), u32 RAM end,
           u32 flash end, u32 0, u32 CRC
  0x20080  0x3800-byte uncompressed stub, copied to RAM 0x200000
           (stub+0x1147 = BE AD DE magic, stub+0x114a = u32 image length)
  0x23880  raw deflate stream, inflated by sBoot to RAM 0x203800
  end-6    u32 inflated length, then two bytes sBoot does not read

sBoot verifies CRC-32/MPEG-2 with init 0 over [0x20080, flash end) against
the header word at 0x20014, then inflates. Inflate stops at the end of the
final deflate block, so a shorter stream can be zero-padded up to the
trailer and every length field stays as the factory wrote it.

RAM address of an application byte = 0x200000 + (flash offset - 0x20080)
for the stub, and 0x203800 + offset into the inflated data.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

HEADER = 0x20000
STUB_LEN = 0x3800
RAM_BASE = 0x200000
APP_RAM = RAM_BASE + STUB_LEN
TRAILER_LEN = 6


@dataclass(frozen=True)
class Patch:
    name: str
    addr: int          # RAM address
    old: bytes
    new: bytes
    why: str


# b.movi r7,imm is the two bytes 98 E0|imm (AEON R2, 16-bit form).
PATCHES = {
    "poweron": Patch(
        "poweron", 0x25748C, bytes.fromhex("98e1"), bytes.fromhex("98e2"),
        "power-on mode constant 1 (OFF: go to standby on AC boot) -> 2 (ON)"),
    "hdmi": Patch(
        "hdmi", 0x257559, bytes.fromhex("98e6"), bytes.fromhex("98e4"),
        "boot input source constant 6 (USB 1) -> 4 (HDMI)"),
}


def crc32_mpeg2(data: bytes, crc: int = 0) -> int:
    """CRC-32, polynomial 0x04C11DB7, MSB first, init 0, no final XOR."""
    table = _crc_table()
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ table[(crc >> 24) ^ b]
    return crc


_TABLE: list[int] | None = None


def _crc_table() -> list[int]:
    global _TABLE
    if _TABLE is None:
        t = []
        for i in range(256):
            c = i << 24
            for _ in range(8):
                c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
            t.append(c)
        _TABLE = t
    return _TABLE


@dataclass
class Image:
    src: int
    ram_base: int
    flash_end: int
    crc: int
    stub: bytes
    app: bytes            # inflated
    stream_len: int       # bytes of deflate stream actually consumed
    trailer: bytes

    @property
    def comp_start(self) -> int:
        return self.src + STUB_LEN

    @property
    def comp_room(self) -> int:
        """Bytes available for the deflate stream before the trailer."""
        return self.flash_end - TRAILER_LEN - self.comp_start


def unpack(flash: bytes) -> Image:
    src, ram_base, ram_end, flash_end, _zero, crc = struct.unpack_from("<6I", flash, HEADER)
    if ram_base != RAM_BASE or src != HEADER + 0x80:
        raise ValueError(f"unexpected header: src={src:#x} ram={ram_base:#x}")
    if ram_end - ram_base != flash_end - src:
        raise ValueError("header RAM span and flash span disagree")
    stub = flash[src:src + STUB_LEN]
    if stub[0x1147:0x114A] != b"\xbe\xad\xde":
        raise ValueError("stub magic missing")
    if struct.unpack_from("<I", stub, 0x114A)[0] != flash_end - src:
        raise ValueError("stub length field disagrees with header")
    actual = crc32_mpeg2(flash[src:flash_end])
    if actual != crc:
        raise ValueError(f"image CRC mismatch: header {crc:#010x}, computed {actual:#010x}")
    comp = flash[src + STUB_LEN:flash_end - TRAILER_LEN]
    d = zlib.decompressobj(-15)
    app = d.decompress(comp)
    if not d.eof:
        raise ValueError("deflate stream did not terminate")
    trailer = flash[flash_end - TRAILER_LEN:flash_end]
    if struct.unpack_from("<I", trailer)[0] != len(app):
        raise ValueError("trailer length disagrees with inflated size")
    return Image(src, ram_base, flash_end, crc, stub, app, len(comp) - len(d.unused_data), trailer)


def apply_patch(app: bytes, patch: Patch) -> bytes:
    off = patch.addr - APP_RAM
    if app[off:off + len(patch.old)] != patch.old:
        raise ValueError(
            f"patch {patch.name}: expected {patch.old.hex()} at {patch.addr:#x}, "
            f"found {app[off:off + len(patch.old)].hex()}")
    return app[:off] + patch.new + app[off + len(patch.new):]


def deflate_best(data: bytes) -> bytes:
    """Smallest raw deflate stream we can make: zlib -9, and 7-Zip if present.

    zlib -9 comes out about 600 bytes larger than the factory stream; 7-Zip's
    deflate encoder is about 21 KB smaller, so 7-Zip is what makes it fit.
    """
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    best = c.compress(data) + c.flush()
    seven = shutil.which("7z") or shutil.which("7za")
    if seven:
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "app.bin"
            raw.write_bytes(data)
            gz = Path(td) / "app.gz"
            subprocess.run([seven, "a", "-tgzip", "-mx=9", "-mfb=258", "-mpass=15", str(gz), str(raw)],
                           check=True, stdout=subprocess.DEVNULL)
            cand = _strip_gzip(gz.read_bytes())
        if len(cand) < len(best):
            best = cand
    if zlib.decompress(best, -15) != data:
        raise RuntimeError("recompressed stream does not round-trip")
    return best


def _strip_gzip(g: bytes) -> bytes:
    if g[:2] != b"\x1f\x8b" or g[2] != 8:
        raise ValueError("not a gzip/deflate file")
    flg, o = g[3], 10
    if flg & 4:
        o += 2 + struct.unpack_from("<H", g, o)[0]
    if flg & 8:
        o = g.index(b"\0", o) + 1
    if flg & 16:
        o = g.index(b"\0", o) + 1
    if flg & 2:
        o += 2
    return g[o:-8]


def repack(flash: bytes, img: Image, app: bytes) -> bytes:
    """Return a full flash image with the application replaced by `app`.

    Only the deflate stream area and the header CRC word change.
    """
    if len(app) != len(img.app):
        raise ValueError("patched application must keep its length")
    stream = deflate_best(app)
    if len(stream) > img.comp_room:
        raise ValueError(f"stream is {len(stream)} bytes, only {img.comp_room} fit")
    out = bytearray(flash)
    s = img.comp_start
    out[s:s + img.comp_room] = stream + bytes(img.comp_room - len(stream))
    struct.pack_into("<I", out, HEADER + 0x14, crc32_mpeg2(bytes(out[img.src:img.flash_end])))
    result = bytes(out)
    check = unpack(result)          # re-validates CRC, lengths, inflate
    if check.app != app:
        raise RuntimeError("repacked image does not inflate to the patched application")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("unpack", help="write stub+application as one RAM image (load at 0x200000)")
    u.add_argument("flash", type=Path)
    u.add_argument("out", type=Path)
    p = sub.add_parser("patch", help="apply named patches and write a full flash image")
    p.add_argument("flash", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("patches", nargs="*", choices=sorted(PATCHES),
                   help="none = repack only (tests the recompression and CRC path by itself)")
    a = ap.parse_args(argv)

    flash = a.flash.read_bytes()
    img = unpack(flash)
    if a.cmd == "unpack":
        a.out.write_bytes(img.stub + img.app)
        print(f"wrote {a.out}: {len(img.stub) + len(img.app)} bytes, CRC {img.crc:#010x} verified")
        return 0
    app = img.app
    for name in a.patches:
        app = apply_patch(app, PATCHES[name])
        print(f"applied {name}: {PATCHES[name].why}")
    out = repack(flash, img, app)
    a.out.write_bytes(out)
    changed = sum(x != y for x, y in zip(flash, out))
    print(f"wrote {a.out}: {len(out)} bytes, {changed} flash bytes differ from input")
    print(f"sha256 {hashlib.sha256(out).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
