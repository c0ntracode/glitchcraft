import json
import os
import random
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError, Patch
from glitchcraft.gb import codec

with open(os.path.join(os.path.dirname(__file__), "fixtures", "gb_vectors.json")) as f:
    V = json.load(f)["hand_decoded"]


class GbCodecTests(unittest.TestCase):
    def test_decode_every_fixture_vector(self):
        for v in V:
            with self.subTest(code=v["code"]):
                self.assertEqual(codec.decode(v["code"]), Patch(v["address"], v["value"], v["compare"]))

    def test_six_digit_code_has_no_compare(self):
        self.assertIsNone(codec.decode("00C-4BE").compare)

    def test_encode_inverts_decode_for_every_fixture_vector(self):
        for v in V:
            with self.subTest(code=v["code"]):
                p = Patch(v["address"], v["value"], v["compare"])
                self.assertEqual(codec.decode(codec.encode(p)), p)

    def test_roundtrip_random_patches(self):
        rng = random.Random(1357)
        for _ in range(2000):
            cmp = rng.choice([None, rng.randint(0, 255)])
            p = Patch(rng.randint(0, 0x7FFF), rng.randint(0, 255), cmp)
            self.assertEqual(codec.decode(codec.encode(p)), p)

    def test_the_ignored_digit_does_not_change_the_patch(self):
        self.assertEqual(codec.decode("010-03F-E0A"), codec.decode("010-03F-E6A"))

    def test_encoded_nine_digit_codes_carry_the_check_digit_real_codes_have(self):
        # every published code has H = G xor 8 (the "cloak"); emulators ignore it but hardware may not
        for v in V:
            if v["compare"] is not None:
                code = codec.encode(Patch(v["address"], v["value"], v["compare"]))
                self.assertEqual(int(code[9], 16), int(code[8], 16) ^ 8, code)
                self.assertEqual(code, v["code"])

    def test_decode_accepts_lowercase_and_no_hyphens(self):
        self.assertEqual(codec.decode("01003fe6a"), codec.decode("010-03F-E6A"))

    def test_encode_refuses_an_address_above_7fff(self):
        with self.assertRaises(GlitchError):
            codec.encode(Patch(0x8000, 0, None))

    def test_decode_refuses_an_address_above_7fff(self):
        with self.assertRaises(GlitchError):
            codec.decode("000-000-000")   # F digit 0 -> top nibble 0xF

    def test_encode_refuses_a_wide_value_or_compare(self):
        for p in (Patch(0, 256, None), Patch(0, 0, 256)):
            with self.assertRaises(GlitchError):
                codec.encode(p)

    def test_bad_length_or_digits_raise(self):
        for bad in ("", "00C-4B", "00C-4BE-3B", "00C-4BE-3BEE", "00G-4BE", "xyz-123"):
            with self.subTest(code=bad):
                with self.assertRaises(GlitchError):
                    codec.decode(bad)


if __name__ == "__main__":
    unittest.main()
