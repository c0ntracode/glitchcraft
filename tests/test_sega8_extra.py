"""Adversarial Game Gear / Master System tests: hostile or sloppy input should give a specific message, never a
traceback and never silently wrong output."""
import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli, vet
from glitchcraft.core import GlitchError, Patch
from glitchcraft.sega8 import codec, dis_z80, rom
from test_sega8_rom import make_sega8

KB16 = 0x4000


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def code_for(addr, value, compare=None):
    return codec.encode(Patch(addr, value, compare))


def text_at(data, addr, count=1):
    return [i.text for i in dis_z80.disassemble(data, addr, count)]


class Sega8ExtraTests(unittest.TestCase):
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

    def banked(self, name="b.gg", size=0x20000, marker=None, **kw):
        return self.write(name, make_sega8(size=size, size_nibble=0xF, marker=marker, **kw))

    # ---- identification -----------------------------------------------------------------------------------------
    def test_header_at_3ff0_with_data_beyond_is_found_and_banked(self):
        info = rom.identify(make_sega8(size=0x20000, header_at=0x3FF0))
        self.assertEqual((info.details["header_at"], info.details["mapper"], info.details["banks"]), (0x3FF0, "Sega", 8))

    def test_header_at_1ff0_with_data_beyond_is_found(self):
        info = rom.identify(make_sega8(size=0x20000, header_at=0x1FF0))
        self.assertEqual(info.details["header_at"], 0x1FF0)

    def test_two_signatures_prefer_the_highest_location(self):
        sig = b"TMR SEGA" + bytes(2) + bytes([0x34, 0x12, 0x26, 0x70, 0x4C])   # region 4 (SMS Export) at 3FF0
        info = rom.identify(make_sega8(size=0x8000, region=0x6, marker={0x3FF0: sig}))
        self.assertEqual((info.details["header_at"], info.details["system"]), (0x7FF0, "Game Gear"))

    def test_signature_cut_off_by_end_of_file_is_not_a_header(self):
        data = bytearray(0x7FF8)
        data[0x7FF0:0x7FF8] = b"TMR SEGA"            # the other 8 header bytes are missing
        self.assertIsNone(rom.identify(bytes(data)))
        p = self.write("cut.gg", bytes(data))
        self.assert_clean_error(self.run_ok("id", p), "not recognized")

    def test_cut_off_signature_falls_back_to_a_complete_lower_header(self):
        data = bytearray(make_sega8(size=0x8000, header_at=0x3FF0))
        data = data[:0x7FF8]
        data[0x7FF0:0x7FF8] = b"TMR SEGA"
        self.assertEqual(rom.identify(bytes(data)).details["header_at"], 0x3FF0)

    def test_unknown_region_nibble_is_reported_and_id_still_works(self):
        p = self.write("u.gg", make_sega8(region=0x9))
        code, out, _ = self.run_ok("id", p)
        self.assertEqual(code, 0)
        self.assertIn("system: unknown", out)
        self.assertIn("region: unknown ($9)", out)

    def test_unknown_size_nibble_is_reported_not_refused(self):
        info = rom.identify(make_sega8(size_nibble=0x3))
        self.assertEqual(info.details["header_size"], "unknown ($3)")

    def test_rom_smaller_than_the_smallest_header_slot_is_not_recognized(self):
        for size in (0x10, 0x1000, 0x1FFF):
            p = self.write(f"t{size}.gg", make_sega8(size=size, header_at=0))
            self.assert_clean_error(self.run_ok("id", p), "not recognized")

    def test_8kb_rom_with_header_at_1ff0_is_recognized(self):
        self.assertIsNotNone(rom.identify(make_sega8(size=0x2000, header_at=0x1FF0)))

    def test_48kb_is_unmapped_and_one_byte_more_is_the_sega_mapper(self):
        for size, mapper, banks in ((0xC000, "none", 3), (0xC001, "Sega", 4), (0x10000, "Sega", 4)):
            d = rom.identify(make_sega8(size=size)).details
            self.assertEqual((d["mapper"], d["banks"]), (mapper, banks), hex(size))

    def test_64kb_needs_a_bank_above_slot_0_but_48kb_does_not(self):
        flat = self.write("f.gg", make_sega8(size=0xC000, marker={0xBFFF: b"\x42", 0x9000: b"\x37"}))
        big = self.write("g.gg", make_sega8(size=0x10000, marker={0x9000: b"\x37"}))
        self.assertIn("original=$42", self.run_ok("decode", flat, code_for(0xBFFF, 0))[1])
        self.assertIn("original=$37", self.run_ok("decode", flat, code_for(0x9000, 0))[1])
        self.assert_clean_error(self.run_ok("make", big, "--addr", "9000", "--value", "00"), "bank")
        self.assertIn("original: $37", self.run_ok("make", big, "--addr", "9000", "--value", "00", "--bank", "2")[1])

    def test_size_nibble_disagreeing_with_file_size_follows_the_file(self):
        small = rom.identify(make_sega8(size=0x8000, size_nibble=0xF)).details      # header says 128 KB, file is 32 KB
        self.assertEqual((small["mapper"], small["banks"], small["header_size"]), ("none", 2, "128 KB"))
        big = rom.identify(make_sega8(size=0x20000, size_nibble=0xC)).details       # header says 32 KB, file is 128 KB
        self.assertEqual((big["mapper"], big["banks"]), ("Sega", 8))

    def test_codemasters_header_is_identified_and_mapped_with_a_bank(self):
        banks = 8
        marker = {0x7FE0: bytes([banks]), 0x7FE6: (0x1234).to_bytes(2, "little"),
                  0x7FE8: ((0x10000 - 0x1234) & 0xFFFF).to_bytes(2, "little"), 3 * 0x4000 + 0x10: b"\x3C"}
        p = self.write("cm.gg", make_sega8(size=0x20000, size_nibble=0xF, marker=marker))
        self.assertIn("mapper: Codemasters", self.run_ok("id", p)[1])
        self.assertIn("bank-dependent", self.run_ok("vet", p, code_for(0x4010, 0))[1])
        code, out, _ = self.run_ok("make", p, "--addr", "4010", "--value", "00", "--bank", "3")
        self.assertEqual(code, 0)
        self.assertIn("original: $3C", out)

    def test_ordinary_rom_with_zero_checksum_is_not_taken_for_codemasters(self):
        self.assertEqual(rom.identify(make_sega8(size=0x20000)).details["mapper"], "Sega")

    # ---- codes --------------------------------------------------------------------------------------------------
    def test_code_forms_lowercase_ok_wrong_lengths_and_spaces_refused(self):
        p = self.write("s.gg", make_sega8(marker={0x201: b"\x05"}))
        c = code_for(0x0201, 0x09, 0x05)
        self.assertEqual(self.run_ok("decode", p, c)[1], self.run_ok("decode", p, c.lower())[1])
        self.assert_clean_error(self.run_ok("decode", p, "01A-2B3-4C"), "6 or 9")        # 8 digits
        self.assert_clean_error(self.run_ok("decode", p, "01A-2B3-4C5D"), "6 or 9")      # 10 digits
        self.assert_clean_error(self.run_ok("decode", p, "01A 2B3"), "6 or 9")
        self.assert_clean_error(self.run_ok("decode", p, "01A-2B3-4C5-6"), "6 or 9")     # too many groups
        self.assert_clean_error(self.run_ok("decode", p, ""), "6 or 9")
        self.assert_clean_error(self.run_ok("vet", p, "01A-2B3-4C"), "6 or 9")

    def test_wrong_h_digit_is_ignored_like_the_hardware_and_decodes_the_same(self):
        good = code_for(0x0201, 0x09, 0x05)       # ABC-DEF-GHI, H is the xor-8 filler
        bad = good[:9] + ("0" if good[9] != "0" else "1") + good[10:]
        self.assertNotEqual(good, bad)
        self.assertEqual(codec.decode(good), codec.decode(bad))

    def test_address_bfff_is_the_last_patchable_and_c000_is_refused_everywhere(self):
        p = self.write("s.gg", make_sega8(size=0xC000, marker={0xBFFF: b"\x42"}))
        self.assertEqual(codec.decode("00F-FF4").address, 0xBFFF)
        self.assertIn("$BFFF", self.run_ok("decode", p, "00F-FF4")[1])
        self.assertEqual(codec.decode(code_for(0xBFFF, 0x11, 0x42)).compare, 0x42)
        self.assertIn("round-trip: ok", self.run_ok("make", p, "--addr", "BFFF", "--value", "11", "--compare", "42")[1])
        for argv in (("decode", p, "000-003"), ("vet", p, "000-003"), ("patch-copy", p, os.path.join(self.dir, "o"), "000-003")):
            self.assert_clean_error(self.run_ok(*argv), "c000")
        for addr in ("C000", "FFFF", "10000"):
            self.assert_clean_error(self.run_ok("make", p, "--addr", addr, "--value", "00"), "outside")
        self.assertRaises(GlitchError, codec.encode, Patch(0xC000, 0))

    def test_make_value_compare_and_address_garbage_are_refused(self):
        p = self.write("s.gg", make_sega8())
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0200", "--value", "100"), "one byte")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0200", "--value", "1", "--compare", "100"), "one byte")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "zzzz", "--value", "00"), "hex")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0200"), "value")

    def test_make_compare_that_differs_from_the_rom_is_refused(self):
        p = self.write("s.gg", make_sega8(marker={0x201: b"\x05"}))
        self.assert_clean_error(self.run_ok("make", p, "--addr", "0201", "--value", "09", "--compare", "77"), "differs")

    def test_past_the_end_of_an_unbanked_rom_is_not_blamed_on_a_missing_bank(self):
        p = self.write("s.gg", make_sega8(size=0x8000))   # 32 KB, no mapper: $9000 simply is not there
        res = self.run_ok("make", p, "--addr", "9000", "--value", "00")
        code, out, err = res
        self.assertNotEqual(code, 0)
        self.assertNotIn("switchable", err, "an unbanked ROM has no bank to give")
        self.assertNotIn("bank-dependent", self.run_ok("decode", p, code_for(0x9000, 0))[1])
        self.assertNotIn("bank-dependent", self.run_ok("vet", p, code_for(0x9000, 0))[1])

    # ---- banks --------------------------------------------------------------------------------------------------
    def test_bank_selects_the_slot_the_address_is_in(self):
        marks = {b * KB16 + o: bytes([0x80 + b]) for b in range(8) for o in (0x10, 0x500)}
        p = self.banked(marker=marks)
        cases = (("4010", "3", 0x83), ("8010", "5", 0x85), ("4010", "0", 0x80),   # slot 1 and 2, bank 0 in a switchable slot
                 ("0500", "4", 0x84), ("0500", None, 0x80))                       # slot 0 past the first 1 KB follows --bank
        for addr, bank, want in cases:
            extra = ("--bank", bank) if bank else ()
            _, out, _ = self.run_ok("make", p, "--addr", addr, "--value", "00", *extra)
            self.assertIn(f"original: ${want:02X}", out, (addr, bank))

    def test_first_kilobyte_is_fixed_whatever_the_bank(self):
        p = self.banked(marker={0x200: b"\x11", 3 * KB16 + 0x200: b"\x22"})
        for bank in ("0", "3", "7"):
            self.assertIn("original: $11", self.run_ok("make", p, "--addr", "0200", "--value", "00", "--bank", bank)[1])
        self.assertIn("original=$11", self.run_ok("decode", p, code_for(0x0200, 0), "--bank", "3")[1])
        self.assertNotIn("original=$22", self.run_ok("vet", p, code_for(0x0200, 0), "--bank", "3")[1])

    def test_bank_forms_decimal_hex_and_equals(self):
        p = self.write("big.gg", make_sega8(size=0x88000, size_nibble=0x1, marker={0x20 * KB16 + 0x10: b"\xAB"}))
        for bank in (("--bank", "32"), ("--bank", "0x20"), ("--bank=32",), ("--bank=0x20",)):
            code, out, _ = self.run_ok("make", p, "--addr", "4010", "--value", "00", *bank)
            self.assertEqual(code, 0, bank)
            self.assertIn("original: $AB", out)
        for cmd in (("decode", p, code_for(0x4010, 0), "--bank=0x20"), ("vet", p, code_for(0x4010, 0), "--bank=0x20")):
            self.assertIn("$AB", self.run_ok(*cmd)[1].upper())

    def test_bank_out_of_range_names_the_range_in_every_command(self):
        p = self.banked()
        for cmd in (("make", p, "--addr", "4010", "--value", "00", "--bank", "8"),
                    ("vet", p, "--bank", "8", code_for(0x4010, 0)),
                    ("decode", p, "--bank", "8", code_for(0x4010, 0)),
                    ("disasm", p, "4010", "2", "--bank", "8"),
                    ("patch-copy", p, os.path.join(self.dir, "o.gg"), "--bank", "8", code_for(0x4010, 0))):
            self.assert_clean_error(self.run_ok(*cmd), "out of range")

    def test_negative_non_numeric_and_missing_bank_values_name_the_option(self):
        p = self.banked()
        for cmd in (("make", p, "--addr", "4010", "--value", "00", "--bank=-1"),
                    ("vet", p, "--bank", "-1", code_for(0x4010, 0)),
                    ("disasm", p, "4010", "3", "--bank", "-2")):
            self.assert_clean_error(self.run_ok(*cmd), "bank")
        self.assert_clean_error(self.run_ok("vet", p, "--bank", "abc", code_for(0x4010, 0)), "--bank")
        self.assert_clean_error(self.run_ok("vet", p, "--bank", "08", code_for(0x4010, 0)), "--bank")
        self.assert_clean_error(self.run_ok("vet", p, code_for(0x4010, 0), "--bank"), "--bank")
        self.assert_clean_error(self.run_ok("make", p, "--addr", "4010", "--value", "0", "--bank"), "--bank")

    def test_bank_on_a_rom_without_a_mapper_is_not_silently_ignored(self):
        p = self.write("small.gg", make_sega8())   # 32 KB: two banks at most
        code, _, _ = self.run_ok("make", p, "--addr", "4010", "--value", "00", "--bank", "5")
        self.assertNotEqual(code, 0, "bank 5 does not exist in a 2-bank ROM but was accepted")

    def test_bank_past_a_truncated_dump_gives_a_specific_error_everywhere(self):
        p = self.banked(size=0x10100)    # 5 banks by size, but bank 4 holds only 0x100 bytes
        self.assertEqual(self.run_ok("make", p, "--addr", "4050", "--value", "00", "--bank", "4")[0], 0)
        for cmd in (("make", p, "--addr", "4200", "--value", "00", "--bank", "4"),
                    ("decode", p, "--bank", "4", code_for(0x4200, 0)),
                    ("vet", p, "--bank", "4", code_for(0x4200, 0)),
                    ("disasm", p, "4200", "2", "--bank", "4"),
                    ("patch-copy", p, os.path.join(self.dir, "o.gg"), "--bank", "4", code_for(0x4200, 0))):
            self.assert_clean_error(self.run_ok(*cmd), "truncated")

    def test_banked_rom_address_without_a_bank_asks_for_one_everywhere(self):
        p = self.banked()
        self.assertIn("bank-dependent", self.run_ok("decode", p, code_for(0x4010, 0))[1])
        self.assertIn("bank-dependent", self.run_ok("vet", p, code_for(0x4010, 0))[1])
        self.assert_clean_error(self.run_ok("make", p, "--addr", "4010", "--value", "0"), "bank")
        self.assert_clean_error(self.run_ok("disasm", p, "4010", "2"), "bank")

    def test_patch_copy_with_bank_changes_only_that_bank(self):
        p = self.banked(marker={3 * KB16 + 0x10: b"\x05", 5 * KB16 + 0x10: b"\x05"})
        dst = os.path.join(self.dir, "o.gg")
        code, _, _ = self.run_ok("patch-copy", p, dst, "--bank", "3", code_for(0x4010, 0x99, 0x05))
        self.assertEqual(code, 0)
        a, b = self.read(p), self.read(dst)
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        self.assertEqual(diff, [3 * KB16 + 0x10])
        self.assertEqual(b[3 * KB16 + 0x10], 0x99)

    # ---- patch-copy ---------------------------------------------------------------------------------------------
    def test_patch_copy_can_patch_the_last_byte_of_a_banked_rom(self):
        p = self.banked(marker={0x1FFFF: b"\x42"})
        dst = os.path.join(self.dir, "o.gg")
        code, _, _ = self.run_ok("patch-copy", p, dst, "--bank", "7", code_for(0x7FFF, 0x99, 0x42))
        self.assertEqual(code, 0)
        data = self.read(dst)
        self.assertEqual((len(data), data[-1]), (0x20000, 0x99))

    def test_patch_copy_compare_mismatch_leaves_the_byte_and_says_so(self):
        p = self.write("s.gg", make_sega8(marker={0x201: b"\x05"}))
        dst = os.path.join(self.dir, "o.gg")
        code, out, _ = self.run_ok("patch-copy", p, dst, code_for(0x0201, 0x09, 0x77))
        self.assertEqual(code, 0)
        self.assertIn("not applied", out)
        self.assertEqual(self.read(dst), self.read(p))

    def test_patch_copy_refuses_same_path_symlink_and_hard_link_to_the_input(self):
        p = self.write("s.gg", make_sega8(marker={0x201: b"\x05"}))
        before = self.read(p)
        self.assert_clean_error(self.run_ok("patch-copy", p, p, code_for(0x0201, 9)), "overwrite")
        link, hard = os.path.join(self.dir, "link.gg"), os.path.join(self.dir, "hard.gg")
        os.symlink(p, link)
        os.link(p, hard)
        for target in (link, hard):
            self.assert_clean_error(self.run_ok("patch-copy", p, target, code_for(0x0201, 9)), "overwrite")
            self.assertEqual(self.read(p), before, f"input ROM was overwritten through {target}")

    def test_patch_copy_into_a_missing_directory_or_onto_a_directory_is_a_clean_error(self):
        p = self.write("s.gg", make_sega8())
        self.assert_clean_error(self.run_ok("patch-copy", p, os.path.join(self.dir, "no_such_dir", "o.gg"),
                                            code_for(0x0201, 9)), "no_such_dir")
        self.assert_clean_error(self.run_ok("patch-copy", p, self.dir, code_for(0x0201, 9)), "cannot write")

    def test_patch_copy_with_one_unmapped_code_writes_nothing(self):
        p = self.banked()
        dst = os.path.join(self.dir, "o.gg")
        self.assert_clean_error(self.run_ok("patch-copy", p, dst, code_for(0x0201, 9), code_for(0x4010, 9)), "not mapped")
        self.assertFalse(os.path.exists(dst))

    def test_patch_copy_with_no_codes_says_so_instead_of_writing_a_plain_copy(self):
        p = self.write("s.gg", make_sega8())
        dst = os.path.join(self.dir, "o.gg")
        self.assert_clean_error(self.run_ok("patch-copy", p, dst), "code")
        self.assertFalse(os.path.exists(dst))

    def test_patch_copy_with_missing_output_names_the_usage(self):
        p = self.write("s.gg", make_sega8())
        self.assert_clean_error(self.run_ok("patch-copy", p), "usage")

    def test_decode_and_vet_with_no_code_say_so(self):
        p = self.write("s.gg", make_sega8())
        self.assert_clean_error(self.run_ok("decode", p), "code")
        self.assert_clean_error(self.run_ok("vet", p), "code")

    # ---- disassembler -------------------------------------------------------------------------------------------
    def test_truncated_prefixes_and_operands_at_the_end_of_data_become_bytes(self):
        for tail in ("DD", "FD", "ED", "CB", "DDCB01", "FDCB", "DD21", "DD2100", "ED43", "ED4300", "CD00", "3E", "DD36"):
            out = text_at(bytes.fromhex(tail), 0x100, 8)
            self.assertTrue(out[0].startswith(".byte"), (tail, out))   # what follows a lone prefix byte is decoded on its own
            self.assertEqual(out[0], f".byte ${int(tail[:2], 16):02X}", (tail, out))

    def test_complete_prefixed_instructions_are_not_truncated(self):
        self.assertEqual(text_at(bytes.fromhex("DDCB017E"), 0, 1), ["BIT 7,(IX+$01)"])
        self.assertEqual(text_at(bytes.fromhex("ED4300C0"), 0, 1), ["LD ($C000),BC"])
        self.assertEqual(text_at(bytes.fromhex("FD360512"), 0, 1), ["LD (IY+$05),$12"])
        self.assertEqual(text_at(bytes.fromhex("CB3C"), 0, 1), ["SRL H"])

    def test_useless_prefix_chains_decode_the_instruction_that_really_runs(self):
        self.assertEqual(text_at(bytes.fromhex("DDDDFD213412"), 0, 3), ["NOP ; DD", "NOP ; DD", "LD IY,$1234"])
        self.assertEqual(text_at(bytes.fromhex("DDED4D"), 0, 2), ["NOP ; DD", "RETI"])

    def test_relative_jumps_across_a_bank_boundary_compute_the_cpu_target(self):
        self.assertEqual(text_at(bytes.fromhex("1810"), 0x3FFE), ["JR $4010"])
        self.assertEqual(text_at(bytes.fromhex("18FC"), 0x4000), ["JR $3FFE"])
        self.assertEqual(text_at(bytes.fromhex("10FE"), 0x7FFE), ["DJNZ $7FFE"])
        self.assertEqual(text_at(bytes.fromhex("2005"), 0xBFFE), ["JR NZ,$C005"])      # runs into RAM; not wrapped
        self.assertEqual(text_at(bytes.fromhex("1880"), 0x0000), ["JR $FF82"])         # wraps below zero

    def test_disasm_count_formats(self):
        p = self.write("s.gg", make_sega8(marker={0x200: b"\x3C" * 20}))
        self.assertEqual(self.run_ok("disasm", p, "0200", "5")[1].count("INC A"), 5)
        self.assertEqual(self.run_ok("disasm", p, "$0200", "$10")[1].count("INC A"), 16)
        for bad in ("abc", "-3", "0", "1.5"):
            self.assert_clean_error(self.run_ok("disasm", p, "0200", bad), "count" if bad in ("-3", "0") else "number")
        self.assert_clean_error(self.run_ok("disasm", p, "0200"), "count")

    def test_disasm_huge_count_stops_at_the_end_of_the_file(self):
        p = self.write("s.gg", make_sega8(size=0x2000, header_at=0x1FF0))
        code, out, _ = self.run_ok("disasm", p, "1FF0", str(10 ** 9))
        self.assertEqual(code, 0)
        self.assertLessEqual(len(out.splitlines()), 16)

    def test_disasm_ram_or_unbanked_address_is_refused(self):
        p = self.banked()
        self.assert_clean_error(self.run_ok("disasm", p, "C000", "2", "--bank", "1"), "not mapped")
        self.assert_clean_error(self.run_ok("disasm", p, "4000", "2"), "bank")

    def test_disasm_does_not_run_an_instruction_into_the_next_bank(self):
        p = self.banked(marker={KB16 - 1: b"\x3E", KB16: b"\x55"})   # LD A,n as the last byte of bank 0
        out = self.run_ok("disasm", p, "3FFF", "1")[1]
        self.assertIn(".byte $3E", out, "the operand byte at $4000 depends on the bank in slot 1, not on bank 1 in the file")

    # ---- xrefs --------------------------------------------------------------------------------------------------
    def test_xrefs_finds_every_form_of_ram_variable_access(self):
        forms = {0x300: ("32 00 C0", "write"), 0x320: ("3A 00 C0", "read"), 0x340: ("22 00 C0", "write"),
                 0x360: ("2A 00 C0", "read"), 0x380: ("ED 43 00 C0", "write"), 0x3A0: ("ED 5B 00 C0", "read"),
                 0x3C0: ("ED 73 00 C0", "write"), 0x3E0: ("DD 22 00 C0", "write"), 0x400: ("FD 2A 00 C0", "read")}
        p = self.write("s.gg", make_sega8(marker={o: bytes.fromhex(b) for o, (b, _) in forms.items()}))
        out = self.run_ok("xrefs", p, "C000")[1]
        for off, (_, kind) in forms.items():
            self.assertIn(f"${off:04X} {kind}", out)

    def test_xrefs_finds_an_instruction_hidden_behind_a_useless_dd_prefix(self):
        p = self.write("s.gg", make_sega8(marker={0x500: bytes.fromhex("DD3200C0")}))   # DD is ignored by LD (nn),A
        self.assertIn("$0501 write", self.run_ok("xrefs", p, "C000")[1])

    def test_xrefs_to_a_rst_vector_finds_rst_even_as_the_last_byte_of_the_file(self):
        p = self.write("s.gg", make_sega8(size=0x4001, header_at=0x3FF0, marker={0x400: b"\xEF", 0x4000: b"\xFF"}))
        out = self.run_ok("xrefs", p, "0028")[1]
        self.assertIn("$0400", out)
        self.assertIn("$4000", self.run_ok("xrefs", p, "0038")[1])

    def test_xrefs_in_a_switchable_bank_report_the_file_offset(self):
        p = self.banked(marker={3 * KB16 + 0x100: bytes.fromhex("3200C0")})
        out = self.run_ok("xrefs", p, "C000")[1]
        self.assertIn("file offset 0xC100 (bank-dependent)", out)

    def test_xrefs_jr_across_the_bank_boundary_resolves_its_target(self):
        p = self.banked(marker={KB16 - 2: bytes.fromhex("1810")})
        self.assertIn("$3FFE jump", self.run_ok("xrefs", p, "4010")[1])

    def test_xrefs_does_not_stitch_an_operand_from_the_next_bank(self):
        p = self.banked(marker={KB16 - 1: b"\x32", KB16: bytes.fromhex("00C0")})   # LD (nn),A split across banks
        self.assertNotIn("$3FFF", self.run_ok("xrefs", p, "C000")[1])

    def test_xrefs_bad_arguments(self):
        p = self.write("s.gg", make_sega8())
        self.assert_clean_error(self.run_ok("xrefs", p), "address")
        self.assert_clean_error(self.run_ok("xrefs", p, "zz"), "hex")

    # ---- vet ----------------------------------------------------------------------------------------------------
    def test_vet_patch_at_the_end_of_the_file_does_not_crash(self):
        p = self.banked(marker={0x1FFFE: bytes.fromhex("CD"), 0x1FFFD: b"\x3E"})
        for addr, value in ((0x7FFF, 0xC3), (0x7FFF, 0xDD), (0x7FFF, 0xED), (0x7FFF, 0xCB), (0x7FFF, 0xFD), (0x7FFE, 0x00)):
            code, out, err = self.run_ok("vet", p, "--bank", "7", code_for(addr, value))
            self.assertEqual(code, 0, (addr, value, err))
            self.assertIn(f"${addr:04X}", out)

    def test_vet_truncated_instruction_at_the_end_of_a_bank_does_not_crash(self):
        p = self.banked(marker={KB16 - 1: bytes.fromhex("CD")})
        code, out, _ = self.run_ok("vet", p, code_for(0x3FFF, 0xC9))
        self.assertEqual(code, 0)
        self.assertIn("RET", out)

    def test_vet_patch_at_the_end_of_a_bank_does_not_read_the_next_bank_as_code(self):
        p = self.banked(marker={0x3FFE: bytes.fromhex("C9"), 0x4000: bytes.fromhex("ED77")})   # RET, then an undefined ED op
        code, out, _ = self.run_ok("vet", p, code_for(0x3FFE, 0x00))
        self.assertEqual(code, 0)
        self.assertNotIn("unofficial-opcode-follows", out)   # what follows $3FFF in slot 1 depends on the bank

    def test_vet_one_byte_opcode_turned_into_cb_consumes_the_next_byte(self):
        p = self.write("s.gg", make_sega8(marker={0x200: bytes.fromhex("003C00")}))
        _, out, _ = self.run_ok("vet", p, code_for(0x0200, 0xCB))
        self.assertIn("NOP -> SRL H", out)
        self.assertIn("opcode-class-change", out)

    def test_vet_one_byte_opcode_turned_into_ed_and_dd_fd_is_flagged(self):
        p = self.write("s.gg", make_sega8(marker={0x200: bytes.fromhex("004D00"), 0x300: bytes.fromhex("003C00"),
                                                 0x400: bytes.fromhex("00213412")}))
        out = self.run_ok("vet", p, code_for(0x0200, 0xED))[1]
        self.assertIn("RETI", out)
        self.assertIn("control-flow-change", out)
        for off, op in ((0x300, 0xDD), (0x300, 0xFD), (0x300, 0xED), (0x400, 0xFD)):
            self.assertIn("opcode-class-change", self.run_ok("vet", p, code_for(off, op))[1], (off, op))
        self.assertIn("IY", self.run_ok("vet", p, code_for(0x0400, 0xFD))[1])

    def test_vet_patch_after_a_useless_prefix_describes_the_instruction_that_will_run(self):
        # DD 00 34 12: executing from $0500 the DD makes a patched 00->21 into LD IX,$1234, not LD HL,$1234
        p = self.write("s.gg", make_sega8(marker={0x500: bytes.fromhex("DD003412")}))
        _, out, _ = self.run_ok("vet", p, code_for(0x0501, 0x21))
        self.assertIn("IX", out)

    def test_vet_jr_patched_across_a_bank_boundary_shows_the_cpu_target(self):
        p = self.banked(marker={0x3FFE: bytes.fromhex("0010")})
        code, out, _ = self.run_ok("vet", p, code_for(0x3FFE, 0x18))
        self.assertEqual(code, 0)
        self.assertIn("JR $4010", out)
        self.assertIn("control-flow-change", out)

    def test_vet_jp_patched_into_ram_or_a_banked_slot_has_no_target_listing_and_no_crash(self):
        p = self.banked(marker={0x200: bytes.fromhex("C31111")})
        for lo, hi in ((0x00, 0xC0), (0x10, 0x40)):
            code, out, _ = self.run_ok("vet", p, code_for(0x0201, lo), code_for(0x0202, hi))
            self.assertEqual(code, 0)
            self.assertIn("combined", out)

    def test_vet_vector_and_header_area_flags(self):
        p = self.write("s.gg", make_sega8())
        for addr in (0x0000, 0x0066, 0x7FF0, 0x7FFF):
            self.assertIn("vector-area", self.run_ok("vet", p, code_for(addr, 0x00))[1], hex(addr))
        for addr in (0x0067, 0x7FEF):
            self.assertNotIn("vector-area", self.run_ok("vet", p, code_for(addr, 0x00))[1], hex(addr))

    def test_vet_compare_mismatch_is_flagged_and_says_it_will_not_apply(self):
        p = self.write("s.gg", make_sega8(marker={0x201: b"\x05"}))
        _, out, _ = self.run_ok("vet", p, code_for(0x0201, 0x09, 0x77))
        self.assertIn("compare-mismatch", out)
        self.assertIn("will not apply", out)

    def test_vet_empty_code_list_through_the_api_is_an_empty_report(self):
        report = vet.vet(make_sega8(), [])
        self.assertEqual((report.findings, report.combined), ([], []))


if __name__ == "__main__":
    unittest.main()
