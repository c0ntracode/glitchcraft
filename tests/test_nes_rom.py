import hashlib
import os
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError
from glitchcraft.nes import rom

SMB = os.path.join(os.path.dirname(__file__), "..", "roms", "nes", "smb.nes")


def make_rom(prg_banks, mapper=0, trainer=False, chr_banks=1):
    """Synthetic iNES file. Every 16 KB PRG bank is filled with (bank number + 1)."""
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4], header[5] = prg_banks, chr_banks
    header[6] = ((mapper & 0x0F) << 4) | (4 if trainer else 0)
    header[7] = mapper & 0xF0
    body = bytes(512) if trainer else b""
    for b in range(prg_banks):
        body += bytes([b + 1]) * 0x4000
    return bytes(header) + body + bytes(0x2000 * chr_banks)


class RomTests(unittest.TestCase):
    def info(self, data):
        return rom.identify(data)

    def test_nrom256_maps_linearly(self):
        info = self.info(make_rom(2))
        self.assertEqual(rom.cpu_to_offset(info, 0x8000), 16)
        self.assertEqual(rom.cpu_to_offset(info, 0xC000), 16 + 0x4000)

    def test_nrom128_mirrors(self):
        info = self.info(make_rom(1))
        self.assertEqual(rom.cpu_to_offset(info, 0x8000), 16)
        self.assertEqual(rom.cpu_to_offset(info, 0xC000), 16)

    def test_trainer_shifts_offset_by_512(self):
        info = self.info(make_rom(2, trainer=True))
        self.assertEqual(rom.cpu_to_offset(info, 0x8000), 16 + 512)

    def test_headerless_returns_none(self):
        self.assertIsNone(rom.identify(bytes(40976)))

    def test_truncated_file_raises(self):
        with self.assertRaises(GlitchError):
            rom.identify(make_rom(2)[:1000])

    def test_mmc1_switchable_window_returns_none_without_bank(self):
        info = self.info(make_rom(8, mapper=1))
        self.assertIsNone(rom.cpu_to_offset(info, 0x8000))
        self.assertEqual(rom.cpu_to_offset(info, 0x8000, bank=3), 16 + 3 * 0x4000)

    def test_fixed_last_bank_maps_for_unrom(self):
        data = make_rom(8, mapper=2)
        info = self.info(data)
        off = rom.cpu_to_offset(info, 0xC123)
        self.assertEqual(data[off], 8)  # last bank filled with 8

    def test_mmc3_fixed_banks_and_unknown_mapper(self):
        data = make_rom(8, mapper=4)  # 16 x 8 KB banks
        info = self.info(data)
        self.assertEqual(data[rom.cpu_to_offset(info, 0xE000)], 8)   # last 8 KB bank is in last 16 KB bank
        self.assertIsNone(rom.cpu_to_offset(info, 0x8000))
        info9 = self.info(make_rom(2, mapper=9))
        self.assertIsNone(rom.cpu_to_offset(info9, 0x8000, bank=0))

    def test_offset_to_cpu_inverts_cpu_to_offset(self):
        info = self.info(make_rom(2))
        for addr in (0x8000, 0x9ABC, 0xFFFF):
            self.assertEqual(rom.offset_to_cpu(info, rom.cpu_to_offset(info, addr)), addr)

    def test_read_original_unmapped_raises_with_bank_hint(self):
        data = make_rom(8, mapper=1)
        with self.assertRaises(GlitchError) as ctx:
            rom.read_original(data, self.info(data), 0x8000)
        self.assertIn("bank", str(ctx.exception))

    def test_offset_to_cpu_nrom128(self):
        info = self.info(make_rom(1))
        self.assertEqual(rom.offset_to_cpu(info, 16 + 0x6B), 0xC06B)

    def test_bank_out_of_range_raises(self):
        info = self.info(make_rom(8, mapper=1))
        for bank in (-1, 8):
            with self.subTest(bank=bank):
                with self.assertRaises(GlitchError) as ctx:
                    rom.cpu_to_offset(info, 0x8000, bank=bank)
                self.assertIn("bank", str(ctx.exception))

    def test_zero_prg_banks_rejected(self):
        with self.assertRaises(GlitchError):
            rom.identify(make_rom(0))

    def test_dirty_header_warns_and_names_likely_mapper(self):
        data = bytearray(make_rom(2))
        data[7:16] = b"DiskDude!"
        info = rom.identify(bytes(data))
        self.assertEqual(info.details["mapper"], 64)
        self.assertIn("mapper 0", info.details["header_warning"])

    def test_clean_header_has_no_warning(self):
        self.assertNotIn("header_warning", self.info(make_rom(2)).details)

    def test_read_original_ram_address_explains_rom_only(self):
        data = make_rom(2)
        with self.assertRaises(GlitchError) as ctx:
            rom.read_original(data, self.info(data), 0x075A)
        self.assertIn("RAM", str(ctx.exception))

    def test_header_fields(self):
        info = self.info(make_rom(2, mapper=3))
        self.assertEqual((info.platform, info.details["mapper"], info.details["prg_banks"]), ("nes", 3, 2))

    @unittest.skipUnless(os.path.exists(SMB), "roms/nes/smb.nes not present")
    def test_smb_real_rom(self):
        with open(SMB, "rb") as f:
            data = f.read()
        info = rom.identify(data)
        self.assertEqual(info.sha1, "33d23c2f2cfa4c9efec87f7bc1321ce3ce6c89bd")
        self.assertEqual(info.details["mapper"], 0)
        self.assertEqual(rom.read_original(data, info, 0x8256), 0xD8)
        self.assertEqual(info.sha1, hashlib.sha1(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
