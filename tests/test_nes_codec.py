import json
import os
import random
import unittest

import _path  # noqa: F401
from glitchcraft.core import GlitchError, Patch
from glitchcraft.nes import codec

with open(os.path.join(os.path.dirname(__file__), "fixtures", "nes_vectors.json")) as f:
    V = json.load(f)


class CodecTests(unittest.TestCase):
    def test_decode_six_letter_own_vectors(self):
        for code, pair in V["six_letter_own_analysis"].items():
            if code == "note":
                continue
            with self.subTest(code=code):
                self.assertEqual(codec.decode(code), Patch(pair[0], pair[1], None))

    def test_decode_six_letter_published_vector(self):
        v = V["six_letter_published"]["GOSSIP"]
        self.assertEqual(codec.decode("GOSSIP"), Patch(v["address"], v["value"], None))

    def test_unused_bit_gives_equivalent_codes(self):
        for a, b in V["equivalent_six_letter"]:
            self.assertEqual(codec.decode(a), codec.decode(b))

    def test_decode_eight_letter_published_vectors(self):
        for code, v in V["eight_letter_published"].items():
            with self.subTest(code=code):
                self.assertEqual(codec.decode(code), Patch(v["address"], v["value"], v["compare"]))

    def test_encode_inverts_decode_for_every_vector(self):
        codes = [c for c in V["six_letter_own_analysis"] if c != "note"] + list(V["eight_letter_published"])
        for code in codes:
            with self.subTest(code=code):
                self.assertEqual(codec.encode(codec.decode(code)), code)

    def test_roundtrip_random_patches(self):
        rng = random.Random(1234)
        for _ in range(2000):
            p = Patch(rng.randint(0x8000, 0xFFFF), rng.randint(0, 255), rng.choice([None, rng.randint(0, 255)]))
            self.assertEqual(codec.decode(codec.encode(p)), p)

    def test_decode_is_case_and_separator_insensitive(self):
        self.assertEqual(codec.decode("zex-pyg la"), codec.decode("ZEXPYGLA"))

    def test_bad_length_and_bad_letter_raise_glitcherror(self):
        with self.assertRaises(GlitchError) as ctx:
            codec.decode("AATOZAA")
        self.assertIn("7", str(ctx.exception))
        with self.assertRaises(GlitchError) as ctx:
            codec.decode("AATOZB")
        self.assertIn("B", str(ctx.exception))

    def test_encode_rejects_address_below_8000(self):
        with self.assertRaises(GlitchError):
            codec.encode(Patch(0x7FFF, 0, None))


if __name__ == "__main__":
    unittest.main()
