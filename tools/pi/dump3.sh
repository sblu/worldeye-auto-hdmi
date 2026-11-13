#!/usr/bin/env bash
# Read the W25Q32 three times on the Pi and check that the reads agree.
# Usage: ./dump3.sh pristine
set -euo pipefail

NAME="${1:?usage: $0 <dump-name>   e.g. pristine}"
P='linux_spi:dev=/dev/spidev0.0,spispeed=2000'
C='W25Q32BV/W25Q32CV/W25Q32DV'
mkdir -p ~/dumps

for i in 1 2 3; do
  sudo flashrom -p "$P" -c "$C" -r ~/dumps/"${NAME}_$i.bin"
done

echo
sha256sum ~/dumps/"${NAME}"_{1,2,3}.bin
distinct=$(sha256sum ~/dumps/"${NAME}"_{1,2,3}.bin | awk '{print $1}' | sort -u | wc -l)
if [ "$distinct" -eq 1 ]; then
  echo "PASS: all three reads of $NAME are identical"
else
  echo "FAIL: $distinct different hashes for $NAME; re-seat the clip and run again"
  exit 1
fi
