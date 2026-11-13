import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli
from glitchcraft.core import Patch
from glitchcraft.gb import codec
from test_gb_rom import make_gb


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def code_for(addr, value, compare=None):
    return codec.encode(Patch(addr, value, compare))


class GbCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        marker = {
            0x0200: bytes.fromhex("3E05E0404F"),         # LD A,5 / LDH ($FF40),A / LD C,A
            0x0300: bytes.fromhex("01C0D3"),              # LD BC,$D3C0 (a conditional RET and an illegal byte hide inside)
            0x0400: bytes.fromhex("01C9D3"),              # LD BC,$D3C9 (an unconditional RET and an illegal byte)
            0x0700: bytes.fromhex("3ED34F"),              # LD A,$D3 / LD C,A
            0x0500: bytes.fromhex("00C9"),                # NOP / RET
            0x0600: bytes.fromhex("EA00C0"),              # LD ($C000),A
            3 * 0x4000 + 0x10: bytes.fromhex("3C3C3C"),   # INC A x3 in bank 3
        }
        flat = {k: v for k, v in marker.items() if k < 0x8000}   # a marker past the end would silently grow the ROM
        self.small = self.write("small.gb", make_gb(marker=flat))
        self.banked = self.write("banked.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02, marker=marker))

    def write(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_id_reports_the_platform_title_and_mapper(self):
        code, out, _ = run("id", self.banked)
        self.assertEqual(code, 0)
        for want in ("platform: gb", "title: TESTGAME", "mbc: MBC1", "banks: 8"):
            self.assertIn(want, out)

    def test_decode_shows_the_original_byte(self):
        _, out, _ = run("decode", self.small, code_for(0x0201, 0x09))
        self.assertIn("$0201", out)
        self.assertIn("original=$05", out)

    def test_make_roundtrips_with_a_compare(self):
        code, out, _ = run("make", self.small, "--addr", "0201", "--value", "09", "--compare", "05")
        self.assertEqual(code, 0)
        self.assertIn("code: " + code_for(0x0201, 0x09, 0x05), out)
        self.assertIn("round-trip: ok", out)

    def test_make_refuses_a_compare_that_differs_from_the_rom(self):
        code, _, err = run("make", self.small, "--addr", "0201", "--value", "09", "--compare", "06")
        self.assertNotEqual(code, 0)
        self.assertIn("will not apply", err)

    def test_make_in_the_switchable_area_needs_a_bank(self):
        code, _, err = run("make", self.banked, "--addr", "4010", "--value", "00")
        self.assertNotEqual(code, 0)
        self.assertIn("--bank", err)
        code, out, _ = run("make", self.banked, "--addr", "4010", "--value", "00", "--bank", "3")
        self.assertEqual(code, 0)
        self.assertIn("original: $3C", out)

    def test_make_warns_when_the_patch_lands_in_the_header_area(self):
        code, out, _ = run("make", self.small, "--addr", "0147", "--value", "00")
        self.assertEqual(code, 0)
        self.assertIn("warning", out)
        self.assertIn("header", out)
        code, out, _ = run("make", self.small, "--addr", "0201", "--value", "09")
        self.assertNotIn("warning", out)

    def test_make_above_7fff_explains_that_it_is_not_rom(self):
        code, _, err = run("make", self.small, "--addr", "C000", "--value", "00")
        self.assertNotEqual(code, 0)
        self.assertIn("cannot write RAM", err)

    def test_vet_flags_a_patch_that_adds_a_jump(self):
        _, out, _ = run("vet", self.small, code_for(0x0200, 0xC3))
        self.assertIn("LD A,$05 -> JP", out)
        self.assertIn("control-flow-change", out)

    def test_vet_flags_a_patch_that_makes_the_next_byte_an_illegal_opcode(self):
        _, out, _ = run("vet", self.small, code_for(0x0700, 0x00))   # LD A,$D3 becomes NOP; D3 then executes
        self.assertIn("unofficial-opcode-follows", out)

    def test_vet_stops_following_at_an_unconditional_ret(self):
        _, out, _ = run("vet", self.small, code_for(0x0400, 0x00))   # NOP, RET, then D3 is never reached
        self.assertNotIn("unofficial-opcode-follows", out)

    def test_vet_follows_past_a_conditional_ret(self):
        _, out, _ = run("vet", self.small, code_for(0x0300, 0x00))   # NOP, RET NZ, then D3 can be reached
        self.assertIn("unofficial-opcode-follows", out)

    def test_vet_flags_the_header_area_and_a_compare_mismatch(self):
        _, out, _ = run("vet", self.small, code_for(0x0134, 0x41))
        self.assertIn("vector-area", out)
        _, out, _ = run("vet", self.small, code_for(0x0201, 0x09, 0x77))
        self.assertIn("compare-mismatch", out)

    def test_vet_flags_bank_dependent_until_a_bank_is_given(self):
        _, out, _ = run("vet", self.banked, code_for(0x4010, 0x00))
        self.assertIn("bank-dependent", out)
        _, out, _ = run("vet", self.banked, "--bank", "3", code_for(0x4010, 0x00))
        self.assertNotIn("bank-dependent", out)
        self.assertIn("INC A -> NOP", out)

    def test_a_bank_is_ignored_below_4000_even_when_it_is_nonsense(self):
        code, out, _ = run("make", self.banked, "--addr", "0201", "--value", "09", "--bank", "999")
        self.assertEqual(code, 0)
        self.assertIn("original: $05", out)

    def test_bank_accepts_hex_and_equals_form(self):
        big = self.write("big.gb", make_gb(size=0x100000, cart=0x01, size_code=0x05,
                                           marker={0x21 * 0x4000 + 0x10: bytes.fromhex("3C")}))
        for flag in (["--bank", "0x20"], ["--bank", "32"], ["--bank=0x20"]):
            code, out, err = run("make", big, "--addr", "4010", "--value", "00", *flag)
            self.assertEqual(code, 0, (flag, err))
            self.assertIn("original: $3C", out)

    def test_bank_that_is_not_a_number_says_how_to_write_one(self):
        code, _, err = run("disasm", self.banked, "4010", "1", "--bank", "zz")
        self.assertNotEqual(code, 0)
        self.assertIn("0x", err)

    def test_patch_copy_into_a_hard_link_of_the_input_is_refused(self):
        link = os.path.join(self.dir, "hard.gb")
        os.link(self.small, link)
        code, _, err = run("patch-copy", self.small, link, code_for(0x0201, 9))
        self.assertNotEqual(code, 0)
        self.assertIn("overwrite", err)

    def test_disasm_never_runs_an_instruction_into_the_next_bank(self):
        rom = self.write("edge.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02,
                                            marker={0x3FFF: b"\x3E", 0x4000: b"\x55"}))
        _, out, _ = run("disasm", rom, "3FFF", "1")
        self.assertNotIn("LD A,$55", out)
        self.assertIn(".byte $3E", out)

    def test_xrefs_does_not_stitch_an_operand_from_the_next_bank(self):
        rom = self.write("edge2.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02,
                                             marker={0x3FFF: b"\xEA", 0x4000: bytes.fromhex("00C0")}))
        _, out, _ = run("xrefs", rom, "C000")
        self.assertNotIn("$3FFF", out)

    def test_vet_does_not_read_the_next_bank_as_code(self):
        rom = self.write("edge3.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02,
                                             marker={0x3FFE: b"\xC9", 0x4000: b"\xD3"}))
        _, out, _ = run("vet", rom, code_for(0x3FFE, 0x00))   # RET -> NOP; the byte after is in another bank
        self.assertNotIn("unofficial-opcode-follows", out)

    def test_disasm_with_a_bank(self):
        _, out, _ = run("disasm", self.banked, "4010", "3", "--bank", "3")
        self.assertEqual(out.count("INC A"), 3)

    def test_patch_copy_applies_two_codes_with_a_bank(self):
        dst = os.path.join(self.dir, "out.gb")
        code, _, _ = run("patch-copy", self.banked, dst, "--bank", "3", code_for(0x4010, 0x00), code_for(0x0201, 0x09))
        self.assertEqual(code, 0)
        with open(dst, "rb") as f:
            data = f.read()
        self.assertEqual((data[3 * 0x4000 + 0x10], data[0x201]), (0x00, 0x09))

    def test_patch_copy_in_a_banked_area_hints_at_bank(self):
        code, _, err = run("patch-copy", self.banked, os.path.join(self.dir, "x.gb"), code_for(0x4010, 0x00))
        self.assertNotEqual(code, 0)
        self.assertIn("--bank", err)

    def test_decode_warns_when_the_compare_does_not_match_the_rom(self):
        _, out, _ = run("decode", self.small, code_for(0x0201, 0x09, 0x77))
        self.assertIn("will not apply", out)
        _, out, _ = run("decode", self.small, code_for(0x0201, 0x09, 0x05))
        self.assertNotIn("will not apply", out)

    def test_disasm_of_a_ram_address_does_not_suggest_a_bank(self):
        code, _, err = run("disasm", self.banked, "C000", "2")
        self.assertNotEqual(code, 0)
        self.assertNotIn("--bank", err)
        self.assertIn("not ROM", err)

    def test_xrefs_rejects_bank_instead_of_ignoring_it(self):
        code, _, err = run("xrefs", self.banked, "C000", "--bank", "3")
        self.assertNotEqual(code, 0)
        self.assertIn("file offset", err)

    def test_xrefs_lists_the_store(self):
        _, out, _ = run("xrefs", self.small, "C000")
        self.assertIn("$0600 write", out)


if __name__ == "__main__":
    unittest.main()
