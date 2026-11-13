"""Published codes against the author's real dumps (git-ignored roms/). Each test skips when its ROM is absent.

A compare byte that equals the ROM byte at the patched address, in the bank the code was written for, is independent
evidence that the codec and the address mapping are right. Codes: almarsguides.com, Sonic Retro / console lists,
GameFAQs-style lists (see docs/evals/real-roms-2026-11-12.md). Effects are published claims, not checked in a game."""
import contextlib
import glob
import io
import os
import unittest

import _path  # noqa: F401
from glitchcraft import cli

ROMS = os.path.join(os.path.dirname(__file__), "..", "roms")


def find(pattern):
    hits = sorted(glob.glob(os.path.join(ROMS, pattern)))
    return hits[0] if hits else None


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


class RealRomTests(unittest.TestCase):
    def assert_applies(self, rom, code, bank=None, original=None):
        if rom is None:
            self.skipTest("ROM not present")
        args = ["decode", rom, code] + (["--bank", bank] if bank is not None else [])
        rc, out, err = run(*args)
        self.assertEqual(rc, 0, err)
        self.assertNotIn("will not apply", out, f"{code} compare does not match {rom}")
        if original is not None:
            self.assertIn(f"original={original}", out)

    def assert_does_not_apply(self, rom, code):
        if rom is None:
            self.skipTest("ROM not present")
        self.assertIn("will not apply", run("decode", rom, code)[1])

    def test_game_gear_sonic_chaos_published_codes(self):
        rom = find("sega8/Sonic Chaos (JUE) [!].gg")
        self.assert_applies(rom, "3A6-24E-2A2", original="$32")   # infinite lives: LD ($D29B),A -> LD A,($D29B)
        self.assert_applies(rom, "008-3BD-E6E", original="$01")   # stop timer: ADD A,1 -> ADD A,0

    def test_game_gear_sonic_1_published_codes_match_the_revision_they_were_written_for(self):
        v10 = find("sega8/Sonic the Hedgehog (JUE) (V1.0).gg")
        v11 = find("sega8/Sonic the Hedgehog (JUE) (V1.1)*.gg")
        self.assert_applies(v10, "013-7DE-E66", original="$03")               # start with 1 life
        self.assert_applies(v10, "003-F8C-3B7", original="$77")               # stop timer
        self.assert_applies(v10, "007-01A-3BE", bank="1", original="$35")     # infinite lives: DEC (HL) -> NOP
        self.assert_applies(v11, "003-8CE-5D4", original="$AF")               # level select, part 1
        self.assert_applies(v11, "013-88E-91A", original="$1C")               # level select, part 2
        self.assert_applies(v11, "2A2-86A-6E2", bank="1", original="$22")     # LD ($D296),HL -> LD HL,($D296)

    def test_game_gear_sonic_1_codes_do_not_apply_to_the_other_revision_or_build(self):
        v10 = find("sega8/Sonic the Hedgehog (JUE) (V1.0).gg")
        v11 = find("sega8/Sonic the Hedgehog (JUE) (V1.1)*.gg")
        proto = find("sega8/Sonic the Hedgehog (JUE) (Proto)*.gg")
        self.assert_does_not_apply(v11, "013-7DE-E66")
        self.assert_does_not_apply(v10, "003-8CE-5D4")
        self.assert_does_not_apply(proto, "013-7DE-E66")

    def test_a_file_named_gg_can_carry_a_master_system_header(self):
        proto = find("sega8/Sonic the Hedgehog (JUE) (Proto)*.gg")
        if proto is None:
            self.skipTest("ROM not present")
        self.assertIn("system: Master System", run("id", proto)[1])       # the tool reports the header, not the extension

    def test_master_system_codemasters_micro_machines_is_detected_and_mapped(self):
        rom = find("sega8/Micro Machines (E)*.sms")
        if rom is None:
            self.skipTest("ROM not present")
        _, out, _ = run("id", rom)
        self.assertIn("mapper: Codemasters", out)
        self.assertIn("supported: True", out)
        _, out, _ = run("xrefs", rom, "8000")                       # the slot-2 bank register it writes
        self.assertIn("write", out)

    def test_game_gear_codes_do_not_apply_to_the_master_system_build(self):
        self.assert_does_not_apply(find("sega8/Sonic the Hedgehog (UE) [!].sms"), "3A6-24E-2A2")

    def test_game_boy_tetris_published_codes(self):
        rom = find("gb/Tetris*.gb")
        for code in ("063-8FF-7FE", "263-8FF-7FE", "000-AED-19E", "001-5ED-3B5"):
            self.assert_applies(rom, code)

    def test_game_boy_mbc1_link_s_awakening_published_codes_in_the_right_bank(self):
        rom = find("gb/Legend of Zelda*Awakening*.gb")
        self.assert_applies(rom, "00F-84F-E6E")                     # bank 0: infinite bombs
        self.assert_applies(rom, "000-989-19E", bank="2")           # infinite health
        self.assert_applies(rom, "C9D-8F9-081", bank="3")           # invincibility
        self.assertIn("bank-dependent", run("decode", rom, "000-989-19E")[1])   # no bank given: it cannot be placed

    def test_game_boy_mbc3_pokemon_red_published_codes_in_the_right_bank(self):
        rom = find("gb/Pokemon Red.gb")
        self.assert_applies(rom, "009-0EC-7F5")                     # bank 0
        self.assert_applies(rom, "C9F-3C9-E69", bank="15")          # no random battles
        self.assert_applies(rom, "C90-2DB-3BE", bank="26")          # infinite PP
        self.assert_applies(rom, "CED-56A-D50", bank="1")           # debug mode

    def test_nes_mmc1_mega_man_2_published_codes(self):
        rom = find("nes/Mega Man 2*.nes")
        self.assert_applies(rom, "SXUGTPVG")                        # fixed bank, infinite lives
        self.assert_applies(rom, "NNEAALLV", bank="14")             # 255 max lives
        self.assert_applies(rom, "PESUGPLE", bank="13")             # continue with 9 lives

    def test_nes_mmc3_super_mario_bros_3_published_codes(self):
        rom = find("nes/Super Mario Bros. 3*Rev 1*.nes")
        self.assert_applies(rom, "SLXPLOVS", bank="30")             # infinite lives
        self.assert_applies(rom, "AAVZNULP", bank="8")              # always run

    def test_nes_super_mario_bros_per_jump_palette_investigation(self):
        """Facts behind docs/evals/smb-jump-palette.md, checked on the real dump (SHA-1 in TESTING.md)."""
        rom = find("nes/smb.nes")
        if rom is None:
            self.skipTest("ROM not present")
        self.assertIn("sha1: 33d23c2f2cfa4c9efec87f7bc1321ce3ce6c89bd", run("id", rom)[1])
        inc = ["VVNLLKSE", "KKNLGGLL", "LENLIGGA"]                  # STA $0433 -> INC $03C4 (opcode, low, high byte)
        others = ["SZVZKYAX", "PEOUTXKY", "AUVAEKZP", "YXVAOGAL", "POVAXGYX"]   # no reset; mask bit 0; Luigi in palette 1
        for code in inc + others:
            self.assert_applies(rom, code)
        _, out, _ = run("vet", rom, *inc)
        self.assertIn("STA $0433 -> INC $03C4", out)
        self.assertIn("displaced: STA $0433 no longer runs", out)
        with open(rom, "rb") as f:
            data = f.read()
        at = lambda a, n=1: data[a - 0x8000 + 16:a - 0x8000 + 16 + n]   # noqa: E731
        self.assertEqual(at(0x85D7, 12).hex(), "221627182230271922372716")   # Mario, Luigi, Fire rows
        for area in (0x8CA4, 0x8CC8, 0x8CEC, 0x8D10):                   # sprite palettes of each area set
            sprite = at(area + 3 + 16, 16)
            self.assertTrue(all(sprite[i + 1:i + 4] != bytes([0x30, 0x27, 0x19]) for i in range(0, 16, 4)), hex(area))
        self.assertEqual(at(0xAF64, 3).hex(), "209ab2")             # the per-frame JSR to the palette reset
        callers = [a for a in range(0x8000, 0xFFFD) if at(a, 3) == bytes([0x20, 0xF1, 0x85])]
        self.assertEqual(callers, [0x85AD, 0x9175, 0xD830, 0xD941])  # nothing on a jump path calls GetPlayerColors

    def test_snes_hirom_earthbound_mirrors_agree(self):
        rom = find("snes/EarthBound*.sfc")
        self.assert_applies(rom, "8251-57D6", original="$9D")       # unlimited HP: STA -> LDA at C2:716C

    def test_genesis_sonic_1_rev00_published_codes_land_on_the_intended_instructions(self):
        rom = find("genesis/Sonic_The_Hedgehog_W_REV00*.bin")
        if rom is None:
            self.skipTest("ROM not present")
        _, out, _ = run("vet", rom, "GJ6A-CA7A", "AY3T-AACL")
        self.assertIn("SUBQ.B #1,($FFFFFE12).w -> BRA.S", out)      # infinite lives skips the decrement
        self.assertIn("MOVE.B #$03,($FFFFFE12).w -> MOVE.B #$05,($FFFFFE12).w", out)

    def test_genesis_rom_without_a_sega_header_is_identified(self):
        rom = find("genesis/Micro Machines*.md")
        if rom is None:
            self.skipTest("ROM not present")
        rc, out, _ = run("id", rom)
        self.assertEqual(rc, 0)
        self.assertIn("header_warning", out)


if __name__ == "__main__":
    unittest.main()
