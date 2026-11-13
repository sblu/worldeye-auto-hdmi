#!/usr/bin/env bash
# Prove that in-circuit WRITE and ERASE work through the clip, without touching
# any firmware: write a pattern into the erased, unused region 0x3a0000-0x3bffff,
# read it back, then erase the region again and confirm the chip is byte-for-byte
# what it was before. Run on the Pi, globe unplugged, clip attached as for a dump.
# Usage: ./scratchtest.sh
set -euo pipefail

P='linux_spi:dev=/dev/spidev0.0,spispeed=2000'
C='W25Q32BV/W25Q32CV/W25Q32DV'
START=$((0x3a0000)); LEN=$((0x20000))
D=~/dumps/scratchtest; mkdir -p "$D"; cd "$D"
printf '003a0000:003bffff scratch\n' > layout.txt

[ -f before_1.bin ] && cp before_1.bin previous_run.bin
echo "== 1. read the chip twice"
sudo flashrom -p "$P" -c "$C" -r before_1.bin
sudo flashrom -p "$P" -c "$C" -r before_2.bin
cmp before_1.bin before_2.bin || { echo "FAIL: the two reads differ; re-seat the clip"; exit 1; }
sha256sum before_1.bin
if [ -f previous_run.bin ]; then
  if cmp -s previous_run.bin before_1.bin; then echo "chip is identical to the start of the previous run"
  else echo "note: chip differs from the previous run (expected only if the globe was powered in between)"; fi
fi

echo "== 2. confirm the scratch region is erased"
python3 - <<PY
d=open('before_1.bin','rb').read()
assert len(d)==4*1024*1024, 'not a 4 MB image'
r=d[$START:$START+$LEN]
assert r==b'\xff'*$LEN, 'scratch region is not all 0xFF; stopping'
import hashlib
pat=b''.join(hashlib.sha256(i.to_bytes(4,'little')).digest() for i in range($LEN//32))
open('test.bin','wb').write(d[:$START]+pat+d[$START+$LEN:])
print('scratch region is erased; test image built')
PY

echo "== 3. write-protect status (information only)"
sudo flashrom -p "$P" -c "$C" --wp-status || echo "(wp-status not available; continuing)"

echo
echo "About to WRITE a test pattern to 0x3a0000-0x3bffff on the chip in the globe."
read -r -p "Type YES to continue: " ok; [ "$ok" = "YES" ] || { echo "stopped, nothing written"; exit 1; }

echo "== 4. write the pattern (scratch region only)"
sudo flashrom -p "$P" -c "$C" -l layout.txt -i scratch -w test.bin || echo "flashrom reported a write failure; reading back to see what is on the chip"
sudo flashrom -p "$P" -c "$C" -r after.bin
if cmp after.bin test.bin; then echo "write OK: pattern present, rest of chip unchanged"
else echo "WRITE CHECK FAILED (see above); attempting to restore anyway"; fi

echo "== 5. erase the region again (restore)"
sudo flashrom -p "$P" -c "$C" -l layout.txt -i scratch -w before_1.bin || echo "flashrom reported a failure on restore; reading back"
sudo flashrom -p "$P" -c "$C" -r restored.bin
echo "== 6. write-protect status after the test"
sudo flashrom -p "$P" -c "$C" --wp-status || true
if cmp -s restored.bin before_1.bin && ! cmp -s after.bin test.bin; then
  echo "NO WRITE HAPPENED: the chip refused the write (write-protected) and is unchanged."
  exit 2
fi
if cmp restored.bin before_1.bin && cmp after.bin test.bin; then
  echo "PASS: in-circuit write and erase work; chip is identical to before the test"
  sha256sum restored.bin
else
  echo "FAIL: keep the clip on, do not power the globe, and send this whole output"
  exit 1
fi
