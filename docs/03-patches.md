# 03 The patches

Both changes are in the application's main initialisation function, RAM
address 0x2573aa (called from `main` at 0x261097). Addresses are RAM addresses
in the image described in [02](02-firmware-layout.md).

## What the stock code does

Boot type is stored at RAM 0x395320: 0 = `AC_BOOT` (power was applied),
1 = `DC_BOOT` (woken from standby). The firmware prints these names on its
serial console.

### 1. Power-on mode is forced to OFF

After loading the saved settings, the init function writes a constant over the
saved power-on mode:

```
00257484  c1800761   b.movhi r12,0x3b
00257488  fccc540c   b.addi  r6,r12,0x540c
0025748c  98e1       b.movi  r7,0x1           <-- POWERON_MODE_OFF
0025748e  ece60314   b.sw    0x314(r6),r7     ; RAM 0x3b5720 = 1
```

Then, on an AC boot:

| Mode | Console message | What happens |
|---|---|---|
| 2 | `POWERON_MODE_ON >>` | carries on into normal start-up |
| 1 | `POWERON_MODE_OFF >>`, `should go to standby!!!!!` | saves settings, `Power down`, hands over to the standby micro |
| 0 | `POWERON_MODE_SAVE >>` | standby only if it was in standby when power was lost |

The firmware's own factory-default routine sets this field to 2; the constant
above overrides it on every boot. That is the whole reason the globe waits for
the remote.

### 2. Start-up source is forced to USB

Later in the same function:

```
00257559  98e6       b.movi  r7,0x6           <-- input source 6 = USB 1
0025755b  0cea08     b.sw    0x8(r10),r7      ; RAM 0x3b5414 current source
0025755e  0cea0c     b.sw    0xc(r10),r7      ; RAM 0x3b5418 previous source
...
          call 0x260861(source, 0)            ; switch input
```

`main` then chooses the first screen: a USB source opens the source page
(top-level state 8); any other source shows a short source banner (state 0xb)
and goes to normal viewing. The remote's source menu does the same thing when
OK is pressed on HDMI: it stores 4 and calls the same switch routine.

## The two changes

| Name | RAM address | Offset in inflated stream | Old | New | Effect |
|---|---|---|---|---|---|
| `poweron` | 0x25748c | 0x053c8c | `98 e1` | `98 e2` | power-on mode ON: power applied means run |
| `hdmi` | 0x257559 | 0x053d59 | `98 e6` | `98 e4` | start-up source HDMI instead of USB 1 |

Each replaces one two-byte instruction with another of the same length. The
remote's Power key (standby and wake) is untouched.

## Results on hardware

| Image | Result |
|---|---|
| Repacked, no patch | Behaves exactly as stock. Proves sBoot accepts the recompressed stream and recomputed CRC |
| `poweron` | Power applied: green LED and the source page without the remote. HDMI after selecting it |
| `poweron` + `hdmi` | Power applied: straight to live HDMI. Remote off/on returns to HDMI. Back and all menus work. Selecting USB, then cycling power, starts on HDMI again |

## Variations

The source values are 4 (HDMI), 6 (USB 1) and 7 (USB 2); 1, 2, 3 and 5 are
inputs this product does not have. To make the unit start on the last-used
source instead of a fixed one, the store instructions at 0x25755b and 0x25755e
would be replaced with no-ops so the saved value survives; this has not been
tried.

## Building the images

Create the output folder first (`mkdir -p images`).

```
python -m tools.fwimage patch dumps/pristine_1.bin images/test0_repack_only.bin
python -m tools.fwimage patch dumps/pristine_1.bin images/test1_poweron.bin poweron
python -m tools.fwimage patch dumps/pristine_1.bin images/test2_poweron_hdmi.bin poweron hdmi
```

The tool checks the header, the stub magic, the lengths and the CRC of your
dump, checks that the old instruction bytes are where it expects them, and
re-validates its own output. If your firmware is a different build it stops
rather than guessing. It needs `7z` (or `7za`) on the PATH.

Run the tests with `python -m pytest -q`. Tests that need a dump are skipped
if `dumps/pristine_1.bin` is not present.
