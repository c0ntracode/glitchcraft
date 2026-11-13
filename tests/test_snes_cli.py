import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli
from glitchcraft.core import Patch
from glitchcraft.snes import codec
from test_snes_rom import make_snes


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class SnesCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        plant = bytearray(make_snes("lorom", title=b"SNES TEST"))
        plant[0x1000:0x1003] = bytes.fromhex("CE BE 0D")      # DEC $0DBE at $00:9000
        plant[0x2000:0x2002] = bytes.fromhex("D0 05")         # BNE at $00:A000
        self.rom = self.write("game.sfc", bytes(plant))

    def write(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_id_reports_title_layout_and_hash(self):
        code, out, _ = run("id", self.rom)
        self.assertEqual(code, 0)
        self.assertIn("platform: snes", out)
        self.assertIn("title: SNES TEST", out)
        self.assertIn("layout: lorom", out)
        self.assertIn("sha1: ", out)

    def test_decode_prints_the_original_byte(self):
        code, out, _ = run("decode", self.rom, codec.encode(Patch(0x009000, 0xAD)))
        self.assertEqual(code, 0)
        self.assertIn("$009000", out)
        self.assertIn("original=$CE", out)

    def test_make_roundtrips_a_24_bit_address(self):
        code, out, _ = run("make", self.rom, "--addr", "009000", "--value", "AD")
        self.assertEqual(code, 0)
        self.assertIn("code: " + codec.encode(Patch(0x009000, 0xAD)), out)
        self.assertIn("original: $CE", out)
        self.assertIn("round-trip: ok", out)

    def test_make_refuses_compare_on_snes(self):
        code, _, err = run("make", self.rom, "--addr", "009000", "--value", "AD", "--compare", "CE")
        self.assertEqual(code, 2)
        self.assertIn("no compare byte", err)

    def test_make_with_ram_address_says_game_genie_patches_rom(self):
        code, _, err = run("make", self.rom, "--addr", "7E0DBE", "--value", "63")
        self.assertEqual(code, 2)
        self.assertIn("RAM", err)

    def test_vet_flags_control_flow_change_on_65816_bytes(self):
        code, out, _ = run("vet", self.rom, codec.encode(Patch(0x00A000, 0xEA)))
        self.assertEqual(code, 0)
        self.assertIn("BNE $00A007 -> NOP", out)
        self.assertIn("control-flow-change", out)

    def test_vet_flags_an_address_that_is_not_rom(self):
        code, out, _ = run("vet", self.rom, codec.encode(Patch(0x7E0DBE, 0x63)))
        self.assertEqual(code, 0)
        self.assertIn("not-rom-address", out)

    def test_xrefs_finds_the_lives_style_operand(self):
        code, out, _ = run("xrefs", self.rom, "0DBE")
        self.assertEqual(code, 0)
        self.assertIn("$009000 rmw", out)

    def test_decode_of_a_ram_address_says_not_rom(self):
        code, out, _ = run("decode", self.rom, codec.encode(Patch(0x7E0DBE, 0x63)))
        self.assertEqual(code, 0)
        self.assertIn("not-rom-address", out)
        self.assertNotIn("bank-dependent", out)

    def test_vet_does_not_desync_after_a_16_bit_immediate(self):
        plant = bytearray(make_snes("lorom"))
        plant[0x1000:0x1009] = bytes.fromhex("C2 20 A9 34 12 8D BE 0D 60")
        path = self.write("wide.sfc", bytes(plant))
        code, out, _ = run("vet", path, codec.encode(Patch(0x009008, 0x00)))
        self.assertEqual(code, 0)
        self.assertIn("RTS -> BRK", out)
        self.assertNotIn("boundary-uncertain", out)

    def test_vet_flags_boundaries_that_rest_on_a_guessed_width(self):
        plant = bytearray(make_snes("lorom"))
        plant[0x1000:0x1003] = bytes.fromhex("A9 01 60")
        path = self.write("guess.sfc", bytes(plant))
        _, out, _ = run("vet", path, codec.encode(Patch(0x009002, 0x00)))
        self.assertIn("boundary-uncertain", out)

    def test_xrefs_accepts_the_7e_form_of_a_wram_address(self):
        code, out, _ = run("xrefs", self.rom, "7E0DBE")
        self.assertEqual(code, 0)
        self.assertIn("$009000 rmw", out)

    def test_patch_copy_writes_value_at_mapped_offset(self):
        out_path = os.path.join(self.dir, "patched.sfc")
        code, _, _ = run("patch-copy", self.rom, out_path, codec.encode(Patch(0x009000, 0xAD)))
        self.assertEqual(code, 0)
        with open(out_path, "rb") as f:
            self.assertEqual(f.read()[0x1000], 0xAD)


if __name__ == "__main__":
    unittest.main()
