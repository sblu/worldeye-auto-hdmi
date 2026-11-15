"""Build a MERGE.BIN for the WorldEye's built-in USB updater, and predict what it will do.

What the updater does (application RAM 0x2c9eca, read from the code, see docs):

  * file MERGE.BIN in the USB drive's root, size <= 0x3e0000;
  * CRC-32, polynomial 0x04C11DB7, seed 0, over the WHOLE file must be 0,
    so the file ends with the CRC of everything before it;
  * the word at file offset 0x21180 must be 0x55aa5678;
  * the file is a flash image from offset 0. It is compared with the flash in
    2 KB steps; every 64 KB block containing a difference is marked. If
    anything at all differs, block 0 and the file's last block are marked too.
    Marked blocks are erased and rewritten, then the whole range is verified;
  * if nothing differs it reports success and reboots without erasing;
  * on an erase/write/verify error it erases block 0 (the bootloader) and hangs.

The file written here is flash[0 : size-4] + CRC. With size 0x3a0000 the four
CRC bytes land at 0x39fffc..0x39ffff, which is erased padding on this firmware,
and the settings sectors (0x3c0000 and up) are outside the file.

UNTESTED ON HARDWARE as of 2026-11-12. The CRC byte order is the main unknown;
a wrong order fails the updater's check before anything is written.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from tools.fwimage import crc32_mpeg2, unpack

BLOCK = 0x10000
STEP = 0x800
ID_OFFSET = 0x21180
ID_WORD = 0x55AA5678
MAX_SIZE = 0x3E0000
DEFAULT_SIZE = 0x3A0000


def build_merge(flash: bytes, size: int = DEFAULT_SIZE, little_endian_crc: bool = False) -> bytes:
    """MERGE.BIN made from a full flash image: flash[0:size-4] followed by the CRC."""
    if len(flash) != 4 * 1024 * 1024:
        raise ValueError("flash image must be 4 MB")
    if size % 16 or not (ID_OFFSET + 0x50 < size <= MAX_SIZE):
        raise ValueError(f"size {size:#x} must be a multiple of 16 and at most {MAX_SIZE:#x}")
    unpack(flash)                                   # header, magic, lengths, application CRC
    if struct.unpack_from("<I", flash, ID_OFFSET)[0] != ID_WORD:
        raise ValueError("identity word 0x55aa5678 missing at 0x21180")
    tail = flash[size - 4:size]
    if tail != b"\xff" * 4:
        raise ValueError(f"flash bytes at {size - 4:#x} are {tail.hex()}, not erased; "
                         "the CRC would overwrite data. Pick another size.")
    body = flash[:size - 4]
    crc = crc32_mpeg2(body)
    out = body + (crc.to_bytes(4, "little") if little_endian_crc else crc.to_bytes(4, "big"))
    if not little_endian_crc and crc32_mpeg2(out) != 0:
        raise RuntimeError("CRC residue is not zero")
    return out


def check_merge(merge: bytes) -> list[str]:
    """Problems the updater would reject the file for (empty list = looks acceptable)."""
    problems = []
    if not (0 < len(merge) <= MAX_SIZE):
        problems.append(f"size {len(merge):#x} is outside 1..{MAX_SIZE:#x}")
    if len(merge) > ID_OFFSET + 4 and struct.unpack_from("<I", merge, ID_OFFSET)[0] != ID_WORD:
        problems.append("identity word missing at 0x21180")
    if crc32_mpeg2(merge) != 0:
        problems.append("CRC over the whole file is not 0 (big-endian convention)")
    return problems


def predict_blocks(chip: bytes, merge: bytes) -> list[int]:
    """64 KB block numbers the updater would erase and rewrite, given the chip's contents."""
    marked: set[int] = set()
    for off in range(0, len(merge), STEP):
        if chip[off:off + STEP][:len(merge) - off] != merge[off:off + STEP]:
            marked.add(off >> 16)
    if marked:
        marked.add(0)
        marked.add((len(merge) - 1) >> 16)
    return sorted(marked)


def seed_image(chip: bytes, merge: bytes) -> bytes:
    """Chip image with the MERGE.BIN's trailing CRC bytes put in place.

    Writing this with the clip first makes a MERGE.BIN built from the same
    contents compare equal everywhere, so the updater runs all its checks and
    then writes nothing.
    """
    out = bytearray(chip)
    out[len(merge) - 4:len(merge)] = merge[-4:]
    return bytes(out)


def _ranges(blocks: list[int]) -> str:
    return ", ".join(f"{b:#04x} ({b * BLOCK:#08x})" for b in blocks) or "none"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build / inspect MERGE.BIN for the WorldEye USB updater")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="make MERGE.BIN from a full 4 MB flash image")
    b.add_argument("flash", type=Path)
    b.add_argument("out", type=Path)
    b.add_argument("--size", type=lambda s: int(s, 0), default=DEFAULT_SIZE)
    b.add_argument("--little-endian-crc", action="store_true",
                   help="append the CRC low byte first (only if the default is rejected by the unit)")
    p = sub.add_parser("plan", help="show which blocks the updater would rewrite on a given chip")
    p.add_argument("chip", type=Path, help="current dump of the chip")
    p.add_argument("merge", type=Path)
    s = sub.add_parser("seed", help="chip image with the CRC bytes in place, for a write-nothing trial")
    s.add_argument("chip", type=Path)
    s.add_argument("merge", type=Path)
    s.add_argument("out", type=Path)
    a = ap.parse_args(argv)

    if a.cmd == "build":
        out = build_merge(a.flash.read_bytes(), a.size, a.little_endian_crc)
        a.out.write_bytes(out)
        print(f"wrote {a.out}: {len(out):#x} bytes, CRC bytes {out[-4:].hex()} at {len(out) - 4:#x}")
        return 0
    chip, merge = a.chip.read_bytes(), a.merge.read_bytes()
    if a.cmd == "plan":
        for line in check_merge(merge):
            print("WARNING:", line)
        blocks = predict_blocks(chip, merge)
        print(f"blocks the updater would erase and rewrite: {_ranges(blocks)}")
        if not blocks:
            print("nothing differs: the updater should verify the file, write nothing, and reboot")
        elif 0 in blocks:
            print("note: block 0 is the bootloader; the updater always rewrites it when anything differs")
        return 0
    out = seed_image(chip, merge)
    a.out.write_bytes(out)
    print(f"wrote {a.out}: CRC bytes {merge[-4:].hex()} placed at {len(merge) - 4:#x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
