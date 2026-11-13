import os
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError
from glitchcraft.snes import rom

SMW = os.path.join(os.path.dirname(__file__), "..", "roms", "snes", "smw", "Super Mario World (USA).sfc")


def make_snes(layout="lorom", size=0x20000, copier=False, title=b"TEST GAME", marker=None):
    """Synthetic SNES ROM: all $EA, internal header with a valid checksum complement."""
    data = bytearray([0xEA]) * size
    base = 0x7FC0 if layout == "lorom" else 0xFFC0
    hdr = bytearray(32)
    hdr[0:21] = title.ljust(21, b" ")
    hdr[0x15] = 0x20 if layout == "lorom" else 0x21
    hdr[0x17] = 0x08
    hdr[0x1C:0x1E] = (0xEDCB).to_bytes(2, "little")
    hdr[0x1E:0x20] = (0x1234).to_bytes(2, "little")
    data[base:base + 32] = hdr
    for offset, value in (marker or {}).items():
        data[offset] = value
    return (bytes(512) if copier else b"") + bytes(data)


class SnesRomTests(unittest.TestCase):
    def test_lorom_maps_bank00_8000_to_offset_0(self):
        info = rom.identify(make_snes("lorom"))
        self.assertEqual(info.details["layout"], "lorom")
        self.assertEqual(rom.cpu_to_offset(info, 0x008000), 0)
        self.assertEqual(rom.cpu_to_offset(info, 0x018000), 0x8000)

    def test_lorom_mirror_bank80_equals_bank00(self):
        info = rom.identify(make_snes("lorom"))
        self.assertEqual(rom.cpu_to_offset(info, 0x80ABCD), rom.cpu_to_offset(info, 0x00ABCD))

    def test_hirom_maps_c00000_to_offset_0(self):
        info = rom.identify(make_snes("hirom"))
        self.assertEqual(info.details["layout"], "hirom")
        self.assertEqual(rom.cpu_to_offset(info, 0xC00000), 0)
        self.assertEqual(rom.cpu_to_offset(info, 0xC1ABCD), 0x1ABCD)
        self.assertEqual(rom.cpu_to_offset(info, 0x008000), 0x8000)

    def test_copier_header_shifts_offsets_by_512(self):
        data = make_snes("lorom", copier=True)
        info = rom.identify(data)
        self.assertTrue(info.details["copier_header"])
        self.assertEqual(rom.cpu_to_offset(info, 0x008000), 512)
        marked = make_snes("lorom", copier=True, marker={0: 0x77})
        self.assertEqual(rom.read_original(marked, rom.identify(marked), 0x008000), 0x77)

    def test_ram_banks_7e_7f_are_not_rom(self):
        data = make_snes("lorom")
        info = rom.identify(data)
        self.assertIsNone(rom.cpu_to_offset(info, 0x7E0DBE))
        with self.assertRaises(GlitchError) as ctx:
            rom.read_original(data, info, 0x7E0DBE)
        self.assertIn("RAM", str(ctx.exception))

    def test_low_half_of_a_lorom_bank_is_not_rom(self):
        info = rom.identify(make_snes("lorom"))
        self.assertIsNone(rom.cpu_to_offset(info, 0x000DBE))

    def test_unrecognized_layout_returns_none(self):
        self.assertIsNone(rom.identify(bytes([0xEA]) * 0x20000))

    def test_title_is_read_from_the_internal_header(self):
        self.assertEqual(rom.identify(make_snes(title=b"MY GAME")).title, "MY GAME")

    def test_offset_past_end_is_reported_never_read(self):
        data = make_snes("lorom", size=0x10000)
        info = rom.identify(data)
        self.assertIsNone(rom.cpu_to_offset(info, 0x028000))
        with self.assertRaises(GlitchError):
            rom.read_original(data, info, 0x028000)

    def test_lorom_banks_fe_ff_are_rom_in_a_4mb_cart(self):
        data = make_snes("lorom", size=0x400000)
        info = rom.identify(data)
        self.assertEqual(rom.cpu_to_offset(info, 0xFE8000), 0x3F0000)
        self.assertEqual(rom.cpu_to_offset(info, 0xFF8000), 0x3F8000)
        self.assertEqual(rom.offset_to_cpu(info, 0x3F8000), 0xFF8000)
        self.assertEqual(rom.read_original(data, info, 0xFE8000), 0xEA)

    def test_katakana_and_nul_padded_titles_are_accepted(self):
        for title in (b"\xb1\xb2\xb3\xb4 GAME", b"TEST\x00\x00\x00"):
            with self.subTest(title=title):
                info = rom.identify(make_snes("lorom", title=title))
                self.assertIsNotNone(info)
                self.assertTrue(info.title)

    def test_unsupported_map_mode_names_itself(self):
        data = bytearray(make_snes("lorom"))
        data[0x7FC0 + 0x15] = 0x23     # SA-1
        with self.assertRaises(GlitchError) as ctx:
            rom.identify(bytes(data))
        self.assertIn("$23", str(ctx.exception))
        self.assertIn("LoROM and HiROM", str(ctx.exception))

    def test_offset_to_cpu_inverts_cpu_to_offset(self):
        for layout in ("lorom", "hirom"):
            info = rom.identify(make_snes(layout))
            for off in (0, 0x8000, 0x1ABCD):
                self.assertEqual(rom.cpu_to_offset(info, rom.offset_to_cpu(info, off)), off)

    @unittest.skipUnless(os.path.exists(SMW), "roms/snes/smw not present")
    def test_real_smw(self):
        with open(SMW, "rb") as f:
            data = f.read()
        info = rom.identify(data)
        self.assertEqual((info.details["layout"], info.title), ("lorom", "SUPER MARIOWORLD"))
        self.assertEqual(info.sha1, "6b47bb75d16514b6a476aa0c73a683a2a4c18765")
        self.assertEqual(rom.read_original(data, info, 0x00D0D8), 0xCE)


if __name__ == "__main__":
    unittest.main()
