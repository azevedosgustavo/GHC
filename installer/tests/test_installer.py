import os
import sys
import tempfile
import unittest
import zipfile
import subprocess
import importlib.util
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "installer"))
import installer as ins


def load_build():
    path = os.path.join(os.path.dirname(__file__), "..", "build.py")
    spec = importlib.util.spec_from_file_location("ghc_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = temporary.name
        self.zip = os.path.join(self.tmp, "payload.zip")
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("GHC.exe", "x")
            z.writestr("lib/a.txt", "y")
        patcher = mock.patch.object(ins, "resource", lambda name: self.zip)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_validate(self):
        self.assertIsNotNone(ins.validate_dir("relativo"))
        self.assertIsNotNone(ins.validate_dir(os.path.abspath(os.sep)))
        self.assertIsNone(ins.validate_dir(os.path.join(self.tmp, "novo")))
        self.assertIsNotNone(ins.validate_dir(self.tmp))  # non-empty, no manifest

    def test_published_setups_preserve_existing_files_even_on_timestamp_collision(self):
        build = load_build()
        source = os.path.join(self.tmp, "setup.exe")
        dest = os.path.join(self.tmp, "dist")
        with open(source, "wb") as f:
            f.write(b"new setup")
        with mock.patch.object(build, "datetime") as clock:
            clock.now.return_value.strftime.return_value = "20261126-120000-000000"
            first = build.publish_setup(source, dest, "0.1.0")
            with open(first, "wb") as f:
                f.write(b"previous setup")
            second = build.publish_setup(source, dest, "0.1.0")
        self.assertNotEqual(first, second)
        with open(first, "rb") as f:
            self.assertEqual(f.read(), b"previous setup")
        with open(second, "rb") as f:
            self.assertEqual(f.read(), b"new setup")

    def test_roundtrip(self):
        dest = os.path.join(self.tmp, "GHC")
        with mock.patch.object(ins, "IS_WIN", False):
            ins.install(dest, {}, log=lambda s: None)
            self.assertTrue(os.path.isfile(os.path.join(dest, "lib", "a.txt")))
            self.assertTrue(os.path.isdir(os.path.join(dest, "skill")))
            self.assertIsNone(ins.validate_dir(dest))  # reinstall over existing is allowed
            ins.install(dest, {}, log=lambda s: None)
            ins.uninstall(dest, False, log=lambda s: None)
            self.assertFalse(os.path.exists(dest))

    def test_user_skills_survive_reinstallation_and_uninstall(self):
        dest = os.path.join(self.tmp, "GHC")
        with mock.patch.object(ins, "IS_WIN", False):
            ins.install(dest, {}, log=lambda s: None)
            skill = os.path.join(dest, "skill", "example.md")
            with open(skill, "w", encoding="utf-8") as f:
                f.write("Instruções")
            ins.install(dest, {}, log=lambda s: None)
            ins.uninstall(dest, False, log=lambda s: None)
            with open(skill, encoding="utf-8") as f:
                self.assertEqual(f.read(), "Instruções")

    def test_build_packages_skills_and_installer_preserves_existing_content(self):
        build = load_build()
        app = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app"))

        def fake_pyi(*args):
            output = args[args.index("--distpath") + 1]
            name = args[args.index("--name") + 1]
            if name == "GHC":
                output = os.path.join(output, name)
            os.makedirs(output, exist_ok=True)
            with open(os.path.join(output, name + ".exe"), "wb") as f:
                f.write(b"stub")

        with mock.patch.object(sys, "argv", ["build.py", "--app", app, "--output-dir", self.tmp]), \
                mock.patch.object(build, "pyi", side_effect=fake_pyi), \
                mock.patch.object(build, "copy_python_runtime"):
            build.main()

        builds = os.path.join(self.tmp, "build")
        payload = os.path.join(builds, os.listdir(builds)[0], "payload.zip")
        relative = os.path.join("skill", "python-desenvolvimento", "SKILL.md")
        source = os.path.join(app, relative)
        dest = os.path.join(self.tmp, "dest")
        with zipfile.ZipFile(payload) as z:
            for name in ("Sys-execucao.md", "Sys-pdf.md", "Sys-word.md", "Sys-excel.md",
                         "Sys-criacao-de-skills.md", "Sys-arquivos.md"):
                self.assertIn("skill/" + name, z.namelist())
        with mock.patch.object(ins, "resource", return_value=payload):
            files = ins.extract_payload(dest)
            installed = os.path.join(dest, relative)
            with open(source, "rb") as f:
                expected = f.read()
            with open(installed, "rb") as f:
                self.assertEqual(f.read(), expected)
            self.assertNotIn(relative, files)
            with open(installed, "wb") as f:
                f.write(b"customizada")
            ins.extract_payload(dest)
            with open(installed, "rb") as f:
                self.assertEqual(f.read(), b"customizada")

    def test_zip_slip(self):
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("../evil.txt", "x")
        with self.assertRaises(ValueError):
            ins.extract_payload(os.path.join(self.tmp, "d"))

    def test_failed_skill_extraction_can_be_retried(self):
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("skill/example.md", "instruções")
        dest = os.path.join(self.tmp, "dest")
        with mock.patch.object(zipfile.ZipFile, "open", side_effect=OSError("falha")):
            with self.assertRaisesRegex(OSError, "falha"):
                ins.extract_payload(dest)
        path = os.path.join(dest, "skill", "example.md")
        self.assertFalse(os.path.exists(path))
        ins.extract_payload(dest)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "instruções")

    def test_runtime_check_requires_successful_report(self):
        exe = os.path.join(self.tmp, "GHC.exe")

        def run_success(args, **kwargs):
            self.assertNotIn("PYTHONHOME", kwargs["env"])
            self.assertNotIn("PYTHONPATH", kwargs["env"])
            with open(args[2], "w", encoding="utf-8") as f:
                f.write("OK")
            return subprocess.CompletedProcess(args, 0)

        with mock.patch.object(ins.subprocess, "run", side_effect=run_success):
            ins.verify_runtime(exe)
        with mock.patch.object(ins.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0)):
            with self.assertRaisesRegex(RuntimeError, "nao produziu"):
                ins.verify_runtime(exe)

        def run_failure(args, **kwargs):
            with open(args[2], "w", encoding="utf-8") as f:
                f.write("ImportError: biblioteca ausente")
            return subprocess.CompletedProcess(args, 1)

        with mock.patch.object(ins.subprocess, "run", side_effect=run_failure):
            with self.assertRaisesRegex(RuntimeError, "biblioteca ausente"):
                ins.verify_runtime(exe)
        with mock.patch.object(ins.subprocess, "run", side_effect=subprocess.TimeoutExpired("GHC", 60)):
            with self.assertRaisesRegex(RuntimeError, "60 segundos"):
                ins.verify_runtime(exe)

    def test_failed_runtime_check_allows_retry(self):
        dest = os.path.join(self.tmp, "GHC")
        with mock.patch.object(ins, "IS_WIN", True), \
                mock.patch.object(ins, "app_running", return_value=False), \
                mock.patch.object(ins, "verify_runtime", side_effect=RuntimeError("falhou")):
            with self.assertRaisesRegex(RuntimeError, "falhou"):
                ins.install(dest, {}, log=lambda s: None)
        self.assertIsNone(ins.validate_dir(dest))
        self.assertIn("GHC.exe", ins.load_manifest(dest)["files"])

    def test_package_verification_reports_failure(self):
        report = os.path.join(self.tmp, "report.txt")
        with mock.patch.object(ins, "verify_runtime", side_effect=RuntimeError("dependencia ausente")):
            self.assertEqual(ins.main(["--verify-package", report]), 1)
        with open(report, encoding="utf-8") as f:
            self.assertIn("dependencia ausente", f.read())

    def test_vbs(self):
        v = ins.shortcut_vbs([r"C:\u\Desktop\A.lnk"], r"C:\GHC\GHC.exe", r"C:\GHC")
        self.assertIn('CreateShortcut("C:\\u\\Desktop\\A.lnk")', v)
        self.assertIn('TargetPath = "C:\\GHC\\GHC.exe"', v)

    @unittest.skipUnless(sys.platform == "win32", "runtime Windows")
    def test_copied_runtime_executes_without_system_python(self):
        destination = os.path.join(self.tmp, "python-runtime")
        load_build().copy_python_runtime(destination)
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        executable = os.path.join(destination, "python.exe")
        result = subprocess.run([executable, "-c", "import ssl, sqlite3, json; print('OK')"],
                                cwd=self.tmp, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(result.stdout.strip(), b"OK")
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app")))
        try:
            from harness import tools
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "executable", os.path.join(self.tmp, "GHC.exe")):
                output = tools.run_python(self.tmp, """
import os, sys, docx, openpyxl, reportlab
from reportlab.pdfgen import canvas
for module in (docx, openpyxl, reportlab):
    assert os.path.commonpath([sys.prefix, module.__file__]) == sys.prefix
pdf = canvas.Canvas("teste.pdf")
pdf.drawString(72, 720, "Relatorio acao")
pdf.save()
document = docx.Document()
document.add_paragraph("Texto Word")
document.save("teste.docx")
workbook = openpyxl.Workbook()
workbook.active["A1"] = "Valor Excel"
workbook.save("teste.xlsx")
print("runtime ok")
""")
            self.assertIn("Codigo de saida: 0", output)
            self.assertIn("runtime ok", output)
            from pypdf import PdfReader
            from docx import Document
            import openpyxl
            self.assertIn("Relatorio acao", PdfReader(os.path.join(self.tmp, "teste.pdf")).pages[0].extract_text())
            self.assertEqual(Document(os.path.join(self.tmp, "teste.docx")).paragraphs[0].text, "Texto Word")
            workbook = openpyxl.load_workbook(os.path.join(self.tmp, "teste.xlsx"))
            try:
                self.assertEqual(workbook.active["A1"].value, "Valor Excel")
            finally:
                workbook.close()
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
