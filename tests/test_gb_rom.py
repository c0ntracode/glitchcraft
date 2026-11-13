import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError
from glitchcraft.gb import rom

LOGO = bytes.fromhex("CEED6666CC0D000B03730083000C000D0008111F8889000EDCCC6EE6DDDDD999BBBB67636E0EECCCDDDC999FBBB9333E")


def make_gb(size=0x8000, cart=0x00, size_code=0x00, cgb=0x00, title=b"TESTGAME", marker=None, fix_checksum=True):
    """Synthetic Game Boy ROM: zero filled, valid logo and header checksum, optional {offset: bytes} markers."""
    data = bytearray(size)
    data[0x104:0x134] = LOGO
    data[0x134:0x134 + len(title)] = title
    data[0x143], data[0x147], data[0x148] = cgb, cart, size_code
    for offset, raw in (marker or {}).items():
        data[offset:offset + len(raw)] = raw
    if fix_checksum:
        c = 0
        for b in data[0x134:0x14D]:
            c = (c - b - 1) & 0xFF
        data[0x14D] = c
    return bytes(data)


class GbRomTests(unittest.TestCase):
    def test_identify_reads_title_banks_and_mapper(self):
        info = rom.identify(make_gb(size=0x20000, cart=0x01, size_code=0x02))
        self.assertEqual((info.platform, info.title), ("gb", "TESTGAME"))
        self.assertEqual((info.details["mbc"], info.details["banks"]), ("MBC1", 8))
        self.assertTrue(info.details["supported"])

    def test_missing_logo_returns_none(self):
        data = bytearray(make_gb())
        data[0x104] ^= 0xFF
        self.assertIsNone(rom.identify(bytes(data)))
        self.assertIsNone(rom.identify(b"\x00" * 0x100))

    def test_cgb_flag_is_reported(self):
        self.assertEqual(rom.identify(make_gb(cgb=0x80)).details["cgb"], "enhanced")
        self.assertEqual(rom.identify(make_gb(cgb=0xC0)).details["cgb"], "only")
        self.assertEqual(rom.identify(make_gb()).details["cgb"], "no")

    def test_bad_header_checksum_is_reported_not_refused(self):
        info = rom.identify(make_gb(fix_checksum=False, title=b"X"))
        self.assertFalse(info.details["header_checksum_ok"])
        self.assertTrue(rom.identify(make_gb()).details["header_checksum_ok"])

    def test_unsupported_mapper_is_named_and_unmapped(self):
        info = rom.identify(make_gb(size=0x20000, cart=0x20, size_code=0x02))
        self.assertEqual(info.details["mbc"], "MBC6")
        self.assertFalse(info.details["supported"])
        self.assertIsNone(rom.cpu_to_offset(info, 0x0100))
        with self.assertRaises(GlitchError):
            rom.read_original(make_gb(size=0x20000, cart=0x20, size_code=0x02), info, 0x0100)

    def test_bank_zero_area_maps_to_the_same_offset(self):
        info = rom.identify(make_gb(size=0x20000, cart=0x01, size_code=0x02))
        self.assertEqual(rom.cpu_to_offset(info, 0x3FFF), 0x3FFF)

    def test_switchable_area_needs_a_bank_on_a_banked_cartridge(self):
        info = rom.identify(make_gb(size=0x20000, cart=0x01, size_code=0x02))
        self.assertIsNone(rom.cpu_to_offset(info, 0x4000))
        self.assertEqual(rom.cpu_to_offset(info, 0x4123, 3), 3 * 0x4000 + 0x123)

    def test_a_32k_cartridge_has_no_bank_to_pick(self):
        info = rom.identify(make_gb())
        self.assertEqual(rom.cpu_to_offset(info, 0x7FFF), 0x7FFF)

    def test_bank_zero_selects_bank_one_on_mbc1_and_mbc3_but_not_mbc5(self):
        for cart, want in ((0x01, 1), (0x13, 1), (0x19, 0)):
            info = rom.identify(make_gb(size=0x20000, cart=cart, size_code=0x02))
            self.assertEqual(rom.cpu_to_offset(info, 0x4000, 0), want * 0x4000, hex(cart))

    def test_mbc1_banks_20_40_60_select_the_next_bank(self):
        info = rom.identify(make_gb(size=0x100000, cart=0x01, size_code=0x05))
        self.assertEqual(rom.cpu_to_offset(info, 0x4000, 0x20), 0x21 * 0x4000)

    def test_bank_beyond_the_rom_raises(self):
        info = rom.identify(make_gb(size=0x20000, cart=0x01, size_code=0x02))
        with self.assertRaises(GlitchError):
            rom.cpu_to_offset(info, 0x4000, 8)

    def test_addresses_above_7fff_are_not_rom(self):
        info = rom.identify(make_gb())
        self.assertIsNone(rom.cpu_to_offset(info, 0x8000))
        with self.assertRaises(GlitchError):
            rom.read_original(make_gb(), info, 0xC000)

    def test_read_original_reads_the_byte_and_demands_a_bank_when_needed(self):
        data = make_gb(size=0x20000, cart=0x01, size_code=0x02, marker={3 * 0x4000 + 5: b"\x7e", 0x0200: b"\x42"})
        info = rom.identify(data)
        self.assertEqual(rom.read_original(data, info, 0x0200), 0x42)
        self.assertEqual(rom.read_original(data, info, 0x4005, 3), 0x7E)
        with self.assertRaises(GlitchError):
            rom.read_original(data, info, 0x4005)

    def test_offset_to_cpu(self):
        info = rom.identify(make_gb(size=0x20000, cart=0x01, size_code=0x02))
        self.assertEqual(rom.offset_to_cpu(info, 0x0200), 0x0200)
        self.assertIsNone(rom.offset_to_cpu(info, 0x8005))
        self.assertEqual(rom.offset_to_cpu(rom.identify(make_gb()), 0x4005), 0x4005)


if __name__ == "__main__":
    unittest.main()
