import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli
from glitchcraft.core import Patch
from glitchcraft.sega8 import codec
from test_sega8_rom import make_sega8


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def code_for(addr, value, compare=None):
    return codec.encode(Patch(addr, value, compare))


class Sega8CliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        marker = {
            0x0200: bytes.fromhex("3E053200C04F"),   # LD A,5 / LD ($C000),A / LD C,A
            0x0300: bytes.fromhex("01C0DD2400"),     # LD BC,$DDC0 / INC H: hides RET NZ and DD 24 (INC IXH)
            0x0400: bytes.fromhex("01C9DD2400"),     # LD BC,$DDC9: hides RET and DD 24
            0x0600: bytes.fromhex("3200C0"),         # LD ($C000),A
            0x0700: bytes.fromhex("3EDD24"),         # LD A,$DD / INC H
            3 * 0x4000 + 0x10: bytes.fromhex("3C3C3C"),   # INC A x3 in bank 3
        }
        flat = {k: v for k, v in marker.items() if k < 0x8000}   # a marker past the end would silently grow the ROM
        self.small = self.write("small.gg", make_sega8(marker=flat))
        self.banked = self.write("banked.gg", make_sega8(size=0x20000, size_nibble=0xF, marker=marker))

    def write(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_id_reports_system_and_mapper(self):
        code, out, _ = run("id", self.banked)
        self.assertEqual(code, 0)
        for want in ("platform: sega8", "system: Game Gear", "mapper: Sega", "banks: 8"):
            self.assertIn(want, out)

    def test_decode_shows_the_original_byte(self):
        _, out, _ = run("decode", self.small, code_for(0x0201, 0x09))
        self.assertIn("$0201", out)
        self.assertIn("original=$05", out)

    def test_make_roundtrips_with_a_compare_and_writes_the_check_digit(self):
        code, out, _ = run("make", self.small, "--addr", "0201", "--value", "09", "--compare", "05")
        self.assertEqual(code, 0)
        want = code_for(0x0201, 0x09, 0x05)
        self.assertIn("code: " + want, out)
        self.assertEqual(int(want[9], 16), int(want[8], 16) ^ 8)

    def test_make_in_a_banked_slot_needs_a_bank(self):
        code, _, err = run("make", self.banked, "--addr", "4010", "--value", "00")
        self.assertNotEqual(code, 0)
        self.assertIn("--bank", err)
        code, out, _ = run("make", self.banked, "--addr", "4010", "--value", "00", "--bank", "3")
        self.assertEqual(code, 0)
        self.assertIn("original: $3C", out)

    def test_make_in_ram_explains_it_is_not_rom(self):
        code, _, err = run("make", self.small, "--addr", "C000", "--value", "00")
        self.assertNotEqual(code, 0)
        self.assertIn("cannot write RAM", err)

    def test_vet_flags_a_patch_that_adds_a_jump(self):
        _, out, _ = run("vet", self.small, code_for(0x0200, 0xC3))
        self.assertIn("JP", out)
        self.assertIn("control-flow-change", out)

    def test_vet_flags_an_undocumented_opcode_that_now_runs(self):
        _, out, _ = run("vet", self.small, code_for(0x0700, 0x00))   # LD A,$DD becomes NOP; DD 24 then executes
        self.assertIn("unofficial-opcode-follows", out)

    def test_vet_stops_following_at_an_unconditional_ret(self):
        _, out, _ = run("vet", self.small, code_for(0x0400, 0x00))   # NOP, RET, then DD 24 is not reached
        self.assertNotIn("unofficial-opcode-follows", out)

    def test_vet_follows_past_a_conditional_ret(self):
        _, out, _ = run("vet", self.small, code_for(0x0300, 0x00))   # NOP, RET NZ, then DD 24 can be reached
        self.assertIn("unofficial-opcode-follows", out)

    def test_vet_flags_the_vector_and_header_areas_and_compare_mismatch(self):
        _, out, _ = run("vet", self.small, code_for(0x0038, 0xC9))
        self.assertIn("vector-area", out)
        _, out, _ = run("vet", self.small, code_for(0x7FF2, 0x00))
        self.assertIn("vector-area", out)
        _, out, _ = run("vet", self.small, code_for(0x0201, 0x09, 0x77))
        self.assertIn("compare-mismatch", out)

    def test_vet_flags_bank_dependent_until_a_bank_is_given(self):
        _, out, _ = run("vet", self.banked, code_for(0x4010, 0x00))
        self.assertIn("bank-dependent", out)
        _, out, _ = run("vet", self.banked, "--bank", "3", code_for(0x4010, 0x00))
        self.assertNotIn("bank-dependent", out)
        self.assertIn("INC A -> NOP", out)

    def test_disasm_with_a_bank(self):
        _, out, _ = run("disasm", self.banked, "4010", "3", "--bank", "3")
        self.assertEqual(out.count("INC A"), 3)

    def test_patch_copy_applies_two_codes_with_a_bank(self):
        dst = os.path.join(self.dir, "out.gg")
        code, _, _ = run("patch-copy", self.banked, dst, "--bank", "3", code_for(0x4010, 0x00), code_for(0x0201, 0x09))
        self.assertEqual(code, 0)
        with open(dst, "rb") as f:
            data = f.read()
        self.assertEqual((data[3 * 0x4000 + 0x10], data[0x201]), (0x00, 0x09))

    def test_xrefs_lists_the_store(self):
        _, out, _ = run("xrefs", self.small, "C000")
        self.assertIn("$0600 write", out)
        self.assertIn("$0202 write", out)

    def test_xrefs_says_so_when_nothing_references_the_address(self):
        code, out, _ = run("xrefs", self.small, "D123")
        self.assertEqual(code, 0)
        self.assertIn("no references", out)

    def test_disasm_past_the_end_of_a_small_rom_says_so_even_with_a_bank(self):
        code, _, err = run("disasm", self.small, "8000", "2", "--bank", "1")
        self.assertNotEqual(code, 0)
        self.assertNotIn("needs --bank", err)

    def test_xrefs_on_a_48k_rom_places_branch_targets_at_their_real_address(self):
        rom = self.write("flat48.gg", make_sega8(size=0xC000, marker={0x8000: bytes.fromhex("1803")}))   # JR $8005
        _, out, _ = run("xrefs", rom, "8005")
        self.assertIn("$8000 jump", out)
        _, out, _ = run("xrefs", rom, "4005")
        self.assertNotIn("$8000", out)

    def test_xrefs_in_a_banked_rom_does_not_guess_the_slot_of_a_relative_branch(self):
        rom = self.write("jr.gg", make_sega8(size=0x20000, marker={3 * 0x4000: bytes.fromhex("1803")}))
        for target in ("4005", "8005"):
            _, out, _ = run("xrefs", rom, target)
            self.assertNotIn("jump", out)

    def test_vet_shows_the_real_change_behind_a_useless_prefix(self):
        rom = self.write("pfx.gg", make_sega8(marker={0x0800: bytes.fromhex("FD3E05C9")}))
        _, out, _ = run("vet", rom, code_for(0x0802, 0x09))          # the operand, not the opcode
        self.assertIn("LD A,$05 -> LD A,$09", out)
        rom2 = self.write("pfx2.gg", make_sega8(marker={0x0800: bytes.fromhex("DD00341200")}))
        _, out, _ = run("vet", rom2, code_for(0x0801, 0x21))         # 00 -> 21 after DD: LD IX,nn
        self.assertIn("LD IX,$1234", out)

    def test_make_warns_in_the_vector_area(self):
        code, out, _ = run("make", self.small, "--addr", "0038", "--value", "C9")
        self.assertEqual(code, 0)
        self.assertIn("warning", out)


if __name__ == "__main__":
    unittest.main()
