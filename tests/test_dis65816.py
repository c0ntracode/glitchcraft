import os
import unittest

import _path  # noqa: F401
from glitchcraft.core import Hit
from glitchcraft.snes import dis65816, rom
from test_snes_rom import SMW, make_snes


def dis(hexbytes, addr=0x008000, count=1, **kw):
    return dis65816.disassemble(bytes.fromhex(hexbytes), addr, count, **kw)


class Dis65816Tests(unittest.TestCase):
    def test_lda_immediate_is_8_bit_when_m_set(self):
        out = dis("A9 01 60", count=2, m=1, x=1)
        self.assertEqual([i.text for i in out], ["LDA #$01", "RTS"])
        self.assertEqual(out[1].addr, 0x008002)

    def test_lda_immediate_is_16_bit_when_m_clear(self):
        out = dis("A9 34 12 60", count=2, m=0, x=1)
        self.assertEqual([i.text for i in out], ["LDA #$1234", "RTS"])
        self.assertEqual(out[1].addr, 0x008003)

    def test_index_register_immediates_follow_x_not_m(self):
        self.assertEqual(dis("A2 34 12", m=1, x=0)[0].text, "LDX #$1234")
        self.assertEqual(dis("A2 34", m=0, x=1)[0].text, "LDX #$34")

    def test_rep_sep_change_tracked_widths(self):
        out = dis("C2 30 A9 34 12 E2 20 A9 01", count=4, m=1, x=1)
        self.assertEqual([i.text for i in out], ["REP #$30", "LDA #$1234", "SEP #$20", "LDA #$01"])

    def test_unknown_width_is_marked(self):
        self.assertTrue(dis("A9 01 60", count=1)[0].text.endswith("; width unknown"))
        self.assertFalse(dis("EA", count=1)[0].text.endswith("; width unknown"))

    def test_unknown_width_decodes_as_8_bit(self):
        out = dis("A9 04 9D B4 0D", count=2)
        self.assertEqual(out[0].text, "LDA #$04; width unknown")
        self.assertEqual(out[1].text, "STA $0DB4,X")

    def test_long_absolute_and_long_jump_formats(self):
        self.assertEqual(dis("5C EE FF C0")[0].text, "JML $C0FFEE")
        self.assertEqual(dis("AF BE 0D 7E")[0].text, "LDA $7E0DBE")
        self.assertEqual(dis("22 00 80 02")[0].text, "JSL $028000")

    def test_other_addressing_modes(self):
        cases = {"A5 12": "LDA $12", "B5 12": "LDA $12,X", "B6 12": "LDX $12,Y", "AD 34 12": "LDA $1234",
                 "BD 34 12": "LDA $1234,X", "B9 34 12": "LDA $1234,Y", "B2 12": "LDA ($12)",
                 "A1 12": "LDA ($12,X)", "B1 12": "LDA ($12),Y", "A7 12": "LDA [$12]", "B7 12": "LDA [$12],Y",
                 "A3 12": "LDA $12,S", "B3 12": "LDA ($12,S),Y", "6C 34 12": "JMP ($1234)",
                 "7C 34 12": "JMP ($1234,X)", "DC 34 12": "JML [$1234]", "54 01 02": "MVN $02,$01",
                 "F4 34 12": "PEA $1234", "D4 12": "PEI ($12)", "0A": "ASL A", "EB": "XBA", "FB": "XCE"}
        for hexbytes, text in cases.items():
            with self.subTest(text=text):
                self.assertEqual(dis(hexbytes, m=1, x=1)[0].text, text)

    def test_branches_show_absolute_targets(self):
        self.assertEqual(dis("80 FE", addr=0x008000)[0].text, "BRA $008000")
        self.assertEqual(dis("D0 05", addr=0x00D0E4)[0].text, "BNE $00D0EB")
        self.assertEqual(dis("82 FD FF", addr=0x018000)[0].text, "BRL $018000")

    def test_exactly_256_opcodes_defined(self):
        self.assertEqual(len(dis65816.OPCODES), 256)
        self.assertTrue(all(e is not None for e in dis65816.OPCODES))

    def test_truncated_tail_becomes_byte_directive(self):
        self.assertEqual([i.text for i in dis("AF BE", count=2)], [".byte $AF", ".byte $BE"])

    def test_locate_tracks_rep_so_16_bit_immediates_do_not_desync(self):
        data = bytes.fromhex("C2 20 A9 34 12 8D BE 0D 60")
        start, m, x, uncertain = dis65816.locate(data, 0, 8)
        self.assertEqual((start, m, uncertain), (8, 0, False))

    def test_locate_reports_uncertainty_when_a_width_was_guessed(self):
        data = bytes.fromhex("A9 01 60")
        start, m, x, uncertain = dis65816.locate(data, 0, 2)
        self.assertEqual((start, uncertain), (2, True))

    def test_xrefs_7e_wram_address_also_finds_16_bit_operands(self):
        data = bytearray(make_snes("lorom"))
        data[0x1000:0x1003] = bytes.fromhex("CE BE 0D")
        info = rom.identify(bytes(data))
        self.assertIn(Hit(0x009000, "rmw", 0x1000), dis65816.xrefs(info, bytes(data), 0x7E0DBE))

    def test_xrefs_finds_indexed_absolute_and_indexed_long_operands(self):
        data = bytearray(make_snes("lorom"))
        data[0x1000:0x1003] = bytes.fromhex("BD BE 0D")       # LDA $0DBE,X
        data[0x1010:0x1013] = bytes.fromhex("B9 BE 0D")       # LDA $0DBE,Y
        data[0x2000:0x2004] = bytes.fromhex("BF BE 0D 7E")    # LDA $7E0DBE,X
        info = rom.identify(bytes(data))
        hits = [h.offset for h in dis65816.xrefs(info, bytes(data), 0x0DBE)]
        self.assertIn(0x1000, hits)
        self.assertIn(0x1010, hits)
        self.assertIn(0x2000, [h.offset for h in dis65816.xrefs(info, bytes(data), 0x7E0DBE)])

    def test_xrefs_finds_absolute_and_long_operands_in_a_lorom(self):
        data = bytearray(make_snes("lorom"))
        data[0x1000:0x1003] = bytes.fromhex("CE BE 0D")       # DEC $0DBE at $00:9000
        data[0x2000:0x2004] = bytes.fromhex("AF BE 0D 7E")    # LDA $7E0DBE at $00:A000
        info = rom.identify(bytes(data))
        hits = dis65816.xrefs(info, bytes(data), 0x0DBE)
        self.assertIn(Hit(0x009000, "rmw", 0x1000), hits)
        hits_long = dis65816.xrefs(info, bytes(data), 0x7E0DBE)
        self.assertIn(Hit(0x00A000, "read", 0x2000), hits_long)

    @unittest.skipUnless(os.path.exists(SMW), "roms/snes/smw not present")
    def test_xrefs_lives_counter_in_real_smw(self):
        with open(SMW, "rb") as f:
            data = f.read()
        info = rom.identify(data)
        self.assertIn((0x00D0D8, "rmw"), [(h.cpu, h.kind) for h in dis65816.xrefs(info, data, 0x0DBE)])


if __name__ == "__main__":
    unittest.main()
