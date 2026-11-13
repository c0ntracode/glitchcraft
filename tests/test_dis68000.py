import os
import unittest

import _path  # noqa: F401
from glitchcraft.core import Hit
from glitchcraft.genesis import dis68000, rom
from test_genesis_rom import SONIC, make_md


def dis(hexbytes, addr=0x001000, count=1):
    return dis68000.disassemble(bytes.fromhex(hexbytes), addr, count)


def text(hexbytes, addr=0x001000):
    return dis(hexbytes, addr)[0].text


class Dis68000Tests(unittest.TestCase):
    def test_no_operand_instructions(self):
        for hexbytes, want in {"4E75": "RTS", "4E71": "NOP", "4E73": "RTE", "4E77": "RTR", "4E76": "TRAPV",
                               "4AFC": "ILLEGAL", "4E41": "TRAP #1"}.items():
            with self.subTest(op=want):
                self.assertEqual(text(hexbytes), want)

    def test_branches_show_absolute_targets(self):
        self.assertEqual(text("6000 0100"), "BRA.W $001102")
        self.assertEqual(text("6100 FFF0"), "BSR.W $000FF2")
        self.assertEqual(text("6700 0010"), "BEQ.W $001012")
        self.assertEqual(text("60FE"), "BRA.S $001000")
        self.assertEqual(text("6604"), "BNE.S $001006")
        self.assertEqual(dis("6000 0100")[0].raw, bytes.fromhex("60000100"))

    def test_jumps_and_calls(self):
        self.assertEqual(text("4EB9 0000 1234"), "JSR ($00001234).l")
        self.assertEqual(text("4EF9 0001 0000"), "JMP ($00010000).l")
        self.assertEqual(text("4E90"), "JSR (A0)")
        self.assertEqual(text("4EBA 0010"), "JSR $001012(PC)")

    def test_moveq_and_move_family(self):
        self.assertEqual(text("7001"), "MOVEQ #$01,D0")
        self.assertEqual(text("72FF"), "MOVEQ #$FF,D1")
        self.assertEqual(text("303C 1234"), "MOVE.W #$1234,D0")
        self.assertEqual(text("1018"), "MOVE.B (A0)+,D0")
        self.assertEqual(text("2200"), "MOVE.L D0,D1")
        self.assertEqual(text("11FC 0003 FE12"), "MOVE.B #$03,($FFFFFE12).w")
        self.assertEqual(text("33FC 0001 00FF 0000"), "MOVE.W #$0001,($00FF0000).l")
        self.assertEqual(text("2040"), "MOVEA.L D0,A0")
        self.assertEqual(text("3EFC 1000"), "MOVE.W #$1000,(A7)+")
        self.assertEqual(text("3F00"), "MOVE.W D0,-(A7)")

    def test_quick_and_immediate_arithmetic(self):
        self.assertEqual(text("5338 FE12"), "SUBQ.B #1,($FFFFFE12).w")
        self.assertEqual(text("5240"), "ADDQ.W #1,D0")
        self.assertEqual(text("5048"), "ADDQ.W #8,A0")
        self.assertEqual(text("0640 0001"), "ADDI.W #$0001,D0")
        self.assertEqual(text("0C40 000A"), "CMPI.W #$000A,D0")
        self.assertEqual(text("0240 00FF"), "ANDI.W #$00FF,D0")
        self.assertEqual(text("0000 0080"), "ORI.B #$80,D0")

    def test_register_arithmetic_and_logic(self):
        self.assertEqual(text("D040"), "ADD.W D0,D0")
        self.assertEqual(text("D081"), "ADD.L D1,D0")
        self.assertEqual(text("9240"), "SUB.W D0,D1")
        self.assertEqual(text("B040"), "CMP.W D0,D0")
        self.assertEqual(text("B141"), "EOR.W D0,D1")
        self.assertEqual(text("8040"), "OR.W D0,D0")
        self.assertEqual(text("C041"), "AND.W D1,D0")
        self.assertEqual(text("D0FC 0010"), "ADDA.W #$0010,A0")
        self.assertEqual(text("D1C0"), "ADDA.L D0,A0")

    def test_multiply_and_divide(self):
        self.assertEqual(text("80FC 0003"), "DIVU.W #$0003,D0")
        self.assertEqual(text("81FC 0003"), "DIVS.W #$0003,D0")
        self.assertEqual(text("C0FC 0003"), "MULU.W #$0003,D0")
        self.assertEqual(text("C1FC 0003"), "MULS.W #$0003,D0")
        self.assertEqual(text("8240"), "OR.W D0,D1")

    def test_clear_test_lea_dbcc_ext_swap(self):
        self.assertEqual(text("4240"), "CLR.W D0")
        self.assertEqual(text("4279 00FF 0000"), "CLR.W ($00FF0000).l")
        self.assertEqual(text("4A38 FE12"), "TST.B ($FFFFFE12).w")
        self.assertEqual(text("41F9 0000 1234"), "LEA ($00001234).l,A0")
        self.assertEqual(text("43E9 0010"), "LEA $10(A1),A1")
        self.assertEqual(text("51C9 FFFC"), "DBRA D1,$000FFE")
        self.assertEqual(text("4880"), "EXT.W D0")
        self.assertEqual(text("48C0"), "EXT.L D0")
        self.assertEqual(text("4840"), "SWAP D0")

    def test_shifts_bit_ops_and_movem(self):
        self.assertEqual(text("E348"), "LSL.W #1,D0")
        self.assertEqual(text("E248"), "LSR.W #1,D0")
        self.assertEqual(text("E548"), "LSL.W #2,D0")
        self.assertEqual(text("E540"), "ASL.W #2,D0")
        self.assertEqual(text("E369"), "LSL.W D1,D1")
        self.assertEqual(text("0800 0007"), "BTST #7,D0")
        self.assertEqual(text("0100"), "BTST D0,D0")
        self.assertEqual(text("08C0 0003"), "BSET #3,D0")
        self.assertEqual(text("48E7 FFFE"), "MOVEM.L D0-D7/A0-A6,-(A7)")
        self.assertEqual(text("4CDF 7FFF"), "MOVEM.L (A7)+,D0-D7/A0-A6")

    def test_unknown_opcodes_print_dc_w_and_are_not_official(self):
        for hexbytes in ("A000", "F000", "4E7A 0000"):
            with self.subTest(op=hexbytes):
                i = dis(hexbytes)[0]
                self.assertTrue(i.text.startswith("dc.w $"), i.text)
                self.assertFalse(i.official)
                self.assertEqual(len(i.raw), 2)

    def test_truncated_or_odd_tail_becomes_byte_directive(self):
        self.assertEqual([i.text for i in dis("33FC 0001", count=3)][0], "dc.w $33FC")
        self.assertEqual([i.text for i in dis("4E", count=1)], [".byte $4E"])

    def test_invalid_effective_addresses_print_dc_w(self):
        self.assertTrue(text("4EC0").startswith("dc.w"))      # JMP D0 is not a legal effective address
        self.assertTrue(text("2078").startswith("dc.w"))      # MOVEA.L with a truncated extension word

    def test_addresses_advance_by_instruction_length(self):
        out = dis("33FC 0001 00FF 0000 4E75", count=2)
        self.assertEqual([i.addr for i in out], [0x001000, 0x001008])

    def test_xrefs_finds_absolute_short_and_long_operands(self):
        data = make_md(marker={0x1000: bytes.fromhex("5338FE12"), 0x1010: bytes.fromhex("33FC000100FFFE12"),
                               0x1020: bytes.fromhex("4EB900001234"), 0x1030: bytes.fromhex("4A38FE12")})
        info = rom.identify(data)
        kinds = {(h.cpu, h.kind) for h in dis68000.xrefs(info, data, 0xFFFFFE12)}
        self.assertIn((0x001000, "rmw"), kinds)
        self.assertIn((0x001010, "write"), kinds)
        self.assertIn((0x001030, "read"), kinds)
        jumps = dis68000.xrefs(info, data, 0x1234)
        self.assertIn(Hit(0x001020, "jump", 0x1020), jumps)

    @unittest.skipUnless(os.path.exists(SONIC), "roms/genesis not present")
    def test_real_sonic_life_loss_instruction(self):
        with open(SONIC, "rb") as f:
            data = f.read()
        info = rom.identify(data)
        self.assertEqual(dis68000.disassemble(data[0x13F74:0x13F78], 0x13F74, 1)[0].text, "SUBQ.B #1,($FFFFFE12).w")
        self.assertIn(0x013F74, [h.cpu for h in dis68000.xrefs(info, data, 0xFFFFFE12)])


if __name__ == "__main__":
    unittest.main()
