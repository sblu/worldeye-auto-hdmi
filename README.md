# Gakken WorldEye: power on straight to HDMI

The Gakken WorldEye is a projector globe (an MStar-based pico projector inside
a sphere). Stock behaviour makes it awkward for an unattended display: applying
power only puts it in standby, the remote's Power key is needed to start it,
and it always starts on the USB source page, so two more key presses are
needed to get an HDMI picture.

This repository documents a two-instruction firmware patch that changes that:

| | Stock | Patched |
|---|---|---|
| DC power applied | red LED, standby | starts by itself, green LED |
| Source after start | USB source page | live HDMI |
| Remote, menus, USB playback | work | still work |
| Remote Power key | standby / wake | unchanged |

It was developed and tested on one unit in November 2026 (firmware build
"Nov 18 2013, 11:47:24", board `BD_MST021B_10ALG_11313_64M`).

**No firmware is included here.** You dump your own unit, the tool patches
your dump, and you write the result back. The same clip that reads the chip
also restores it, and no soldering is needed.

## What you need

- A Raspberry Pi with the 40-pin header (3B used here) and a spare microSD card
- A SOIC-8 test clip with jumper leads (the kind sold with CH341A programmers)
- One 1 kΩ resistor (anything from 470 Ω to 2.2 kΩ)
- A PC with Python 3.10+ and 7-Zip (`7z`) to build the patched image
- A multimeter

Do not use a bare CH341A "black" programmer on this chip: the common version
drives its data lines at 5 V and the flash is a 3.3 V part.

## The short version

1. [Open the globe and find the flash chip](docs/01-hardware.md).
2. [Wire the clip to the Pi and take three identical dumps](docs/04-flashing-with-a-raspberry-pi.md). Keep them safe.
3. Build the patched images on the PC (`mkdir -p images` first):
   ```
   python -m tools.fwimage patch dumps/pristine_1.bin images/test0_repack_only.bin
   python -m tools.fwimage patch dumps/pristine_1.bin images/test1_poweron.bin poweron
   python -m tools.fwimage patch dumps/pristine_1.bin images/test2_poweron_hdmi.bin poweron hdmi
   ```
   The tool refuses to run if your dump is not the firmware version it knows.
4. [Write them one at a time](docs/04-flashing-with-a-raspberry-pi.md#writing), testing the globe after each. `test0` changes no behaviour and only proves the repacking works on your unit.
5. To go back to stock, write your own pristine dump with the same script.

## Read this before you start

- This can leave the unit unable to start until you rewrite the chip. The
  procedure is built so that you always can, but only if your pristine dumps
  are good. Do not skip the three-identical-dumps step or the staged test images.
- The unit is out of production. Decide for yourself whether the risk is worth it.
- Everything here was done on one unit. Other hardware revisions or firmware
  builds may differ; the tool checks the bytes it expects and stops if they
  are not there.

## Contents

| Document | What is in it |
|---|---|
| [01 Hardware](docs/01-hardware.md) | Chips, connectors, what was identified on the board |
| [02 Firmware layout](docs/02-firmware-layout.md) | Flash map, boot chain, image format, checksum, settings store, reverse-engineering setup |
| [03 The patches](docs/03-patches.md) | What the firmware does at start-up and the two instructions that change |
| [04 Flashing with a Raspberry Pi](docs/04-flashing-with-a-raspberry-pi.md) | Wiring diagram, dumping, the write-protect resistor, writing, restoring |
| [05 Hidden menus and IR codes](docs/05-hidden-menus-and-ir-codes.md) | Key sequences, the full IR code table, Flipper Zero file |
| [06 USB updater](docs/06-usb-updater.md) | The built-in `MERGE.BIN` updater: what the code shows, not yet tried |
| [07 Troubleshooting and open questions](docs/07-troubleshooting-and-open-questions.md) | Read glitches, a weak flash bit, an intermittent start-up fault, things not yet known |

Tools: `tools/fwimage.py` (unpack / patch / repack, with tests in `tests/`),
`tools/pi/` (scripts that run on the Pi), `flipper/WorldEye.ir`,
`ghidra_scripts/` (headless helper scripts used during the analysis).

## Licence

MIT for the tools and documentation (see `LICENSE`). The WorldEye firmware is
not part of this repository.
