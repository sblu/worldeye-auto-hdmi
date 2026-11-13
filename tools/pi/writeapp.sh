#!/usr/bin/env bash
# Write ONLY the application region (0x020000-0x0dffff) of a 4 MB image to the
# flash chip in the globe, through the clip, and prove the result with repeated
# reads. The bootloader, the data after the application, and the settings
# sectors are left exactly as they are on the chip.
#
# Wiring: as for a dump, plus chip pin 3 (/WP) to Pi pin 1 (3.3 V) through 1 kOhm.
# Globe unplugged. Do not touch the clip while this runs.
#
# Usage: ./writeapp.sh <image.bin>
#   e.g. ./writeapp.sh ~/images/test0_repack_only.bin
#        ./writeapp.sh ~/images/pristine_1.bin        (puts the factory application back)
# Only ever use images built from YOUR OWN dump of YOUR OWN unit.
set -uo pipefail

IMG="${1:?usage: $0 <image.bin>}"
export WEAK_OFFSET="${WEAK_OFFSET:--1}"
SPEED="${SPEED:-1000}"                     # kHz; slower than the dumps on purpose
P="linux_spi:dev=/dev/spidev0.0,spispeed=$SPEED"
C='W25Q32BV/W25Q32CV/W25Q32DV'
D=~/dumps/writeapp/$(date +%Y%m%d-%H%M%S); mkdir -p "$D"
IMG=$(readlink -f "$IMG"); cd "$D"
printf '00020000:000dffff app\n' > layout.txt

# cmpx A B -> prints number of differing bytes. If your chip has a known unstable byte,
# set WEAK_OFFSET (e.g. WEAK_OFFSET=0x149873 ./writeapp.sh ...) and that one offset is ignored.
cmpx() { python3 - "$1" "$2" <<'PY'
import sys,os
a=open(sys.argv[1],'rb').read(); b=open(sys.argv[2],'rb').read()
if len(a)!=len(b): print(-1); sys.exit()
W=int(os.environ.get('WEAK_OFFSET','-1'),0)
n=0 if a==b else sum(1 for i in range(len(a)) if a[i]!=b[i] and i!=W)
print(n)
PY
}
rd() { sudo flashrom -p "$P" -c "$C" -r "$1" >/dev/null 2>&1 || { echo "flashrom read failed (clip?)"; return 1; }; }

echo "== 1. read the chip until two reads agree (backup of what is on it now)"
ok=""
for i in 1 2 3 4 5; do
  rd "pre_$i.bin" || continue
  for j in $(seq 1 $((i-1))); do
    [ -f "pre_$j.bin" ] && [ "$(cmpx pre_$i.bin pre_$j.bin)" = "0" ] && ok="pre_$i.bin"
  done
  [ -n "$ok" ] && break
done
[ -n "$ok" ] || { echo "STOP: could not get two matching reads. Reseat the clip. Nothing written."; exit 1; }
cp "$ok" current.bin; echo "backup: $D/current.bin"; sha256sum current.bin

echo "== 2. build the expected result (chip as it is, application region from the image)"
python3 - "$IMG" <<'PY' || { echo "STOP: image check failed. Nothing written."; exit 1; }
import sys,struct
img=open(sys.argv[1],'rb').read(); cur=open('current.bin','rb').read()
assert len(img)==len(cur)==4*1024*1024, 'image and chip must both be 4 MB'
A,B=0x20000,0xe0000
src,ram,ramend,fend,z,crc=struct.unpack_from('<6I',img,A)
assert src==0x20080 and ram==0x200000 and fend<=B, 'image header does not look like a WorldEye application'
# CRC-32/MPEG-2, init 0, over [src, fend) must equal the header word (what sBoot checks)
t=[]
for i in range(256):
    c=i<<24
    for _ in range(8): c=((c<<1)^0x04C11DB7)&0xffffffff if c&0x80000000 else (c<<1)&0xffffffff
    t.append(c)
c=0
for b in img[src:fend]: c=((c<<8)&0xffffffff)^t[(c>>24)^b]
assert c==crc, 'image CRC does not match its header: %08x vs %08x'%(c,crc)
assert img[:A]==cur[:A] or sum(x!=y for x,y in zip(img[:A],cur[:A]))==0, 'bootloader in image differs from chip'
exp=bytearray(cur); exp[A:B]=img[A:B]
open('expected.bin','wb').write(exp)
print('image CRC ok (%08x); %d bytes of the application region will change'%(crc,sum(x!=y for x,y in zip(cur[A:B],img[A:B]))))
PY

echo
echo "About to WRITE the application region 0x020000-0x0dffff from:"
echo "  $IMG"
read -r -p "Type YES to continue: " a; [ "$a" = "YES" ] || { echo "stopped, nothing written"; exit 1; }

echo "== 3. write (up to 3 attempts)"
for try in 1 2 3; do
  sudo flashrom -p "$P" -c "$C" -l layout.txt -i app --noverify-all -w "$IMG" 2>&1 | grep -E "unlock|Erase|Verif|FAILED|Error|error" 
  echo "== 4. read back until two reads match the expected result (attempt $try)"
  good=0
  for i in 1 2 3 4 5; do
    rd "post_${try}_$i.bin" || continue
    n=$(cmpx "post_${try}_$i.bin" expected.bin); echo "  read $i: $n bytes differ from expected"
    [ "$n" = "0" ] && good=$((good+1))
    [ "$good" -ge 2 ] && break
  done
  if [ "$good" -ge 2 ]; then
    echo; sudo flashrom -p "$P" -c "$C" --wp-status 2>/dev/null | grep -i protection
    echo "PASS: two independent reads match. Application region written; everything else unchanged."
    echo "Remove the clip (and the pin 3 link) before powering the globe."
    exit 0
  fi
  echo "not confirmed yet; writing again"
done
echo "FAIL: the chip does not read back as expected after 3 attempts."
echo "Do NOT power the globe. Reseat the clip and run this script again with the same image,"
echo "or with pristine_1.bin to put the factory application back. Backup is $D/current.bin"
exit 1
