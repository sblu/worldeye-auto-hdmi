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
SPEED="${SPEED:-1000}"                     # kHz; slower than the dumps on purpose
P="linux_spi:dev=/dev/spidev0.0,spispeed=$SPEED"
C='W25Q32BV/W25Q32CV/W25Q32DV'
D=~/dumps/writeapp/$(date +%Y%m%d-%H%M%S); mkdir -p "$D"
IMG=$(readlink -f "$IMG"); cd "$D"
export WEAK_OFFSET="${WEAK_OFFSET:--1}"
# Region to write: default is the application. Override for special cases, e.g.
#   REGION_START=0x390000 REGION_END=0x3a0000 ./writeapp.sh seed.bin
export REGION_START="${REGION_START:-0x20000}" REGION_END="${REGION_END:-0xe0000}"   # end is exclusive
printf '%08x:%08x app\n' $((REGION_START)) $((REGION_END - 1)) > layout.txt
# REFRESH=1 erases the region first (by writing it blank) and then writes it, so
# every cell in it is freshly programmed even where the chip already reads right.
# Used to renew a weak bit, e.g.:  REFRESH=1 REGION_START=0x149000 REGION_END=0x14a000
REFRESH="${REFRESH:-0}"

# cmpx A B -> prints number of differing bytes. If your chip has a known unstable byte,
# set WEAK_OFFSET (e.g. WEAK_OFFSET=0x149873 ./writeapp.sh ...) and that one offset is ignored,
# unless the region being written contains it: then it is checked like any other byte.
cmpx() { python3 - "$1" "$2" "${3:-}" <<'PY'
import sys,os
a=open(sys.argv[1],'rb').read(); b=open(sys.argv[2],'rb').read()
if len(a)!=len(b): print(-1); sys.exit()
W=int(os.environ.get('WEAK_OFFSET','-1'),0)
if sys.argv[3]=='strict' and int(os.environ['REGION_START'],0)<=W<int(os.environ['REGION_END'],0): W=-1
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
import sys,struct,os
img=open(sys.argv[1],'rb').read(); cur=open('current.bin','rb').read()
assert len(img)==len(cur)==4*1024*1024, 'image and chip must both be 4 MB'
A,B=int(os.environ['REGION_START'],0),int(os.environ['REGION_END'],0)
assert 0<=A<B<=len(img) and A%0x1000==0 and B%0x1000==0, 'region must be 4 KB aligned'
src,ram,ramend,fend,z,crc=struct.unpack_from('<6I',img,0x20000)
assert src==0x20080 and ram==0x200000 and fend<=0xe0000, 'image header does not look like a WorldEye application'
# CRC-32/MPEG-2, init 0, over [src, fend) must equal the header word (what sBoot checks)
t=[]
for i in range(256):
    c=i<<24
    for _ in range(8): c=((c<<1)^0x04C11DB7)&0xffffffff if c&0x80000000 else (c<<1)&0xffffffff
    t.append(c)
c=0
for b in img[src:fend]: c=((c<<8)&0xffffffff)^t[(c>>24)^b]
assert c==crc, 'image CRC does not match its header: %08x vs %08x'%(c,crc)
W=int(os.environ.get('WEAK_OFFSET','-1'),0)
bad=[i for i in range(0x20000) if img[i]!=cur[i]]
assert not bad, 'bootloader in image differs from chip at %#x'%bad[0]
exp=bytearray(cur); exp[A:B]=img[A:B]
open('expected.bin','wb').write(exp)
blank=bytearray(cur); blank[A:B]=b'\xff'*(B-A); open('blank.bin','wb').write(blank)
if W>=0: print('weak byte %#x: chip reads %#04x now, image has %#04x'%(W,cur[W],img[W]))
print('image CRC ok (%08x); %d bytes of the region %#x-%#x will change'%(crc,sum(x!=y for x,y in zip(cur[A:B],img[A:B])),A,B-1))
PY

echo
printf "About to WRITE the region 0x%06x-0x%06x from:\n" $((REGION_START)) $((REGION_END - 1))
echo "  $IMG"
read -r -p "Type YES to continue: " a; [ "$a" = "YES" ] || { echo "stopped, nothing written"; exit 1; }

echo "== 3. write (up to 3 attempts)"
for try in 1 2 3; do
  if [ "$REFRESH" = "1" ]; then
    echo "   refresh: erasing the region first"
    sudo flashrom -p "$P" -c "$C" -l layout.txt -i app --noverify-all -w blank.bin 2>&1 | grep -E "unlock|Erase|Verif|FAILED|Error|error"
  fi
  sudo flashrom -p "$P" -c "$C" -l layout.txt -i app --noverify-all -w "$IMG" 2>&1 | grep -E "unlock|Erase|Verif|FAILED|Error|error" 
  echo "== 4. read back until two reads match the expected result (attempt $try)"
  good=0
  for i in 1 2 3 4 5; do
    rd "post_${try}_$i.bin" || continue
    n=$(cmpx "post_${try}_$i.bin" expected.bin strict); echo "  read $i: $n bytes differ from expected"
    [ "$n" = "0" ] && good=$((good+1))
    [ "$good" -ge 2 ] && break
  done
  if [ "$good" -ge 2 ]; then
    echo; sudo flashrom -p "$P" -c "$C" --wp-status 2>/dev/null | grep -i protection
    echo "PASS: two independent reads match. Region written; everything else unchanged."
    echo "Remove the clip (and the pin 3 link) before powering the globe."
    exit 0
  fi
  echo "not confirmed yet; writing again"
done
echo "FAIL: the chip does not read back as expected after 3 attempts."
echo "Do NOT power the globe. Reseat the clip and run this script again with the same image,"
echo "or with pristine_1.bin to put the factory application back. Backup is $D/current.bin"
exit 1
