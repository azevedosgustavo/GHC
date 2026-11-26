import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "installer"))
import installer as ins


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.zip = os.path.join(self.tmp, "payload.zip")
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("GHC.exe", "x")
            z.writestr("lib/a.txt", "y")
        ins.resource = lambda name: self.zip

    def test_validate(self):
        self.assertIsNotNone(ins.validate_dir("relativo"))
        self.assertIsNotNone(ins.validate_dir(os.path.abspath(os.sep)))
        self.assertIsNone(ins.validate_dir(os.path.join(self.tmp, "novo")))
        self.assertIsNotNone(ins.validate_dir(self.tmp))  # non-empty, no manifest

    def test_roundtrip(self):
        dest = os.path.join(self.tmp, "GHC")
        ins.install(dest, {}, log=lambda s: None)
        self.assertTrue(os.path.isfile(os.path.join(dest, "lib", "a.txt")))
        self.assertIsNone(ins.validate_dir(dest))  # reinstall over existing is allowed
        ins.install(dest, {}, log=lambda s: None)
        ins.uninstall(dest, False, log=lambda s: None)
        if not ins.IS_WIN:  # on Windows the uninstaller deletes itself after exit
            self.assertFalse(os.path.exists(dest))

    def test_zip_slip(self):
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("../evil.txt", "x")
        with self.assertRaises(ValueError):
            ins.extract_payload(os.path.join(self.tmp, "d"))

    def test_vbs(self):
        v = ins.shortcut_vbs([r"C:\u\Desktop\A.lnk"], r"C:\GHC\GHC.exe", r"C:\GHC")
        self.assertIn('CreateShortcut("C:\\u\\Desktop\\A.lnk")', v)
        self.assertIn('TargetPath = "C:\\GHC\\GHC.exe"', v)


if __name__ == "__main__":
    unittest.main()
