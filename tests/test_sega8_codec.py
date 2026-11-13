import json
import os
import random
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError, Patch
from glitchcraft.gb import codec as gbcodec
from glitchcraft.sega8 import codec

with open(os.path.join(os.path.dirname(__file__), "fixtures", "sega8_vectors.json")) as f:
    V = json.load(f)["hand_decoded"]


class Sega8CodecTests(unittest.TestCase):
    def test_decode_every_published_vector(self):
        for v in V:
            with self.subTest(code=v["code"]):
                self.assertEqual(codec.decode(v["code"]), Patch(v["address"], v["value"], v["compare"]))

    def test_encode_reproduces_the_published_codes_including_the_check_digit(self):
        for v in V:
            with self.subTest(code=v["code"]):
                self.assertEqual(codec.encode(Patch(v["address"], v["value"], v["compare"])), v["code"])

    def test_roundtrip_random_patches_up_to_bfff(self):
        rng = random.Random(97531)
        for _ in range(2000):
            p = Patch(rng.randint(0, 0xBFFF), rng.randint(0, 255), rng.choice([None, rng.randint(0, 255)]))
            self.assertEqual(codec.decode(codec.encode(p)), p)

    def test_the_address_limit_is_bfff(self):
        self.assertEqual(codec.decode(codec.encode(Patch(0xBFFF, 1, None))).address, 0xBFFF)
        for addr in (0xC000, 0xFFFF):
            with self.assertRaises(GlitchError):
                codec.encode(Patch(addr, 1, None))

    def test_decode_refuses_an_address_in_ram(self):
        # F digit 3 -> high nibble 0xC
        with self.assertRaises(GlitchError):
            codec.decode("000-003")

    def test_the_ignored_digit_does_not_change_the_patch(self):
        self.assertEqual(codec.decode("3A6-24E-202"), codec.decode("3A6-24E-2A2"))
        self.assertEqual(codec.decode("3A6-24E-2A2"), codec.decode("3A624E2A2"))

    def test_six_digit_codes_have_no_reference_byte(self):
        self.assertIsNone(codec.decode("3A6-24E").compare)

    def test_bad_input_raises(self):
        for bad in ("", "3A6-24", "3A6-24E-2A", "3A6-24E-2A2F", "3G6-24E"):
            with self.subTest(code=bad):
                with self.assertRaises(GlitchError):
                    codec.decode(bad)

    def test_the_game_boy_codec_keeps_its_smaller_limit(self):
        with self.assertRaises(GlitchError):
            gbcodec.encode(Patch(0x8000, 1, None))


if __name__ == "__main__":
    unittest.main()
