from pathlib import Path

import pytest

from tools.fwimage import crc32_mpeg2
from tools.mergebin import (DEFAULT_SIZE, build_merge, check_merge, predict_blocks, seed_image)

PRISTINE = Path(__file__).resolve().parent.parent / "dumps" / "pristine_1.bin"
needs_dump = pytest.mark.skipif(not PRISTINE.exists(), reason="pristine dump not present")


def test_appending_big_endian_crc_gives_zero_residue():
    body = bytes(range(256)) * 3
    assert crc32_mpeg2(body + crc32_mpeg2(body).to_bytes(4, "big")) == 0


def test_predict_blocks_identical_is_empty():
    chip = bytes(0x40000)
    assert predict_blocks(chip, chip[:0x30000]) == []


def test_predict_blocks_adds_block0_and_last_block():
    chip = bytearray(0x80000)
    merge = bytearray(chip[:0x50000])
    merge[0x2_1234] ^= 1                       # one difference in block 2
    assert predict_blocks(bytes(chip), bytes(merge)) == [0, 2, 4]


def test_predict_blocks_difference_in_last_partial_step():
    chip = bytes(0x30000)
    merge = bytearray(chip[:0x20000 + 100])
    merge[-1] ^= 1
    assert predict_blocks(chip, bytes(merge)) == [0, 2]


def test_build_rejects_wrong_length():
    with pytest.raises(ValueError, match="4 MB"):
        build_merge(bytes(100))


@needs_dump
def test_build_from_pristine_passes_updater_checks():
    flash = PRISTINE.read_bytes()
    m = build_merge(flash)
    assert len(m) == DEFAULT_SIZE
    assert m[:-4] == flash[:DEFAULT_SIZE - 4]
    assert check_merge(m) == []


@needs_dump
def test_pristine_merge_on_pristine_chip_touches_only_block0_and_last():
    flash = PRISTINE.read_bytes()
    m = build_merge(flash)
    assert predict_blocks(flash, m) == [0, 0x39]


@needs_dump
def test_seeded_chip_makes_the_update_a_no_op():
    flash = PRISTINE.read_bytes()
    m = build_merge(flash)
    seeded = seed_image(flash, m)
    assert predict_blocks(seeded, m) == []
    diff = [i for i in range(len(flash)) if flash[i] != seeded[i]]
    assert diff and all(DEFAULT_SIZE - 4 <= i < DEFAULT_SIZE for i in diff)


@needs_dump
def test_build_refuses_size_that_would_overwrite_data():
    with pytest.raises(ValueError, match="not erased"):
        build_merge(PRISTINE.read_bytes(), size=0x390000)


@needs_dump
def test_little_endian_variant_differs_only_in_last_four_bytes():
    flash = PRISTINE.read_bytes()
    a, b = build_merge(flash), build_merge(flash, little_endian_crc=True)
    assert a[:-4] == b[:-4] and a[-4:] == b[-4:][::-1]
