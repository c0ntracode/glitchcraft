import os
import subprocess
import unittest

ROM_EXTENSIONS = (".nes", ".sfc", ".smc", ".gen", ".smd", ".gb", ".gbc", ".gg", ".sms")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def tracked_files():
    """`git ls-files`, or None outside a git checkout (for example an exported tarball), where these checks do not apply."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.splitlines() if out.returncode == 0 else None


class HygieneTests(unittest.TestCase):
    def test_no_rom_files_tracked(self):
        files = tracked_files()
        if files is None:
            self.skipTest("not a git checkout")
        self.assertEqual([f for f in files if f.lower().endswith(ROM_EXTENSIONS)], [])

    def test_no_stray_images_or_archives_tracked(self):
        files = tracked_files()
        if files is None:
            self.skipTest("not a git checkout")
        self.assertEqual([f for f in files if f.lower().endswith((".png", ".jpg", ".zip", ".7z"))], [])

    def test_no_bytecode_tracked(self):
        files = tracked_files()
        if files is None:
            self.skipTest("not a git checkout")
        self.assertEqual([f for f in files if "__pycache__" in f or f.endswith(".pyc")], [])


if __name__ == "__main__":
    unittest.main()
