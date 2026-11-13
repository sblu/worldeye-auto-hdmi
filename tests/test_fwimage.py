import struct
import zlib
from pathlib import Path

import pytest

from tools import fwimage
from tools.fwimage import PATCHES, apply_patch, crc32_mpeg2, repack, unpack

PRISTINE = Path(__file__).resolve().parent.parent / "dumps" / "pristine_1.bin"
needs_dump = pytest.mark.skipif(not PRISTINE.exists(), reason="pristine dump not present")


def test_crc32_mpeg2_check_value():
    # CRC-32/MPEG-2 of "123456789" is 0x0376E6E7 with init 0xFFFFFFFF.
    assert crc32_mpeg2(b"123456789", 0xFFFFFFFF) == 0x0376E6E7


def test_crc_of_empty_is_init():
    assert crc32_mpeg2(b"") == 0


def synthetic_flash(app: bytes) -> bytes:
    """Smallest flash that satisfies unpack(): header, stub, stream, trailer."""
    c = zlib.compressobj(1, zlib.DEFLATED, -15)      # poor ratio leaves room to repack
    stream = c.compress(app) + c.flush()
    src = 0x20080
    total = fwimage.STUB_LEN + len(stream) + 6
    stub = bytearray(fwimage.STUB_LEN)
    stub[0x1147:0x114A] = b"\xbe\xad\xde"
    struct.pack_into("<I", stub, 0x114A, total)
    body = bytes(stub) + stream + struct.pack("<I", len(app)) + b"\xc8\x1d"
    flash = bytearray(b"\xff" * (src + total + 0x100))
    flash[src:src + total] = body
    struct.pack_into("<6I", flash, 0x20000, src, 0x200000, 0x200000 + total, src + total, 0, crc32_mpeg2(body))
    return bytes(flash)


def test_unpack_synthetic_roundtrip():
    app = bytes(range(256)) * 64
    img = unpack(synthetic_flash(app))
    assert img.app == app


def test_unpack_rejects_bad_crc():
    flash = bytearray(synthetic_flash(b"hello world" * 100))
    flash[0x20080 + 0x10] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        unpack(bytes(flash))


def test_repack_changes_only_stream_and_crc():
    app = bytearray(b"The quick brown fox " * 2000)
    flash = synthetic_flash(bytes(app))
    img = unpack(flash)
    app[1234] ^= 0xFF
    out = repack(flash, img, bytes(app))
    assert len(out) == len(flash)
    diff = [i for i, (x, y) in enumerate(zip(flash, out)) if x != y]
    assert all(0x20014 <= i < 0x20018 or img.comp_start <= i < img.flash_end - 6 for i in diff)
    assert unpack(out).app == bytes(app)


def test_repack_rejects_length_change():
    flash = synthetic_flash(b"abc" * 1000)
    with pytest.raises(ValueError, match="length"):
        repack(flash, unpack(flash), b"abc" * 999)


def test_apply_patch_checks_old_bytes():
    app = bytes(0x60000)
    with pytest.raises(ValueError, match="expected 98e1"):
        apply_patch(app, PATCHES["poweron"])


@needs_dump
def test_pristine_unpacks_and_matches_known_facts():
    img = unpack(PRISTINE.read_bytes())
    assert img.crc == 0x3FE64D1D
    assert len(img.app) == 1646704
    assert img.comp_start + img.stream_len == 0xD5F03


@needs_dump
def test_pristine_patch_sites_hold_expected_instructions():
    img = unpack(PRISTINE.read_bytes())
    for p in PATCHES.values():
        off = p.addr - fwimage.APP_RAM
        assert img.app[off:off + 2] == p.old


@needs_dump
def test_pristine_full_patch_touches_two_app_bytes_and_nothing_outside_image():
    flash = PRISTINE.read_bytes()
    img = unpack(flash)
    app = img.app
    for p in PATCHES.values():
        app = apply_patch(app, p)
    assert [i for i, (x, y) in enumerate(zip(img.app, app)) if x != y] == [
        0x25748D - fwimage.APP_RAM, 0x25755A - fwimage.APP_RAM]
    out = repack(flash, img, app)
    assert len(out) == len(flash) == 4 * 1024 * 1024
    assert out[:0x20014] == flash[:0x20014]
    assert out[0x20018:img.comp_start] == flash[0x20018:img.comp_start]
    assert out[img.flash_end - 6:] == flash[img.flash_end - 6:]
    assert unpack(out).app == app
