import unittest

import _path  # noqa: F401
from glitchcraft.core import RomInfo
from glitchcraft.sega8 import dis_z80 as dis

PAD = b"\x00\x00\x00\x00\x00"


def one(raw, addr=0x0100):
    got = dis._decode(bytes(raw) + PAD, 0, addr)
    return got[0], got[1], got[3]


def rom_info(size, banks):
    return RomInfo("sms", size, "0" * 40, None, {"rom_size": size, "banks": banks})


class Z80Tests(unittest.TestCase):
    def test_known_base_opcodes(self):
        cases = {
            "00": ("NOP", 1), "01 34 12": ("LD BC,$1234", 3), "02": ("LD (BC),A", 1), "03": ("INC BC", 1),
            "04": ("INC B", 1), "05": ("DEC B", 1), "06 7F": ("LD B,$7F", 2), "07": ("RLCA", 1),
            "08": ("EX AF,AF'", 1), "09": ("ADD HL,BC", 1), "0A": ("LD A,(BC)", 1), "0B": ("DEC BC", 1),
            "12": ("LD (DE),A", 1), "1A": ("LD A,(DE)", 1), "21 00 C0": ("LD HL,$C000", 3),
            "22 00 C0": ("LD ($C000),HL", 3), "2A 00 C0": ("LD HL,($C000)", 3), "32 34 12": ("LD ($1234),A", 3),
            "3A 34 12": ("LD A,($1234)", 3), "34": ("INC (HL)", 1), "35": ("DEC (HL)", 1),
            "36 10": ("LD (HL),$10", 2), "3E 05": ("LD A,$05", 2), "27": ("DAA", 1), "2F": ("CPL", 1),
            "37": ("SCF", 1), "3F": ("CCF", 1), "39": ("ADD HL,SP", 1), "31 FF DF": ("LD SP,$DFFF", 3),
            "46": ("LD B,(HL)", 1), "77": ("LD (HL),A", 1), "76": ("HALT", 1), "78": ("LD A,B", 1),
            "80": ("ADD A,B", 1), "8E": ("ADC A,(HL)", 1), "97": ("SUB A", 1), "9F": ("SBC A,A", 1),
            "A0": ("AND B", 1), "AF": ("XOR A", 1), "B6": ("OR (HL)", 1), "BE": ("CP (HL)", 1),
            "C0": ("RET NZ", 1), "E0": ("RET PO", 1), "E8": ("RET PE", 1), "F0": ("RET P", 1), "F8": ("RET M", 1),
            "C9": ("RET", 1), "D9": ("EXX", 1), "E9": ("JP (HL)", 1), "F9": ("LD SP,HL", 1),
            "C1": ("POP BC", 1), "F1": ("POP AF", 1), "E5": ("PUSH HL", 1), "F5": ("PUSH AF", 1),
            "C3 50 01": ("JP $0150", 3), "CA 50 01": ("JP Z,$0150", 3), "E2 00 C0": ("JP PO,$C000", 3),
            "FA 00 C0": ("JP M,$C000", 3), "CD 00 01": ("CALL $0100", 3), "DC 34 12": ("CALL C,$1234", 3),
            "F4 34 12": ("CALL P,$1234", 3), "C6 10": ("ADD A,$10", 2), "FE 90": ("CP $90", 2),
            "D6 01": ("SUB $01", 2), "DE 01": ("SBC A,$01", 2), "FF": ("RST $38", 1), "C7": ("RST $00", 1),
            "D3 BF": ("OUT ($BF),A", 2), "DB BF": ("IN A,($BF)", 2), "E3": ("EX (SP),HL", 1),
            "EB": ("EX DE,HL", 1), "F3": ("DI", 1), "FB": ("EI", 1),
        }
        for hexs, (text, size) in cases.items():
            with self.subTest(op=hexs):
                got = one(bytes.fromhex(hexs))
                self.assertEqual((got[0], got[1], got[2]), (text, size, True))

    def test_relative_jumps_show_the_absolute_target(self):
        self.assertEqual(one(b"\x18\xFE", 0x0100)[0], "JR $0100")
        self.assertEqual(one(b"\x20\x05", 0x0100)[0], "JR NZ,$0107")
        self.assertEqual(one(b"\x28\x05", 0x0100)[0], "JR Z,$0107")
        self.assertEqual(one(b"\x30\xF0", 0x0200)[0], "JR NC,$01F2")
        self.assertEqual(one(b"\x38\x00", 0x0200)[0], "JR C,$0202")
        self.assertEqual(one(b"\x10\xFC", 0x0100)[0], "DJNZ $00FE")
        self.assertEqual(one(b"\x18\x7F", 0xFFF0)[0], "JR $0071")   # wraps at 16 bits

    def test_cb_group(self):
        cases = {"CB 11": "RL C", "CB 06": "RLC (HL)", "CB 0F": "RRC A", "CB 1B": "RR E", "CB 27": "SLA A",
                 "CB 2E": "SRA (HL)", "CB 3F": "SRL A", "CB 37": "SLL A", "CB 7C": "BIT 7,H",
                 "CB 46": "BIT 0,(HL)", "CB 86": "RES 0,(HL)", "CB FF": "SET 7,A", "CB C0": "SET 0,B"}
        for hexs, text in cases.items():
            with self.subTest(op=hexs):
                got = one(bytes.fromhex(hexs))
                self.assertEqual((got[0], got[1]), (text, 2))
        for c in range(256):
            self.assertEqual(one(bytes([0xCB, c]))[1:], (2, not 0x30 <= c < 0x38), hex(c))

    def test_ed_documented(self):
        cases = {
            "ED 40": "IN B,(C)", "ED 78": "IN A,(C)", "ED 41": "OUT (C),B", "ED 79": "OUT (C),A",
            "ED 42": "SBC HL,BC", "ED 72": "SBC HL,SP", "ED 4A": "ADC HL,BC", "ED 7A": "ADC HL,SP",
            "ED 43 00 C0": "LD ($C000),BC", "ED 73 00 C0": "LD ($C000),SP", "ED 4B 00 C0": "LD BC,($C000)",
            "ED 7B 00 C0": "LD SP,($C000)", "ED 53 00 C0": "LD ($C000),DE", "ED 5B 00 C0": "LD DE,($C000)",
            "ED 44": "NEG", "ED 45": "RETN", "ED 4D": "RETI", "ED 46": "IM 0", "ED 56": "IM 1", "ED 5E": "IM 2",
            "ED 47": "LD I,A", "ED 4F": "LD R,A", "ED 57": "LD A,I", "ED 5F": "LD A,R", "ED 67": "RRD",
            "ED 6F": "RLD", "ED A0": "LDI", "ED A1": "CPI", "ED A2": "INI", "ED A3": "OUTI", "ED A8": "LDD",
            "ED A9": "CPD", "ED AA": "IND", "ED AB": "OUTD", "ED B0": "LDIR", "ED B1": "CPIR",
            "ED B2": "INIR", "ED B3": "OTIR", "ED B8": "LDDR", "ED B9": "CPDR", "ED BA": "INDR", "ED BB": "OTDR",
        }
        for hexs, text in cases.items():
            with self.subTest(op=hexs):
                raw = bytes.fromhex(hexs)
                got = one(raw)
                self.assertEqual((got[0], got[1], got[2]), (text, len(raw), True))

    def test_ed_undocumented_aliases_and_holes(self):
        for op in (0x4C, 0x54, 0x5C, 0x64, 0x6C, 0x74, 0x7C):
            self.assertEqual(one(bytes([0xED, op])), ("NEG", 2, False), hex(op))
        for op in (0x55, 0x65, 0x75, 0x5D, 0x6D, 0x7D):
            self.assertEqual(one(bytes([0xED, op])), ("RETN", 2, False), hex(op))
        for op, text in ((0x4E, "IM 0"), (0x66, "IM 0"), (0x6E, "IM 0"), (0x76, "IM 1"), (0x7E, "IM 2")):
            self.assertEqual(one(bytes([0xED, op])), (text, 2, False), hex(op))
        self.assertEqual(one(b"\xED\x63\x00\xC0"), ("LD ($C000),HL", 4, False))
        self.assertEqual(one(b"\xED\x6B\x00\xC0"), ("LD HL,($C000)", 4, False))
        self.assertEqual(one(b"\xED\x70"), ("IN F,(C)", 2, False))
        self.assertEqual(one(b"\xED\x71"), ("OUT (C),0", 2, False))
        for op in (0x00, 0x3F, 0x77, 0x7F, 0x80, 0x9F, 0xA4, 0xAC, 0xB4, 0xBC, 0xC0, 0xFF):
            self.assertEqual(one(bytes([0xED, op])), ("NOP", 2, False), hex(op))

    def test_every_ed_opcode_has_the_right_length(self):
        four = {0x43, 0x4B, 0x53, 0x5B, 0x63, 0x6B, 0x73, 0x7B}
        for op in range(256):
            self.assertEqual(one(bytes([0xED, op]))[1], 4 if op in four else 2, hex(op))

    def test_every_base_opcode_decodes_with_the_right_length(self):
        two = {0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x36, 0x3E, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38,
               0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE, 0xD3, 0xDB, 0xCB, 0xED}
        three = {0x01, 0x11, 0x21, 0x31, 0x22, 0x2A, 0x32, 0x3A, 0xCD, 0xC3} | {
            b | lo for b in (0xC0, 0xD0, 0xE0, 0xF0) for lo in (0x2, 0xA, 0x4, 0xC)}
        for op in range(256):
            if op in (0xDD, 0xFD):
                continue
            want = 2 if op in two else 3 if op in three else 1
            text, size, official = one(bytes([op, 0x00, 0x00]))
            self.assertEqual(size, want, hex(op))
            self.assertEqual(official, op != 0xED, hex(op))   # ED 00 is an undefined two-byte NOP
            self.assertTrue(text, hex(op))

    def test_indexed_forms(self):
        cases = {
            "DD 21 34 12": ("LD IX,$1234", 4), "FD 21 34 12": ("LD IY,$1234", 4),
            "DD 22 00 C0": ("LD ($C000),IX", 4), "FD 2A 00 C0": ("LD IY,($C000)", 4),
            "DD 23": ("INC IX", 2), "FD 2B": ("DEC IY", 2), "DD 09": ("ADD IX,BC", 2), "DD 29": ("ADD IX,IX", 2),
            "FD 39": ("ADD IY,SP", 2), "DD E1": ("POP IX", 2), "FD E5": ("PUSH IY", 2),
            "DD E3": ("EX (SP),IX", 2), "DD E9": ("JP (IX)", 2), "FD E9": ("JP (IY)", 2),
            "DD F9": ("LD SP,IX", 2),
            "DD 34 05": ("INC (IX+$05)", 3), "DD 35 FE": ("DEC (IX-$02)", 3),
            "DD 36 05 10": ("LD (IX+$05),$10", 4), "DD 36 FE 10": ("LD (IX-$02),$10", 4),
            "DD 46 7F": ("LD B,(IX+$7F)", 3), "DD 7E 80": ("LD A,(IX-$80)", 3), "DD 66 01": ("LD H,(IX+$01)", 3),
            "DD 6E 01": ("LD L,(IX+$01)", 3), "DD 77 05": ("LD (IX+$05),A", 3), "FD 74 00": ("LD (IY+$00),H", 3),
            "DD 70 03": ("LD (IX+$03),B", 3), "DD 86 04": ("ADD A,(IX+$04)", 3), "FD BE 04": ("CP (IY+$04)", 3),
            "DD A6 FF": ("AND (IX-$01)", 3),
            "DD CB 05 06": ("RLC (IX+$05)", 4), "DD CB 05 46": ("BIT 0,(IX+$05)", 4),
            "FD CB 04 5E": ("BIT 3,(IY+$04)", 4), "FD CB FE 86": ("RES 0,(IY-$02)", 4),
            "DD CB 00 FE": ("SET 7,(IX+$00)", 4), "DD CB 01 3E": ("SRL (IX+$01)", 4),
        }
        for hexs, (text, size) in cases.items():
            with self.subTest(op=hexs):
                got = one(bytes.fromhex(hexs))
                self.assertEqual((got[0], got[1], got[2]), (text, size, True))

    def test_undocumented_indexed_half_registers(self):
        cases = {
            "DD 24": "INC IXH", "DD 2D": "DEC IXL", "FD 25": "DEC IYH", "FD 2C": "INC IYL",
            "DD 26 10": "LD IXH,$10", "FD 2E 10": "LD IYL,$10", "DD 44": "LD B,IXH", "DD 45": "LD B,IXL",
            "DD 60": "LD IXH,B", "DD 65": "LD IXH,IXL", "DD 6C": "LD IXL,IXH", "FD 7D": "LD A,IYL",
            "DD 84": "ADD A,IXH", "DD 8D": "ADC A,IXL", "FD 95": "SUB IYL", "FD BC": "CP IYH",
            "DD A5": "AND IXL", "DD AC": "XOR IXH", "DD B5": "OR IXL", "DD 9C": "SBC A,IXH",
        }
        for hexs, text in cases.items():
            with self.subTest(op=hexs):
                got = one(bytes.fromhex(hexs))
                self.assertEqual((got[0], got[2]), (text, False))
                self.assertEqual(got[1], 3 if text.startswith("LD I") and "$" in text else 2)

    def test_indexed_bit_ops_with_register_copy(self):
        cases = {
            "DD CB 05 00": "RLC (IX+$05),B", "DD CB 05 07": "RLC (IX+$05),A", "FD CB 05 18": "RR (IY+$05),B",
            "DD CB 05 30": "SLL (IX+$05),B", "DD CB 05 36": "SLL (IX+$05)", "DD CB 05 80": "RES 0,(IX+$05),B",
            "DD CB 05 C1": "SET 0,(IX+$05),C", "FD CB 05 FF": "SET 7,(IY+$05),A",
            "DD CB 05 40": "BIT 0,(IX+$05)", "DD CB 05 7F": "BIT 7,(IX+$05)",
        }
        for hexs, text in cases.items():
            with self.subTest(op=hexs):
                self.assertEqual(one(bytes.fromhex(hexs)), (text, 4, False))
        for pre in (0xDD, 0xFD):
            for c in range(256):
                text, size, official = one(bytes([pre, 0xCB, 0x01, c]))
                self.assertEqual(size, 4, hex(c))
                want = (c & 7) == 6 and not 0x30 <= c < 0x38
                self.assertEqual(official, want, hex(c))

    def test_prefix_that_does_not_use_hl_is_a_one_byte_nop(self):
        for pre in (0xDD, 0xFD):
            for op in (0x00, 0x01, 0x76, 0xC3, 0xCD, 0xEB, 0xAF, 0x40, 0x4F, 0x7F, 0xDD, 0xFD, 0xED, 0xFF, 0xD9):
                with self.subTest(pre=pre, op=op):
                    self.assertEqual(one(bytes([pre, op])), (f"NOP ; {pre:02X}", 1, False))
        # the following byte is decoded normally on its own
        out = dis.disassemble(bytes.fromhex("DD3E05"), 0x0100, 5)
        self.assertEqual([(i.addr, i.text) for i in out], [(0x100, "NOP ; DD"), (0x101, "LD A,$05")])
        out = dis.disassemble(bytes.fromhex("FDDD21AABB"), 0x0100, 5)
        self.assertEqual([i.text for i in out], ["NOP ; FD", "LD IX,$BBAA"])

    def test_every_dd_fd_opcode_has_the_right_length(self):
        mem_or_half_2 = {0x09, 0x19, 0x29, 0x39, 0x23, 0x2B, 0x24, 0x25, 0x2C, 0x2D, 0xE1, 0xE3, 0xE5, 0xE9, 0xF9}
        for pre in (0xDD, 0xFD):
            for op in range(256):
                if op == 0xCB:
                    continue
                if op in (0x21, 0x22, 0x2A, 0x36):
                    want = 4
                elif op in (0x34, 0x35, 0x26, 0x2E):
                    want = 3
                elif 0x40 <= op < 0x80 and op != 0x76:
                    d, s = (op >> 3) & 7, op & 7
                    want = 3 if 6 in (d, s) else 2 if {d, s} & {4, 5} else 1
                elif 0x80 <= op < 0xC0:
                    s = op & 7
                    want = 3 if s == 6 else 2 if s in (4, 5) else 1
                elif op in mem_or_half_2:
                    want = 2
                else:
                    want = 1
                text, size, official = one(bytes([pre, op, 0x00, 0x00]))
                self.assertEqual(size, want, f"{pre:02X} {op:02X}")
                if want == 1:
                    self.assertEqual((text, official), (f"NOP ; {pre:02X}", False))

    def test_truncated_instructions_return_none(self):
        for raw in ("C3 50", "C3", "3E", "ED", "ED 43 00", "DD", "DD 21 00", "DD 36 05", "DD CB 05", "DD CB",
                    "CB", "DD 34", "FD 46"):
            with self.subTest(raw=raw):
                self.assertIsNone(dis._decode(bytes.fromhex(raw), 0, 0x100))
        self.assertIsNotNone(dis._decode(bytes.fromhex("DD 21 00 00"), 0, 0x100))

    def test_refs(self):
        def refs(hexs):
            return dis._decode(bytes.fromhex(hexs) + PAD, 0, 0x100)[2]
        self.assertEqual(refs("32 00 C0"), [(0xC000, "write")])
        self.assertEqual(refs("3A 00 C0"), [(0xC000, "read")])
        self.assertEqual(refs("22 00 C0"), [(0xC000, "write")])
        self.assertEqual(refs("2A 00 C0"), [(0xC000, "read")])
        self.assertEqual(refs("ED 43 00 C0"), [(0xC000, "write")])
        self.assertEqual(refs("ED 4B 00 C0"), [(0xC000, "read")])
        self.assertEqual(refs("DD 22 00 C0"), [(0xC000, "write")])
        self.assertEqual(refs("DD 2A 00 C0"), [(0xC000, "read")])
        self.assertEqual(refs("21 00 C0"), [(0xC000, "use")])
        self.assertEqual(refs("DD 21 00 C0"), [(0xC000, "use")])
        self.assertEqual(refs("C3 50 01"), [(0x0150, "jump")])
        self.assertEqual(refs("CA 50 01"), [(0x0150, "jump")])
        self.assertEqual(refs("CD 50 01"), [(0x0150, "call")])
        self.assertEqual(refs("C4 50 01"), [(0x0150, "call")])
        self.assertEqual(refs("20 05"), [(0x0107, "jump")])
        self.assertEqual(refs("10 05"), [(0x0107, "jump")])
        self.assertEqual(refs("FF"), [(0x38, "call")])
        self.assertEqual(refs("E9"), [])
        self.assertEqual(refs("DD E9"), [])
        self.assertEqual(refs("DB BF"), [])

    def test_mnemonic_marks_conditionals(self):
        cases = {"JP $0150": "JP", "JP Z,$0150": "JPcc", "JP PO,$0150": "JPcc", "JP (HL)": "JP", "JP (IX)": "JP",
                 "JP (IY)": "JP", "JR $0100": "JR", "JR NC,$0100": "JRcc", "CALL $0100": "CALL",
                 "CALL M,$0100": "CALLcc", "RET": "RET", "RET NZ": "RETcc", "RET P": "RETcc", "RETI": "RETI",
                 "RETN": "RETN", "RST $38": "RST", "DJNZ $0100": "DJNZ", "LD A,B": "LD", "NOP ; DD": "NOP",
                 "JP C,$0100": "JPcc"}
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(dis.mnemonic(text), want)

    def test_flow_constants(self):
        self.assertEqual(dis.FLOW_MNEMONICS, {"JP", "JR", "CALL", "RET", "RETI", "RETN", "RST", "DJNZ", "ILLEGAL",
                                              "JPcc", "JRcc", "CALLcc", "RETcc"})
        self.assertEqual(dis.ROUTINE_END, {"JP", "JR", "RET", "RETI", "RETN"})

    def test_a_truncated_instruction_at_the_end_becomes_a_byte(self):
        out = dis.disassemble(b"\x00\xC3\x50", 0x0100, 5)
        self.assertEqual([i.text for i in out], ["NOP", ".byte $C3", "LD D,B"])
        out = dis.disassemble(b"\xDD", 0x0100, 5)
        self.assertEqual([i.text for i in out], [".byte $DD"])

    def test_disassemble_walks_and_counts(self):
        out = dis.disassemble(bytes.fromhex("3E05D3BF4F"), 0x0150, 3)
        self.assertEqual([(i.addr, i.raw, i.text, i.official) for i in out],
                         [(0x150, b"\x3E\x05", "LD A,$05", True), (0x152, b"\xD3\xBF", "OUT ($BF),A", True),
                          (0x154, b"\x4F", "LD C,A", True)])

    def test_locate_finds_the_instruction_that_contains_an_offset(self):
        data = bytes.fromhex("3E05CD0020")
        self.assertEqual(dis.locate(data, 0, 3), (2, False))
        self.assertEqual(dis.locate(bytes.fromhex("ED7700"), 0, 1), (0, True))
        self.assertEqual(dis.locate(bytes.fromhex("0000ED77"), 2, 3), (2, True))
        self.assertEqual(dis.locate(bytes.fromhex("00C3"), 0, 1), (1, True))   # truncated tail

    def _rom(self, size, markers):
        data = bytearray(size)
        for off, raw in markers.items():
            data[off:off + len(raw)] = raw
        return bytes(data)

    def test_xrefs_finds_stores_loads_calls_and_extended_forms(self):
        data = self._rom(0x8000, {0x0200: bytes.fromhex("3200C0"),
                                  0x0300: bytes.fromhex("3A00C0"), 0x0400: bytes.fromhex("ED4300C0"),
                                  0x0500: bytes.fromhex("CD00C0"), 0x4100: bytes.fromhex("2A00C0"),
                                  0x0600: bytes.fromhex("DD2100C0")})
        info = rom_info(0x8000, 2)
        got = {(h.offset, h.kind, h.cpu) for h in dis.xrefs(info, data, 0xC000)}
        self.assertEqual(got, {(0x200, "write", 0x200), (0x300, "read", 0x300), (0x400, "write", 0x400),
                               (0x500, "call", 0x500), (0x4100, "read", 0x4100), (0x600, "use", 0x600),
                               (0x601, "use", 0x601)})   # the LD HL,nn hiding inside DD 21

    def test_xrefs_cpu_is_none_in_banked_roms_above_16k(self):
        data = self._rom(0x20000, {0x0200: bytes.fromhex("3A00C0"), 0x4100: bytes.fromhex("3A00C0"),
                                   0x1C100: bytes.fromhex("3A00C0")})
        info = rom_info(0x20000, 8)
        got = {(h.offset, h.cpu) for h in dis.xrefs(info, data, 0xC000)}
        self.assertEqual(got, {(0x200, 0x200), (0x4100, None), (0x1C100, None)})

    def test_xrefs_does_not_guess_the_slot_of_a_relative_branch_in_a_banked_rom(self):
        # a JR in file bank 2 could run in slot 1 or slot 2, so its target address is unknown
        data = self._rom(0x10000, {0x8100: bytes.fromhex("1800")})
        for target in (0x4102, 0x8102):
            self.assertEqual(dis.xrefs(rom_info(0x10000, 4), data, target), [])

    def test_xrefs_still_finds_absolute_operands_in_banked_offsets(self):
        data = self._rom(0x10000, {0x8100: bytes.fromhex("C30050")})   # JP $5000
        got = dis.xrefs(rom_info(0x10000, 4), data, 0x5000)
        self.assertEqual([(h.offset, h.kind, h.cpu) for h in got], [(0x8100, "jump", None)])

    def test_xrefs_skips_unofficial_decodes_and_rst(self):
        data = self._rom(0x8000, {0x0200: bytes.fromhex("DD00"), 0x0300: bytes.fromhex("FF")})
        info = rom_info(0x8000, 2)
        self.assertEqual([h.kind for h in dis.xrefs(info, data, 0x38)], ["call"])


if __name__ == "__main__":
    unittest.main()
