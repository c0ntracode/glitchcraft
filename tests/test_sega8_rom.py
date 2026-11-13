import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError
from glitchcraft.sega8 import rom


def make_sega8(size=0x8000, header_at=0x7FF0, region=0x6, size_nibble=0xC, marker=None, signature=b"TMR SEGA"):
    """Synthetic Game Gear / Master System ROM: zero filled, TMR SEGA header, optional {offset: bytes} markers."""
    data = bytearray(size)
    if header_at is not None:
        data[header_at:header_at + 8] = signature
        data[header_at + 0xA:header_at + 0xC] = (0x1234).to_bytes(2, "little")
        data[header_at + 0xC:header_at + 0xE] = bytes([0x26, 0x70])
        data[header_at + 0xF] = (region << 4) | size_nibble
    for offset, raw in (marker or {}).items():
        data[offset:offset + len(raw)] = raw
    return bytes(data)


class Sega8RomTests(unittest.TestCase):
    def test_identify_reads_system_region_and_size(self):
        info = rom.identify(make_sega8(region=0x6))
        self.assertEqual(info.platform, "sega8")
        self.assertEqual(info.details["system"], "Game Gear")
        self.assertEqual(info.details["region"], "GG Export")
        self.assertEqual(info.details["header_at"], 0x7FF0)
        self.assertEqual(info.details["product_code"], "7026")
        self.assertEqual(info.details["header_checksum"], "1234")

    def test_region_nibble_picks_the_system(self):
        for nibble, system in ((3, "Master System"), (4, "Master System"), (5, "Game Gear"), (7, "Game Gear"),
                               (0, "unknown"), (9, "unknown")):
            self.assertEqual(rom.identify(make_sega8(region=nibble)).details["system"], system, nibble)

    def test_the_header_may_sit_at_3ff0_or_1ff0(self):
        for at, size in ((0x3FF0, 0x4000), (0x1FF0, 0x2000)):
            self.assertEqual(rom.identify(make_sega8(size=size, header_at=at)).details["header_at"], at)

    def test_no_signature_means_not_recognized(self):
        self.assertIsNone(rom.identify(make_sega8(header_at=None)))
        self.assertIsNone(rom.identify(make_sega8(signature=b"TMR SEGB")))
        self.assertIsNone(rom.identify(b"\x00" * 0x100))

    def test_unusual_size_nibble_is_reported_not_refused(self):
        info = rom.identify(make_sega8(size_nibble=0xD))
        self.assertEqual(info.details["header_size"], "48 KB")

    def test_banks_and_mapper_follow_the_file_size(self):
        small = rom.identify(make_sega8(size=0xC000))
        big = rom.identify(make_sega8(size=0x20000, header_at=0x7FF0))
        self.assertEqual((small.details["mapper"], small.details["banks"]), ("none", 3))
        self.assertEqual((big.details["mapper"], big.details["banks"]), ("Sega", 8))
        self.assertTrue(small.details["supported"] and big.details["supported"])

    def _codemasters(self):
        data = bytearray(make_sega8(size=0x20000))
        data[0x7FE0] = 8
        data[0x7FE6:0x7FE8] = (0x1000).to_bytes(2, "little")
        data[0x7FE8:0x7FEA] = (0x10000 - 0x1000).to_bytes(2, "little")
        return rom.identify(bytes(data))

    def test_a_codemasters_header_is_recognized_and_mapped(self):
        info = self._codemasters()
        self.assertEqual(info.details["mapper"], "Codemasters")
        self.assertTrue(info.details["supported"])

    def test_codemasters_slot_zero_has_no_protected_first_kilobyte(self):
        info = self._codemasters()
        self.assertEqual(rom.cpu_to_offset(info, 0x0100, 2), 2 * 0x4000 + 0x100)   # the Sega mapper would keep 0x100
        self.assertEqual(rom.cpu_to_offset(info, 0x0100), 0x0100)                  # slot 0 assumed bank 0
        self.assertEqual(rom.cpu_to_offset(info, 0x4010, 3), 3 * 0x4000 + 0x10)
        self.assertIsNone(rom.cpu_to_offset(info, 0x4010))
        self.assertEqual(rom.bank_end(info, 0x0100), 0x4000)

    def test_the_sega_mapper_still_protects_the_first_kilobyte(self):
        info = rom.identify(make_sega8(size=0x20000))
        self.assertEqual(rom.cpu_to_offset(info, 0x0100, 2), 0x0100)

    def test_a_32k_rom_maps_addresses_directly(self):
        info = rom.identify(make_sega8())
        self.assertEqual(rom.cpu_to_offset(info, 0x0123), 0x0123)
        self.assertEqual(rom.cpu_to_offset(info, 0x7FFF), 0x7FFF)

    def test_bank_independent_start_of_slot_zero_and_default_bank_for_the_rest(self):
        info = rom.identify(make_sega8(size=0x20000))
        self.assertEqual(rom.cpu_to_offset(info, 0x03FF, 5), 0x03FF)      # first 1 KB never moves
        self.assertEqual(rom.cpu_to_offset(info, 0x0400), 0x0400)         # slot 0 assumed bank 0 without --bank
        self.assertEqual(rom.cpu_to_offset(info, 0x0400, 2), 2 * 0x4000 + 0x400)

    def test_banked_areas_need_a_bank(self):
        info = rom.identify(make_sega8(size=0x20000))
        self.assertIsNone(rom.cpu_to_offset(info, 0x4000))
        self.assertIsNone(rom.cpu_to_offset(info, 0x8000))
        self.assertEqual(rom.cpu_to_offset(info, 0x4010, 3), 3 * 0x4000 + 0x10)
        self.assertEqual(rom.cpu_to_offset(info, 0x9FFF, 7), 7 * 0x4000 + 0x1FFF)

    def test_bank_out_of_range_or_past_the_file_raises(self):
        info = rom.identify(make_sega8(size=0x20000))
        with self.assertRaises(GlitchError):
            rom.cpu_to_offset(info, 0x4000, 8)
        with self.assertRaises(GlitchError):
            rom.cpu_to_offset(info, 0x4000, -1)
        short = rom.identify(make_sega8(size=0x8000, size_nibble=0xF))
        short.details["mapper"] = "Sega"
        short.details["banks"] = 8
        with self.assertRaises(GlitchError):
            rom.cpu_to_offset(short, 0x4000, 5)

    def test_ram_and_io_addresses_are_not_rom(self):
        info = rom.identify(make_sega8())
        self.assertIsNone(rom.cpu_to_offset(info, 0xC000))
        with self.assertRaises(GlitchError) as ctx:
            rom.read_original(make_sega8(), info, 0xC000)
        self.assertIn("RAM", str(ctx.exception))

    def test_read_original_and_missing_bank_message(self):
        data = make_sega8(size=0x20000, marker={3 * 0x4000 + 5: b"\x7e", 0x0200: b"\x42"})
        info = rom.identify(data)
        self.assertEqual(rom.read_original(data, info, 0x0200), 0x42)
        self.assertEqual(rom.read_original(data, info, 0x4005, 3), 0x7E)
        with self.assertRaises(GlitchError) as ctx:
            rom.read_original(data, info, 0x4005)
        self.assertIn("--bank", str(ctx.exception))

    def test_offset_to_cpu(self):
        banked = rom.identify(make_sega8(size=0x20000))
        self.assertEqual(rom.offset_to_cpu(banked, 0x0200), 0x0200)
        self.assertIsNone(rom.offset_to_cpu(banked, 0x8005))
        flat = rom.identify(make_sega8())
        self.assertEqual(rom.offset_to_cpu(flat, 0x4005), 0x4005)
        self.assertIsNone(rom.offset_to_cpu(flat, 0x9000))


if __name__ == "__main__":
    unittest.main()
