import contextlib
import io
import os
import tempfile
import unittest

import _path  # noqa: F401
from glitchcraft import cli
from glitchcraft.core import Patch
from glitchcraft.nes import codec
from test_vet import LIVES_SITE, PRANK_SITE, make_nes


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


STORE_SITE = {0x9300: "8D 33 04 60"}     # STA $0433 ; RTS


class DisplacedInstructionTests(unittest.TestCase):
    """A patch that swaps an opcode stops the original instruction from running; `vet` must say so."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.rom = os.path.join(self.dir.name, "g.nes")
        with open(self.rom, "wb") as f:
            f.write(make_nes(plant={**STORE_SITE, **PRANK_SITE, **LIVES_SITE}))

    def codes(self, *patches):
        return [codec.encode(Patch(a, v, c)) for a, v, c in patches]

    def test_three_byte_rewrite_reports_one_displaced_note_naming_the_original(self):
        # STA $0433 -> INC $03C4 takes an opcode byte and both operand bytes
        codes = self.codes((0x9300, 0xEE, 0x8D), (0x9301, 0xC4, 0x33), (0x9302, 0x03, 0x04))
        _, out, _ = run("vet", self.rom, *codes)
        self.assertIn("STA $0433 -> INC $03C4", out)
        self.assertEqual(out.count("displaced:"), 1, out)
        self.assertIn("displaced: STA $0433 no longer runs", out)

    def test_a_single_opcode_change_reports_the_displaced_instruction(self):
        _, out, _ = run("vet", self.rom, "KTGOYX")
        self.assertIn("displaced: BCC $9264 no longer runs", out)

    def test_a_plain_value_change_reports_nothing_displaced(self):
        _, out, _ = run("vet", self.rom, "AATOZE")
        self.assertNotIn("displaced:", out)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.rom = self.path("game.nes", make_nes(plant={**LIVES_SITE, **PRANK_SITE}))

    def path(self, name, data):
        p = os.path.join(self.dir.name, name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def test_id_reports_platform_and_hash(self):
        code, out, _ = run("id", self.rom)
        self.assertEqual(code, 0)
        self.assertIn("platform: nes", out)
        self.assertIn("sha1: ", out)
        self.assertIn("mapper: 0", out)

    def test_decode_shows_original_byte(self):
        code, out, _ = run("decode", self.rom, "AATOZE")
        self.assertEqual(code, 0)
        self.assertIn("$906A", out)
        self.assertIn("original=$02", out)

    def test_make_prints_roundtrip_ok(self):
        code, out, _ = run("make", self.rom, "--addr", "906A", "--value", "08")
        self.assertEqual(code, 0)
        self.assertIn("code: AATOZE", out)
        self.assertIn("original: $02", out)
        self.assertIn("round-trip: ok", out)

    def test_make_with_compare_gives_eight_letters(self):
        code, out, _ = run("make", self.rom, "--addr", "906A", "--value", "08", "--compare", "02")
        self.assertEqual(code, 0)
        self.assertEqual(codec.decode(out.split("code: ")[1].split()[0]), Patch(0x906A, 8, 2))

    def test_make_refuses_bank_dependent_address(self):
        banked = self.path("banked.nes", make_nes(prg_banks=8, mapper=1))
        code, _, err = run("make", banked, "--addr", "8000", "--value", "11")
        self.assertEqual(code, 2)
        self.assertIn("bank", err)

    def test_xrefs_finds_indexed_reads_and_writes_of_the_base_address(self):
        rom = self.path("idx.nes", make_nes(plant={0x9100: "BD 16 40", 0x9110: "B9 16 40", 0x9120: "9D 16 40",
                                                   0x9130: "B5 16", 0x9140: "A1 16", 0x9150: "B1 16"}))
        _, out, _ = run("xrefs", rom, "4016")
        for addr in ("$9100", "$9110", "$9120"):
            self.assertIn(addr, out)
        _, out, _ = run("xrefs", rom, "0016")
        for addr in ("$9130", "$9140", "$9150"):
            self.assertIn(addr, out)

    def test_xrefs_lists_hits(self):
        code, out, _ = run("xrefs", self.rom, "075A")
        self.assertEqual(code, 0)
        self.assertIn("$906B write", out)

    def test_disasm_prints_address_bytes_text(self):
        code, out, _ = run("disasm", self.rom, "9069", "2")
        self.assertEqual(code, 0)
        self.assertIn("$9069: A9 02", out)
        self.assertIn("LDA #$02", out)
        self.assertIn("STA $075A", out)

    def test_vet_prints_flags(self):
        code, out, _ = run("vet", self.rom, "KTGOYX")
        self.assertEqual(code, 0)
        self.assertIn("brk-follows", out)
        self.assertIn("BCC $9264 -> CPX $AD13", out)

    def test_vet_prints_jump_target_listing(self):
        site = make_nes(plant={0x8251: "C9 90 D0 03 4C D8 82", 0x91DE: "A9 00 8D 72 07 A9 03 8D 70 07 60"})
        path = self.path("jump.nes", site)
        code, out, _ = run("vet", path, "VIIATX", "OPIAYZ")
        self.assertEqual(code, 0)
        self.assertIn("target: $91DE LDA #$00", out)
        self.assertIn("STA $0770", out)

    def test_make_refuses_compare_that_would_never_apply(self):
        code, _, err = run("make", self.rom, "--addr", "906A", "--value", "08", "--compare", "99")
        self.assertEqual(code, 2)
        self.assertIn("will not apply", err)

    def test_vet_states_compare_mismatch_in_words(self):
        bad = codec.encode(Patch(0x906A, 8, 0x99))
        code, out, _ = run("vet", self.rom, bad)
        self.assertEqual(code, 0)
        self.assertIn("will not apply on this dump", out)

    def test_make_with_ram_address_says_game_genie_patches_rom(self):
        code, _, err = run("make", self.rom, "--addr", "075A", "--value", "08")
        self.assertEqual(code, 2)
        self.assertIn("RAM", err)
        self.assertNotIn("--bank", err)

    def test_vet_notes_boundaries_are_inferred(self):
        _, out, _ = run("vet", self.rom, "AATOZE")
        self.assertIn("linear sweep", out)

    def test_xrefs_prints_hits_outside_the_cpu_map_by_file_offset(self):
        data = bytearray(make_nes(prg_banks=8, mapper=1))
        data[16 + 0x10:16 + 0x13] = bytes.fromhex("8D 5A 07")
        banked = self.path("banked_x.nes", bytes(data))
        code, out, _ = run("xrefs", banked, "075A")
        self.assertEqual(code, 0)
        self.assertIn("file offset 0x0020", out)

    def test_patch_copy_writes_patched_file(self):
        out_path = os.path.join(self.dir.name, "patched.nes")
        code, _, _ = run("patch-copy", self.rom, out_path, "AATOZE")
        self.assertEqual(code, 0)
        with open(out_path, "rb") as f, open(self.rom, "rb") as g:
            patched, orig = f.read(), g.read()
        self.assertEqual(patched[16 + 0x106A], 8)
        self.assertEqual(orig[16 + 0x106A], 2)

    def test_patch_copy_refuses_same_path(self):
        code, _, err = run("patch-copy", self.rom, self.rom, "AATOZE")
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_bad_code_prints_one_line_error_exit_2(self):
        code, _, err = run("decode", self.rom, "AATOZB")
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertTrue(err.startswith("error:"))

    def test_missing_rom_file_one_line_error(self):
        code, _, err = run("id", os.path.join(self.dir.name, "nope.nes"))
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_unrecognized_rom_names_supported_platforms(self):
        junk = self.path("junk.bin", bytes(100))
        code, _, err = run("id", junk)
        self.assertEqual(code, 2)
        self.assertIn("nes", err)


if __name__ == "__main__":
    unittest.main()
