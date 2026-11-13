"""Adversarial Game Boy CLI tests: hostile or sloppy input should give a specific message, never a traceback."""
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


class GbExtraTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def write(self, name, data):
        p = os.path.join(self.dir, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()

    def run_ok(self, *argv):
        """Run the CLI; an escaped exception (a traceback for the user) is a test failure."""
        try:
            return run(*argv)
        except Exception as e:  # noqa: BLE001
            self.fail(f"uncaught {type(e).__name__}: {e} for {argv[0]}")

    def assert_clean_error(self, res, *words):
        code, out, err = res
        self.assertNotEqual(code, 0, f"expected failure, got out={out!r}")
        self.assertNotIn("Traceback", err)
        self.assertNotIn("IndexError", err)
        low = err.lower()
        for w in words:
            self.assertIn(w.lower(), low, f"{w!r} missing from {err!r}")

    # ---- ROM files ----------------------------------------------------------------------------------------------
    def test_truncated_rom_is_not_recognized(self):
        p = self.write("t.gb", make_gb()[:0x120])
        self.assert_clean_error(self.run_ok("id", p), "not recognized")

    def test_empty_file_is_not_recognized(self):
        p = self.write("e.gb", b"")
        self.assert_clean_error(self.run_ok("id", p), "not recognized")

    def test_missing_file_names_the_problem(self):
        self.assert_clean_error(self.run_ok("id", os.path.join(self.dir, "nope.gb")), "cannot read")

    def test_oversized_file_is_reported_as_size_mismatch(self):
        p = self.write("o.gb", make_gb(size=0x10000))   # header claims 32 KB
        code, out, _ = self.run_ok("id", p)
        self.assertEqual(code, 0)
        self.assertIn("size_mismatch: True", out)

    def test_header_size_code_above_8_falls_back_to_file_size(self):
        for sc in (0x09, 0x52, 0xFF):
            p = self.write(f"s{sc}.gb", make_gb(size=0x10000, cart=0x01, size_code=sc))
            code, out, _ = self.run_ok("id", p)
            self.assertEqual(code, 0)
            self.assertIn("banks: 4", out)

    def test_rom_smaller_than_the_header_claims_gives_a_specific_bank_error(self):
        p = self.write("short.gb", make_gb(size=0x8000, cart=0x01, size_code=0x02))   # claims 8 banks, has 2
        code, out, err = self.run_ok("make", p, "--addr", "4010", "--value", "00", "--bank", "5")
        self.assert_clean_error((code, out, err), "end of this rom")
        self.assertIn("size_mismatch: True", self.run_ok("id", p)[1])

    def test_decode_past_the_real_end_does_not_blame_a_missing_bank(self):
        p = self.write("short.gb", make_gb(size=0x8000, cart=0x01, size_code=0x02))
        _, out, _ = self.run_ok("decode", p, "--bank", "5", code_for(0x4010, 0))
        self.assertNotIn("bank-dependent", out)   # a bank WAS given

    def test_vet_past_the_real_end_does_not_blame_a_missing_bank(self):
        p = self.write("short.gb", make_gb(size=0x8000, cart=0x01, size_code=0x02))
        _, out, _ = self.run_ok("vet", p, "--bank", "5", code_for(0x4010, 0))
        self.assertNotIn("bank-dependent", out)

    # ---- banks --------------------------------------------------------------------------------------------------
    def mbc1_2mb(self):
        marks = {b * 0x4000 + 0x10: bytes([0x80 + b % 0x7F]) for b in (0x01, 0x20, 0x21, 0x40, 0x41, 0x60, 0x61)}
        return self.write("big.gb", make_gb(size=0x200000, cart=0x01, size_code=0x06, marker=marks))

    def test_mbc1_banks_20_40_60_read_the_next_bank(self):
        p = self.mbc1_2mb()
        for bank in (0x20, 0x40, 0x60):
            code, out, _ = self.run_ok("make", p, "--addr", "4010", "--value", "00", "--bank", str(bank))
            self.assertEqual(code, 0)
            self.assertIn(f"original: ${0x80 + (bank + 1) % 0x7F:02X}", out)

    def test_mbc1_bank_0_reads_bank_1_but_mbc5_bank_0_reads_bank_0(self):
        m1 = self.write("m1.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02,
                                         marker={0x10: b"\x11", 0x4010: b"\x22"}))
        m5 = self.write("m5.gb", make_gb(size=0x20000, cart=0x19, size_code=0x02,
                                         marker={0x10: b"\x11", 0x4010: b"\x22"}))
        self.assertIn("original: $22", self.run_ok("make", m1, "--addr", "4010", "--value", "00", "--bank", "0")[1])
        self.assertIn("original: $22", self.run_ok("make", m5, "--addr", "4010", "--value", "00", "--bank", "1")[1])
        self.assertIn("original: $11", self.run_ok("make", m5, "--addr", "4010", "--value", "00", "--bank", "0")[1])

    def test_bank_out_of_range_names_the_range(self):
        p = self.write("b.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02))
        for cmd in (("make", p, "--addr", "4010", "--value", "00", "--bank", "8"),
                    ("vet", p, "--bank", "8", code_for(0x4010, 0)),
                    ("decode", p, "--bank", "8", code_for(0x4010, 0))):
            self.assert_clean_error(self.run_ok(*cmd), "out of range")

    def test_negative_bank_is_rejected_by_every_command(self):
        p = self.write("b.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02))
        for cmd in (("make", p, "--addr", "4010", "--value", "00", "--bank=-1"),
                    ("vet", p, "--bank", "-1", code_for(0x4010, 0)),
                    ("disasm", p, "4010", "3", "--bank", "-2")):
            self.assert_clean_error(self.run_ok(*cmd), "bank")

    def test_non_numeric_and_missing_bank_values_name_the_option(self):
        p = self.write("b.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02))
        self.assert_clean_error(self.run_ok("vet", p, "--bank", "abc", code_for(0x4010, 0)), "--bank")
        self.assert_clean_error(self.run_ok("vet", p, code_for(0x4010, 0), "--bank"), "--bank")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "4010", "--value", "0", "--bank", "x"), "--bank")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "4010", "--value", "0", "--bank"), "--bank")

    def test_bank_larger_than_a_two_bank_rom_is_not_silently_ignored(self):
        p = self.write("small.gb", make_gb())
        code, out, err = self.run_ok("make", p, "--addr", "4010", "--value", "00", "--bank", "5")
        self.assertNotEqual(code, 0, "bank 5 does not exist in a 2-bank ROM but was accepted")

    # ---- codes --------------------------------------------------------------------------------------------------
    def test_lowercase_code_decodes_like_uppercase(self):
        p = self.write("s.gb", make_gb(marker={0x201: b"\x05"}))
        c = code_for(0x0201, 0x09, 0x05)
        self.assertEqual(self.run_ok("decode", p, c)[1], self.run_ok("decode", p, c.lower())[1])

    def test_wrong_length_and_garbage_codes_have_specific_errors(self):
        p = self.write("s.gb", make_gb())
        self.assert_clean_error(self.run_ok("decode", p, "01A-2B3-4"), "6 or 9")      # 7 digits
        self.assert_clean_error(self.run_ok("decode", p, "01A-2B3-4C"), "6 or 9")     # 8 digits
        self.assert_clean_error(self.run_ok("decode", p, "01A-2B3-4C5D"), "6 or 9")   # 10 digits
        self.assert_clean_error(self.run_ok("decode", p, "ZZZ-ZZZ"), "hex")
        self.assert_clean_error(self.run_ok("decode", p, "01A 2B3"), "6 or 9")

    def test_decode_address_boundary_7fff_ok_8000_refused(self):
        p = self.write("s.gb", make_gb(marker={0x7FFF: b"\x42"}))
        code, out, _ = self.run_ok("decode", p, "00F-FF8")
        self.assertEqual(code, 0)
        self.assertIn("$7FFF", out)
        self.assertIn("original=$42", out)
        self.assert_clean_error(self.run_ok("decode", p, "000-007"), "7fff")

    def test_decode_and_vet_with_no_code_say_so(self):
        p = self.write("s.gb", make_gb())
        self.assert_clean_error(self.run_ok("decode", p), "code")
        self.assert_clean_error(self.run_ok("vet", p), "code")

    def test_make_value_and_compare_over_one_byte_are_refused(self):
        p = self.write("s.gb", make_gb())
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0200", "--value", "1FF"), "one byte")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0200", "--value", "1", "--compare", "100"), "one byte")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0200", "--value", "zz"), "hex")

    # ---- patching -----------------------------------------------------------------------------------------------
    def test_patch_copy_can_patch_the_last_byte(self):
        p = self.write("s.gb", make_gb(marker={0x7FFF: b"\x42"}))
        dst = os.path.join(self.dir, "o.gb")
        code, _, _ = self.run_ok("patch-copy", p, dst, code_for(0x7FFF, 0x99, 0x42))
        self.assertEqual(code, 0)
        data = self.read(dst)
        self.assertEqual((len(data), data[0x7FFF]), (0x8000, 0x99))

    def test_patch_copy_compare_mismatch_leaves_the_byte_and_says_so(self):
        p = self.write("s.gb", make_gb(marker={0x201: b"\x05"}))
        dst = os.path.join(self.dir, "o.gb")
        code, out, _ = self.run_ok("patch-copy", p, dst, code_for(0x0201, 0x09, 0x77))
        self.assertIn("not applied", out)
        self.assertEqual(self.read(dst), self.read(p))

    def test_patch_copy_refuses_same_path_and_a_symlink_to_the_input(self):
        p = self.write("s.gb", make_gb(marker={0x201: b"\x05"}))
        before = self.read(p)
        self.assert_clean_error(self.run_ok("patch-copy", p, p, code_for(0x0201, 9)), "overwrite")
        link = os.path.join(self.dir, "link.gb")
        os.symlink(p, link)
        code, _, _ = self.run_ok("patch-copy", p, link, code_for(0x0201, 9))
        self.assertEqual(self.read(p), before, "input ROM was overwritten through a symlink")
        self.assertNotEqual(code, 0)

    def test_patch_copy_into_a_missing_directory_is_a_clean_error(self):
        p = self.write("s.gb", make_gb())
        dst = os.path.join(self.dir, "no_such_dir", "o.gb")
        self.assert_clean_error(self.run_ok("patch-copy", p, dst, code_for(0x0201, 9)), "no_such_dir")

    def test_patch_copy_with_one_bad_code_writes_nothing(self):
        p = self.write("b.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02))
        dst = os.path.join(self.dir, "o.gb")
        res = self.run_ok("patch-copy", p, dst, code_for(0x0201, 9), code_for(0x4010, 9))   # second needs a bank
        self.assert_clean_error(res, "not mapped")
        self.assertFalse(os.path.exists(dst))

    # ---- vet ----------------------------------------------------------------------------------------------------
    def test_vet_two_codes_in_one_instruction_gives_a_combined_finding(self):
        p = self.write("s.gb", make_gb(marker={0x200: bytes.fromhex("3E05")}))   # LD A,$05
        _, out, _ = self.run_ok("vet", p, code_for(0x0200, 0x18), code_for(0x0201, 0x10))
        self.assertIn("combined", out)
        self.assertIn("JR", out.split("combined")[1])

    def test_vet_patch_at_the_end_of_the_file_does_not_crash(self):
        p = self.write("s.gb", make_gb(marker={0x7FFD: bytes.fromhex("01")}))
        for addr in (0x7FFF, 0x7FFE, 0x7FFD):
            code, out, _ = self.run_ok("vet", p, code_for(addr, 0xC3))
            self.assertEqual(code, 0)
            self.assertIn(f"${addr:04X}", out)

    def test_vet_patch_at_the_end_of_a_bank_does_not_read_the_next_bank_as_code(self):
        p = self.write("b.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02,
                                       marker={0x3FFE: bytes.fromhex("01"), 0x4000: bytes.fromhex("D3")}))
        code, out, _ = self.run_ok("vet", p, code_for(0x3FFF, 0x00))
        self.assertEqual(code, 0)
        self.assertNotIn("unofficial-opcode-follows", out)   # the byte at $4000 depends on the bank, not on $3FFF

    def test_vet_header_area_is_flagged_at_both_edges_only(self):
        p = self.write("s.gb", make_gb())
        for addr in (0x0000, 0x00FF, 0x0100, 0x0148, 0x014F):
            self.assertIn("vector-area", self.run_ok("vet", p, code_for(addr, 0x00))[1], hex(addr))
        self.assertNotIn("vector-area", self.run_ok("vet", p, code_for(0x0150, 0x00))[1])

    def test_vet_on_unsupported_mapper_says_so(self):
        p = self.write("u.gb", make_gb(size=0x20000, cart=0x22, size_code=0x02))
        _, out, _ = self.run_ok("vet", p, code_for(0x0200, 0x00))
        self.assertIn("mapper-unsupported", out)
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0200", "--value", "00"), "mbc7")

    # ---- xrefs / disasm / id ------------------------------------------------------------------------------------
    def test_xrefs_finds_ldh_by_full_ff_address_and_not_by_the_low_byte(self):
        p = self.write("s.gb", make_gb(marker={0x200: bytes.fromhex("E040F040")}))   # LDH ($40),A ; LDH A,($40)
        out = self.run_ok("xrefs", p, "FF40")[1]
        self.assertIn("$0200 write", out)
        self.assertIn("$0202 read", out)
        self.assertNotIn("$0200 write", self.run_ok("xrefs", p, "0040")[1])

    def test_xrefs_to_zero_finds_calls_and_jumps(self):
        p = self.write("s.gb", make_gb(marker={0x300: bytes.fromhex("CD0000"), 0x500: bytes.fromhex("C30000")}))
        out = self.run_ok("xrefs", p, "0000")[1]
        self.assertIn("$0300 call", out)
        self.assertIn("$0500 jump", out)

    def test_xrefs_to_a_rst_vector_finds_the_rst(self):
        p = self.write("s.gb", make_gb(marker={0x400: bytes.fromhex("EF")}))   # RST $28
        self.assertIn("$0400", self.run_ok("xrefs", p, "0028")[1])

    def test_xrefs_jr_in_a_switchable_bank_resolves_its_target(self):
        # JR -2 (a jump to itself) at file offset 0xC100 = bank 3, CPU $4100
        p = self.write("b.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02, marker={3 * 0x4000 + 0x100: bytes.fromhex("18FE")}))
        out = self.run_ok("xrefs", p, "4100")[1]
        self.assertIn("0xC100", out.upper().replace("0XC100", "0xC100"))

    def test_xrefs_and_disasm_missing_arguments_name_what_is_missing(self):
        p = self.write("s.gb", make_gb())
        self.assert_clean_error(self.run_ok("xrefs", p), "address")
        self.assert_clean_error(self.run_ok("disasm", p, "0200"), "count")

    def test_disasm_count_formats(self):
        p = self.write("s.gb", make_gb(marker={0x200: b"\x3C" * 20}))
        self.assertEqual(self.run_ok("disasm", p, "0200", "5")[1].count("INC A"), 5)
        self.assertEqual(self.run_ok("disasm", p, "$0200", "$10")[1].count("INC A"), 16)   # $-prefixed count is hex
        self.assert_clean_error(self.run_ok("disasm", p, "0200", "abc"), "not a number")
        self.assert_clean_error(self.run_ok("disasm", p, "0200", "-3"), "count")
        self.assert_clean_error(self.run_ok("disasm", p, "0200", "0"), "count")

    def test_disasm_outside_rom_or_unbanked_is_refused(self):
        b = self.write("b.gb", make_gb(size=0x20000, cart=0x01, size_code=0x02))
        self.assert_clean_error(self.run_ok("disasm", b, "4000", "2"), "bank")
        self.assert_clean_error(self.run_ok("disasm", b, "8000", "2", "--bank", "1"), "not mapped")

    def test_id_on_cgb_only_cart_with_unsupported_mapper(self):
        p = self.write("c.gb", make_gb(size=0x20000, cart=0x22, size_code=0x02, cgb=0xC0))
        code, out, _ = self.run_ok("id", p)
        self.assertEqual(code, 0)
        for want in ("cgb: only", "mbc: MBC7", "supported: False"):
            self.assertIn(want, out)

    def test_id_on_unknown_cart_type_names_the_byte(self):
        p = self.write("c.gb", make_gb(cart=0x42))
        self.assertIn("unknown (type $42)", self.run_ok("id", p)[1])


if __name__ == "__main__":
    unittest.main()
