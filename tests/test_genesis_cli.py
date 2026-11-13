import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli
from glitchcraft.core import Patch
from glitchcraft.genesis import codec, dis68000
from test_genesis_rom import make_md


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def code_for(addr, value):
    return codec.encode(Patch(addr, value, None))


class GenesisCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        marker = {0x1000: bytes.fromhex("5338FE12"), 0x2000: bytes.fromhex("6604"),
                  0x4FE0: bytes.fromhex("F000"), 0x3000: bytes.fromhex("4E71")}
        self.rom = self.write("game.bin", make_md(marker=marker))

    def write(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_id_reports_title_console_and_hash(self):
        code, out, _ = run("id", self.rom)
        self.assertEqual(code, 0)
        self.assertIn("platform: genesis", out)
        self.assertIn("title: TEST GAME", out)
        self.assertIn("console: SEGA MEGA DRIVE", out)
        self.assertIn("sha1: ", out)

    def test_decode_prints_the_word_original(self):
        code, out, _ = run("decode", self.rom, code_for(0x001000, 0x4E71))
        self.assertEqual(code, 0)
        self.assertIn("$001000", out)
        self.assertIn("value=$4E71", out)
        self.assertIn("original=$5338", out)

    def test_make_roundtrips_a_word_patch(self):
        code, out, _ = run("make", self.rom, "--addr", "001000", "--value", "4E71")
        self.assertEqual(code, 0)
        self.assertIn("code: " + code_for(0x001000, 0x4E71), out)
        self.assertIn("original: $5338", out)
        self.assertIn("new: $4E71", out)
        self.assertIn("round-trip: ok", out)

    def test_make_refuses_an_odd_address_and_names_the_even_one(self):
        code, _, err = run("make", self.rom, "--addr", "001001", "--value", "4E71")
        self.assertEqual(code, 2)
        self.assertIn("even", err)
        self.assertIn("$001000", err)
        self.assertNotIn("internal error", err)

    def test_make_refuses_compare_on_genesis(self):
        code, _, err = run("make", self.rom, "--addr", "001000", "--value", "4E71", "--compare", "5338")
        self.assertEqual(code, 2)
        self.assertIn("compare", err)

    def test_make_with_ram_address_says_game_genie_patches_rom(self):
        code, _, err = run("make", self.rom, "--addr", "FFFE12", "--value", "0003")
        self.assertEqual(code, 2)
        self.assertIn("patches ROM reads", err)

    def test_vet_flags_control_flow_change_on_68000_bytes(self):
        code, out, _ = run("vet", self.rom, code_for(0x002000, 0x4E71))
        self.assertEqual(code, 0)
        self.assertIn("BNE.S $002006 -> NOP", out)
        self.assertIn("control-flow-change", out)

    def test_vet_marks_undecoded_opcodes_and_uncertain_boundaries(self):
        _, out, _ = run("vet", self.rom, code_for(0x003000, 0xA000))
        self.assertIn("NOP -> dc.w $A000", out)
        self.assertIn("opcode-class-change", out)
        _, out, _ = run("vet", self.rom, code_for(0x005000, 0x4E71))
        self.assertIn("boundary-uncertain", out)       # an undecoded word sits in the sweep window before it
        _, out, _ = run("vet", self.rom, code_for(0x001000, 0x4E71))
        self.assertNotIn("boundary-uncertain", out)

    def test_vet_does_not_flag_leftover_words_that_an_unconditional_branch_skips(self):
        _, out, _ = run("vet", self.rom, code_for(0x001000, 0x6002))     # BRA.S over the extension word
        self.assertIn("BRA.S $001004", out)
        self.assertNotIn("unofficial-opcode-follows", out)
        _, out, _ = run("vet", self.rom, code_for(0x001000, 0x4E71))     # NOP leaves FE12 to be executed
        self.assertIn("unofficial-opcode-follows", out)

    def test_vet_flags_the_exception_vector_area(self):
        _, out, _ = run("vet", self.rom, code_for(0x000040, 0x0000))
        self.assertIn("vector-area", out)

    def test_vet_reports_word_wide_before_and_after_values(self):
        _, out, _ = run("vet", self.rom, code_for(0x001000, 0x4E71))
        self.assertIn("$5338 -> $4E71", out)
        self.assertIn("SUBQ.B #1,($FFFFFE12).w -> NOP", out)

    def test_patch_copy_writes_both_bytes(self):
        out_path = os.path.join(self.dir, "patched.bin")
        code, _, _ = run("patch-copy", self.rom, out_path, code_for(0x001000, 0x4E71))
        self.assertEqual(code, 0)
        with open(out_path, "rb") as f:
            self.assertEqual(f.read()[0x1000:0x1004], bytes.fromhex("4E71FE12"))

    def test_xrefs_finds_the_operand(self):
        code, out, _ = run("xrefs", self.rom, "FFFE12")
        self.assertEqual(code, 0)
        self.assertIn("$001000 rmw", out)

    def test_xrefs_lists_every_store_of_the_same_variable(self):
        store = bytes.fromhex("11FC0003FE12")
        rom = self.write("multi.bin", make_md(marker={0x1000: store, 0x2000: store, 0x3000: store}))
        _, out, _ = run("xrefs", rom, "FFFE12")
        for addr in ("$001000", "$002000", "$003000"):
            self.assertIn(addr + " write", out)

    def test_patch_with_an_odd_address_patches_its_even_word(self):
        _, out, _ = run("vet", self.rom, code_for(0x001001, 0x4E71))
        self.assertIn("$001000", out)

    def test_locate_reports_whether_every_item_in_the_sweep_decoded(self):
        data = make_md(marker={0x1000: bytes.fromhex("4E714E71")})
        start, uncertain = dis68000.locate(data, 0xFF0, 0x1002)
        self.assertEqual((start, uncertain), (0x1002, False))
        start, uncertain = dis68000.locate(bytes.fromhex("F0004E71"), 0, 2)
        self.assertEqual((start, uncertain), (2, True))


if __name__ == "__main__":
    unittest.main()
