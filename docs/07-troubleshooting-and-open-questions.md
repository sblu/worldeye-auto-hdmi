# 07 Troubleshooting and open questions

## Read glitches through the clip

Symptom: one read differs from the others by hundreds or thousands of bytes in
one stretch (runs of 0xFF, 0x00 or noise), although nothing was written.
Seen at 2000 kHz and 1000 kHz. The chip was fine every time. Mitigations:
reseat the clip, do not touch it during a run, and only ever act on reads
that agree with each other. The scripts in `tools/pi/` do this for you.

## A weak bit in the flash

On the unit tested, one bit (bit 2 of the byte at flash offset 0x149873) reads
either way from one read to the next: the byte comes back as 0x31 or 0x35.
The chip is from 2012. Effects:

- three dumps often needed more than one attempt to match;
- an early analysis mistook this byte for a "current source" flag, because it
  happened to differ between dump sessions.

If your dumps keep differing in a single byte at the same offset, compare them
with `cmp -l` and suspect the same thing. `writeapp.sh` can be told to ignore
one offset: `WEAK_OFFSET=0x149873 ./writeapp.sh image.bin`.

The byte can also be renewed. Erasing and rewriting its 4 KB sector with the
clip made it read steadily on the tested unit (one read straight afterwards
differed, for a reason not examined; every dump since has agreed):

```
REFRESH=1 REGION_START=0x149000 REGION_END=0x14a000 ./writeapp.sh ~/images/your_image.bin
```

`REFRESH=1` erases the region before writing it, so the cells are freshly
programmed even where the chip already reads correctly. The image must hold
the value you believe is right (here 0x31, which fits the neighbouring table
entries). This matters for the USB updater ([06](06-usb-updater.md)), which
treats any difference between file and chip as a reason to rewrite.

## Write refused

`Failed to unlock flash status reg with wp support` followed by a verify
failure where every byte reads 0xFF: the write-protect pin is low. See the
resistor in [04](04-flashing-with-a-raspberry-pi.md). `flashrom --wp-status`
shows "Protection range: all, Protection mode: hardware" on this unit in
normal condition.

## Intermittent flashing red LED at plug-in (unsolved)

On the unit tested, applying power sometimes gave about two seconds of steady
red, then fast regular red flashing, with no response to the remote. Moving
internal wiring eventually cured it each time. This predates the patch.

What the code shows:

- There is no power-on self test and no error-blink routine in the main
  application or the bootloader. What drives the LED was not found.
- On every plug-in the application powers the optical engine in sequence
  (about 2.1 s) and then configures the DPP2607 over I2C (address 0x36). One
  of those steps (RAM 0x2041ec) waits on a busy bit in a loop that uses the
  value read back even if the I2C read failed. With the engine not answering,
  start-up could hang there. The two-second timing fits; it is not proven.

If you see this, look at the connection between the main board and the
optical engine first. The firmware logs to a serial console throughout
start-up (`AC_BOOT`, `write i2c addr %x can't access`, `IIC init fail`), which
would show where it stops; the console pads and baud rate were not identified.

With the patch installed this fault matters more, because the unit is expected
to start unattended.

## Open questions

- Serial console location and baud rate.
- What the data between 0x0d5f09 and 0x16252d is (the weak bit is in it).
- Whether the two-byte field after the inflated-length trailer is a checksum
  of something. sBoot does not read it.
- No-signal behaviour over long periods on HDMI with the patch (a one-hour
  soak is the minimum before relying on it).
- The USB updater ([06](06-usb-updater.md)) is untested.
- Other firmware builds and board revisions: unknown. If the tool rejects
  your dump, please do not force it; compare your build date on the Software
  Update page with "Nov 18 2013, 11:47:24".
