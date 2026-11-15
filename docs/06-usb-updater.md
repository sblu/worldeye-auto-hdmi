# 06 The built-in USB updater

**Status: tested on one unit (2026-11-15).** A write-nothing trial, a real
update back to the stock application, and a real update to the patched
firmware all worked, and clip dumps afterwards matched the files byte for
byte. Even so, read "What the code does" first: a failed update leaves the
unit unable to start, so have the clip and a verified dump at hand
([04](04-flashing-with-a-raspberry-pi.md)).

The stock MStar updater is present in the application and reachable from the
"Software Update?" page ([05](05-hidden-menus-and-ir-codes.md): Up, Down,
Left, Right on the source page). It is also wired to commands on the serial
debug console.

## What the code does

Functions (RAM addresses): set-up 0x25f24e, file search 0x24ddec, load and
check 0x24d7ea, burn 0x2c9eca.

1. Looks for **`MERGE.BIN`** (name compared without regard to case) in the
   root directory of the USB drive.
2. Size must be at most flash size minus 0x20000 = **0x3e0000** bytes. The
   file is read into DRAM.
3. **Integrity:** the SoC's CRC engine (polynomial 0x04C11DB7, seed 0) is run
   over the whole file and the result must be 0. So the file ends with the
   CRC of everything before it, high byte first. This is the same engine and
   polynomial the bootloader uses for the application.
4. **Identity:** the word at file offset 0x21180 must be 0x55aa5678
   (`Error: Unknown TV software` otherwise). The file is therefore a flash
   image starting at flash offset 0.
5. **Compare:** file and flash are compared in 2 KB steps. Each 64 KB block
   that contains a difference is marked.
   - If nothing differs: reports success and reboots. **Nothing is erased.**
   - If anything differs: **block 0 (the first half of the bootloader) and
     the file's last block are marked as well**, whatever their contents.
6. **Burn:** write protection is lifted, marked blocks are erased (64 KB
   each, with a blank check), rewritten from the file, then the *whole* file
   range is verified against flash. Protection is restored and the unit reboots.
7. **On any erase, write or verify error: it erases block 0 and stops in an
   endless loop.** The unit will not start again until the chip is rewritten
   with a programmer.

A file that fails steps 1 to 4 is rejected before anything is written, and
the unit does not reboot. Points 5 and 7 are the reason for caution: every
real update rewrites part of the bootloader, and a failed one deliberately
removes it. Writing with the clip ([04](04-flashing-with-a-raspberry-pi.md))
never touches the bootloader, so it remains the lower-risk route; the USB
route is for when opening the unit again is the bigger nuisance.

## Building a MERGE.BIN

`tools/mergebin.py` builds the file from a full 4 MB flash image (a dump of
your chip, or that dump with the patched application in it):

```
python -m tools.mergebin build images/test2_poweron_hdmi.bin usb/MERGE.BIN
python -m tools.mergebin plan  dumps/current_1.bin usb/MERGE.BIN
```

- The file is `flash[0 : 0x39fffc]` followed by four CRC bytes, 0x3a0000
  bytes in total. On this firmware real data ends at 0x39b563 and the bytes up
  to 0x3a0000 are erased, so the CRC lands in unused space. The settings
  sectors (0x3c0000 and up) are not in the file and are not touched.
- `plan` simulates step 5 against a dump of your chip and lists the blocks
  the updater would erase.

## Running an update

1. USB stick formatted FAT32, `MERGE.BIN` in the root directory. The stick
   used in the tests was a 16 GB SanDisk with the file system directly on the
   device (no partition table); a partitioned stick has not been tried.
2. Power the unit, insert the stick, go to the source page (Back), then press
   Up, Down, Left, Right. The "Software Update?" page appears with the
   firmware build date and an empty bar.
3. Press **OK**.
4. Leave it alone until it has restarted by itself. Do not remove power or
   the stick.

What the screen shows (timings from video of the tested unit):

| | File identical to the chip | File differs (14 blocks rewritten) |
|---|---|---|
| "Software Update?" page stays | about 15 s, bar stays empty | about 3 s |
| Then | picture goes away | small window "Software Updating... NN %" for about 8 s; its background colour shifts as it runs |
| Dark | about 13 s | about 25 s |
| Start-up animation | yes | yes |
| Total until a picture is back | about 45 s | about 45 s |

After the restart the unit comes up on, not in standby, even with stock
firmware. The firmware's normal power-on behaviour applies from the next
time DC power is applied.

## Test record

| Trial | Chip before | File | Predicted by `plan` | Result |
|---|---|---|---|---|
| 0 | patched, plus the file's 4 CRC bytes written with the clip | patched | nothing differs | accepted, restarted, no "Updating" window; dump unchanged below the settings area |
| 1 | as after trial 0 | stock | blocks 0x00, 0x02–0x0d, 0x39 | "Updating" window, restarted, stock behaviour |
| 2 | stock | patched | blocks 0x00, 0x02–0x0d, 0x39 | restarted, starts on HDMI; dump equals the file over its whole length |

Trial 0 is worth repeating on any other unit before a real update: it proves
the file is accepted without the updater writing anything. It needs the
file's four CRC bytes on the chip first:

```
python -m tools.mergebin seed images/test2_poweron_hdmi.bin usb/MERGE.BIN images/seed.bin
# on the Pi, clip and resistor on:
REGION_START=0x390000 REGION_END=0x3a0000 ./writeapp.sh ~/images/seed.bin
```

Then check with `plan` on a fresh dump that it prints "nothing differs".

**A weak flash bit spoils trial 0.** If a byte on the chip reads differently
from one read to the next ([07](07-troubleshooting-and-open-questions.md)),
the updater may see a difference and do a real update instead. On the tested
unit the sector holding that byte was rewritten with the clip first
(`REFRESH=1`, see 07), after which it read steadily.

## What is still unknown

- Behaviour with a partitioned stick, exFAT, or sticks larger than 16 GB.
- What the unit shows when it rejects a file (not provoked in the tests).
- Whether other file sizes work; 0x3a0000 was chosen as a multiple of 64 KB.

## Why not just publish a MERGE.BIN?

Because it would be the firmware itself. Anyone following this needs their
own dump to build one, which means using the clip at least once anyway.
