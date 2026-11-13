# 06 The built-in USB updater

**Status: read from the code only. Not tried. Do not rely on it yet.**

The stock MStar updater is present in the application and reachable from the
"Software Update?" page ([05](05-hidden-menus-and-ir-codes.md)). It is also
wired to commands on the serial debug console.

## What the code does

Functions (RAM addresses): set-up 0x25f24e, file search 0x24ddec, load and
check 0x24d7ea, burn 0x2c9eca.

1. Looks for a file named **`MERGE.BIN`** in the root of the USB drive.
2. Accepts it only if its size is at most the flash size minus 0x20000
   (0x3e0000 bytes), and reads it into DRAM.
3. Integrity: a CRC-32 with polynomial 0x04C11DB7 over the **whole file** must
   come out as 0, which means the file carries its own CRC at the end
   (`CRC32 Integrity Check pass !!`).
4. Identity: the word at file offset 0x21180 must be 0x55aa5678, otherwise
   `Error: Unknown TV software`. That is flash offset 0x21180 in a dump, so
   `MERGE.BIN` is laid out as a flash image starting at offset 0.
5. Compares file and flash in 64 KB blocks; erases, writes and verifies only
   the blocks that differ; then reboots. It lifts the chip's write protection
   itself.
6. On an erase, write or verify error it erases the first block of the range
   and stops in an endless loop.

## What is not known yet

- The exact CRC convention for the trailing bytes (byte order, and whether
  the trailing CRC bytes are themselves written to flash).
- Whether a file shorter than the full flash is handled as expected.
- Behaviour of the progress screen and of the reboot at the end.

## Why it matters, and why to be careful

It would allow changing firmware without opening the globe. But it rewrites
the only firmware chip from inside the running firmware, with no second copy,
and step 6 means a failed update leaves the unit unable to start. Treat it as
something to try only when the clip and a verified pristine dump are at hand
([04](04-flashing-with-a-raspberry-pi.md)).

A sensible first experiment is a `MERGE.BIN` whose contents equal what is
already on the chip: every block compares equal, so the updater should
exercise its file, CRC and identity checks and then write nothing.
