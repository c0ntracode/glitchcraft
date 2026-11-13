import os
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError
from glitchcraft.genesis import rom

SONIC = os.path.join(os.path.dirname(__file__), "..", "roms", "genesis", "Sonic_The_Hedgehog_W_REV01_h3C.bin")


def make_md(size=0x80000, console=b"SEGA MEGA DRIVE ", domestic=b"", overseas=b"TEST GAME", marker=None):
    """Synthetic Genesis ROM: all zero, with a header at $100 and optional marker words {offset: bytes}."""
    data = bytearray(size)
    data[0x100:0x110] = console.ljust(16, b" ")
    data[0x120:0x150] = domestic.ljust(48, b" ")
    data[0x150:0x180] = overseas.ljust(48, b" ")
    data[0x180:0x18E] = b"GM 00000000-00"
    data[0x18E:0x190] = (0xBEEF).to_bytes(2, "big")
    data[0x1A4:0x1A8] = (size - 1).to_bytes(4, "big")
    for offset, raw in (marker or {}).items():
        data[offset:offset + len(raw)] = raw
    return bytes(data)


class GenesisRomTests(unittest.TestCase):
    def test_identify_reads_title_console_and_serial(self):
        info = rom.identify(make_md())
        self.assertEqual((info.platform, info.title), ("genesis", "TEST GAME"))
        self.assertEqual(info.details["console"], "SEGA MEGA DRIVE")
        self.assertEqual(info.details["serial"], "GM 00000000-00")
        self.assertEqual(info.details["rom_size"], 0x80000)

    def test_title_falls_back_to_the_domestic_title_and_collapses_spaces(self):
        info = rom.identify(make_md(domestic=b"SONIC   THE   HEDGEHOG", overseas=b""))
        self.assertEqual(info.title, "SONIC THE HEDGEHOG")

    def test_genesis_console_name_is_accepted(self):
        self.assertIsNotNone(rom.identify(make_md(console=b"SEGA GENESIS")))

    def test_a_rom_without_a_sega_header_is_identified_from_its_vector_table_with_a_warning(self):
        data = bytearray(0x80000)
        data[0:4] = (0x00FFFFFC).to_bytes(4, "big")
        for i in range(1, 64):
            data[i * 4:i * 4 + 4] = (0x104 if i != 2 else 0x1F0).to_bytes(4, "big")
        data[0x100:0x104] = bytes.fromhex("46FC2700")      # code where the header would be
        info = rom.identify(bytes(data))
        self.assertEqual(info.platform, "genesis")
        self.assertIn("no SEGA header", info.details["header_warning"])
        self.assertIsNone(info.title)

    def test_a_vector_table_that_points_outside_the_rom_is_not_a_genesis_rom(self):
        data = bytearray(0x80000)
        data[0:4] = (0x00FFFFFC).to_bytes(4, "big")
        for i in range(1, 64):
            data[i * 4:i * 4 + 4] = (0x104).to_bytes(4, "big")
        for i in range(2, 20):                              # eighteen vectors past the end of a 512 KB ROM
            data[i * 4:i * 4 + 4] = (0x00900000).to_bytes(4, "big")
        self.assertIsNone(rom.identify(bytes(data)))
        self.assertIsNone(rom.identify(b"\x00" * 0x80000))
        self.assertIsNone(rom.identify(b"\xFF" * 0x80000))

    def test_a_few_junk_vectors_are_tolerated(self):
        data = bytearray(0x80000)
        data[0:4] = (0x00FFFFFC).to_bytes(4, "big")
        for i in range(1, 64):
            data[i * 4:i * 4 + 4] = (0x104).to_bytes(4, "big")
        data[36 * 4:36 * 4 + 4] = (0x80000).to_bytes(4, "big")       # as in a real unlicensed ROM
        data[37 * 4:37 * 4 + 4] = (0x9905B779).to_bytes(4, "big")
        self.assertEqual(rom.identify(bytes(data)).platform, "genesis")

    def test_missing_sega_marker_returns_none(self):
        self.assertIsNone(rom.identify(make_md(console=b"NOT A SEGA ROM")))
        self.assertIsNone(rom.identify(bytes(0x80000)))
        self.assertIsNone(rom.identify(bytes(100)))

    def test_smd_file_raises_with_conversion_hint(self):
        smd = bytearray(512 + 0x8000)
        smd[8], smd[9] = 0xAA, 0xBB
        with self.assertRaises(GlitchError) as ctx:
            rom.identify(bytes(smd))
        self.assertIn(".smd", str(ctx.exception))
        self.assertIn(".bin", str(ctx.exception))

    def test_cpu_to_offset_is_identity_within_the_file(self):
        info = rom.identify(make_md())
        self.assertEqual(rom.cpu_to_offset(info, 0x000200), 0x200)
        self.assertEqual(rom.cpu_to_offset(info, 0x07FFFE), 0x7FFFE)

    def test_address_past_the_end_is_not_read(self):
        data = make_md()
        info = rom.identify(data)
        self.assertIsNone(rom.cpu_to_offset(info, 0x080000))
        with self.assertRaises(GlitchError) as ctx:
            rom.read_original(data, info, 0x080000)
        self.assertIn("past the end", str(ctx.exception))

    def test_ram_and_io_addresses_say_game_genie_patches_rom_reads(self):
        data = make_md()
        info = rom.identify(data)
        for addr in (0xFFFE12, 0xA10001, 0x400000):
            with self.subTest(addr=hex(addr)):
                self.assertIsNone(rom.cpu_to_offset(info, addr))
                with self.assertRaises(GlitchError) as ctx:
                    rom.read_original(data, info, addr)
                self.assertIn("patches ROM reads", str(ctx.exception))

    def test_read_original_returns_a_big_endian_word(self):
        data = make_md(marker={0x1000: bytes([0x53, 0x38])})
        self.assertEqual(rom.read_original(data, rom.identify(data), 0x001000), 0x5338)

    def test_odd_address_reads_the_even_word(self):
        data = make_md(marker={0x1000: bytes([0x53, 0x38])})
        info = rom.identify(data)
        self.assertEqual(rom.read_original(data, info, 0x001001), 0x5338)
        self.assertEqual(rom.cpu_to_offset(info, 0x001001), 0x1000)

    def test_rom_over_4mb_is_flagged_in_details(self):
        self.assertTrue(rom.identify(make_md(size=0x500000)).details["big_rom"])
        self.assertFalse(rom.identify(make_md()).details["big_rom"])

    def test_offset_to_cpu_inverts_cpu_to_offset(self):
        info = rom.identify(make_md())
        for off in (0, 0x200, 0x7FFFE):
            self.assertEqual(rom.cpu_to_offset(info, rom.offset_to_cpu(info, off)), off)

    @unittest.skipUnless(os.path.exists(SONIC), "roms/genesis not present")
    def test_real_sonic_rom(self):
        with open(SONIC, "rb") as f:
            data = f.read()
        info = rom.identify(data)
        self.assertEqual((info.title, info.details["serial"]), ("SONIC THE HEDGEHOG", "GM 00004049-01"))
        self.assertEqual(info.sha1, "1f1e480f768237eb0c0e725b622b0d791f47a7a9")
        self.assertEqual(rom.read_original(data, info, 0x013F74), 0x5338)


if __name__ == "__main__":
    unittest.main()
