"""Offline recovery tests; no Java, network, or Minecraft distribution required."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mcsource
import vineflower_fallback as fallback


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root / ".local/references/test"
        self.reference.mkdir(parents=True)
        self.jar = self.root / "input.jar"
        with zipfile.ZipFile(self.jar, "w") as archive:
            archive.writestr("p/Bad.class", b"class")
            archive.writestr("p/Bad$Inner.class", b"inner")
            archive.writestr("p/Other.class", b"other")
        self.identity = {"sha256": hashlib.sha256(self.jar.read_bytes()).hexdigest(), "input_jar": str(self.jar)}
        self.original = 'package p; class Bad { /* Unable to fully structure code */ }'
        (self.reference / "p").mkdir()
        (self.reference / "p/Bad.java").write_text(self.original, encoding="utf-8")
        (self.reference / "summary.txt").write_text("Summary\np.Bad\n----------------------------\nUnable to fully structure code", encoding="utf-8")
        self.record = self.reference / "REFERENCE.json"
        self.record.write_text(json.dumps({"sha256": self.identity["sha256"], "decompiler": {"name": "CFR"}, "status": "needs_review", "summary_has_findings": True}), encoding="utf-8")

    def fake_decompile(self, args, **kwargs):
        inputs, output = Path(args[-2]), Path(args[-1])
        self.assertTrue((inputs / "p/Bad.class").exists())
        self.assertTrue((inputs / "p/Bad$Inner.class").exists())
        self.assertFalse((inputs / "p/Other.class").exists())
        (output / "p").mkdir()
        (output / "p/Bad.java").write_text("package p; public class Bad {}", encoding="utf-8")

    def recover(self, side_effect=None):
        with patch.object(fallback, "get_tool", return_value=self.root / "tool.jar"), patch.object(fallback.subprocess, "run", side_effect=side_effect or self.fake_decompile):
            return fallback.repair_reference(self.root, self.reference, self.identity)

    def test_success_preserves_originals_and_removes_only_workspace(self):
        report = self.recover()
        self.assertEqual(report["status"], "generated_unverified")
        self.assertEqual(report["fallback"]["status"], "recovered_unverified")
        self.assertEqual(report["fallback"]["workspace"], "removed")
        self.assertEqual(report["fallback"]["original_sha256"]["p/Bad.java"], hashlib.sha256(self.original.encode()).hexdigest())
        self.assertIn("finished_utc", report["fallback"])
        self.assertFalse((self.reference / "diagnostics/vineflower/workspace").exists())
        self.assertEqual((self.reference / "diagnostics/vineflower/cfr-original/p/Bad.java.cfr").read_text(), self.original)
        self.assertTrue((self.reference / "summary.txt").exists())
        self.assertTrue((self.reference / "diagnostics/vineflower/vineflower.log").exists())
        self.assertEqual(report["failure_marker_files"], [])
        self.assertEqual(report["fallback"]["output_sha256"]["p/Bad.java"], hashlib.sha256((self.reference / "p/Bad.java").read_bytes()).hexdigest())

    def test_nonzero_exit_keeps_original_and_workspace(self):
        report = self.recover(subprocess.CalledProcessError(1, "java"))
        self.assertEqual(report["fallback"]["status"], "failed")
        self.assertEqual(report["status"], "needs_review")
        self.assertEqual((self.reference / "p/Bad.java").read_text(), self.original)
        self.assertTrue((self.reference / "diagnostics/vineflower/workspace").exists())

    def test_warning_rejects_entire_candidate_set(self):
        def warn(args, **kwargs):
            self.fake_decompile(args, **kwargs)
            kwargs["stdout"].write("WARN: ambiguous code\n")
        report = self.recover(warn)
        self.assertEqual(report["fallback"]["status"], "failed")
        self.assertEqual((self.reference / "p/Bad.java").read_text(), self.original)

    def test_missing_output_is_not_accepted(self):
        report = self.recover(lambda *a, **k: None)
        self.assertEqual(report["fallback"]["status"], "failed")
        self.assertEqual((self.reference / "p/Bad.java").read_text(), self.original)

    def test_failure_marker_in_output_is_not_accepted(self):
        def broken(args, **kwargs):
            self.fake_decompile(args, **kwargs)
            (Path(args[-1]) / "p/Bad.java").write_text("package p; class Bad { // $VF: Couldn't be decompiled\n}")
        self.assertEqual(self.recover(broken)["fallback"]["status"], "failed")

    def test_wrong_package_or_type_is_not_accepted(self):
        for text in ("package other; class Bad {}", "package p; class Other {}", ""):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temp:
                file = Path(temp) / "Bad.java"
                file.write_text(text)
                with self.assertRaises(ValueError):
                    fallback.validate_output(file, "p/Bad.java")

    def test_wrong_jar_is_rejected_before_writing(self):
        before = self.record.read_bytes()
        self.identity["sha256"] = "incorrect"
        with patch.object(fallback, "get_tool") as tool:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                fallback.repair_reference(self.root, self.reference, self.identity)
            tool.assert_not_called()
        self.assertEqual(self.record.read_bytes(), before)
        self.assertFalse((self.reference / "diagnostics").exists())

    def test_invalid_reference_identity_is_rejected_without_diagnostics(self):
        self.record.write_text("[]")
        with self.assertRaisesRegex(ValueError, "must be an object"):
            fallback.repair_reference(self.root, self.reference, self.identity)
        self.assertFalse((self.reference / "diagnostics").exists())

    def test_paths_cannot_escape_reference(self):
        for relative in ("../Bad.java", "/Bad.java", "C:/Bad.java", "p\\Bad.java"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                fallback.source_path(self.reference, relative)
        with self.assertRaises(ValueError):
            fallback.repair_reference(self.root, self.root, self.identity)

    def test_repeated_attempt_requires_manual_review(self):
        self.recover()
        with self.assertRaisesRegex(ValueError, "already recorded"):
            self.recover()

    def test_no_findings_does_not_download_tool(self):
        (self.reference / "p/Bad.java").write_text("package p; class Bad {}")
        (self.reference / "summary.txt").write_text("Summary\nDecompiled with CFR")
        with patch.object(fallback, "get_tool") as tool:
            fallback.repair_reference(self.root, self.reference, self.identity)
            tool.assert_not_called()
        self.assertFalse((self.reference / "diagnostics").exists())

    def test_unknown_summary_stays_unresolved(self):
        with (self.reference / "summary.txt").open("a") as stream:
            stream.write("\nUnknown heading!\n----------------------------\n")
        report = self.recover()
        self.assertEqual(report["status"], "needs_review")
        self.assertTrue(report["fallback"]["unknown_summary_findings"])

    def test_cleanup_failure_keeps_diagnostics(self):
        with patch.object(fallback.shutil, "rmtree", side_effect=OSError("locked")):
            report = self.recover()
        self.assertEqual(report["fallback"]["status"], "recovered_unverified")
        self.assertEqual(report["fallback"]["workspace"], "retained")
        self.assertIn("cleanup_error", report["fallback"])

    def test_partial_replacement_rolls_back(self):
        (self.reference / "p/Second.java").write_text("package p; class Second { /* Decompilation failed */ }", encoding="utf-8")
        second_original = (self.reference / "p/Second.java").read_bytes()
        with zipfile.ZipFile(self.jar, "a") as archive:
            archive.writestr("p/Second.class", b"second")
        self.identity["sha256"] = hashlib.sha256(self.jar.read_bytes()).hexdigest()
        metadata = json.loads(self.record.read_text())
        metadata["sha256"] = self.identity["sha256"]
        self.record.write_text(json.dumps(metadata))
        replace = os.replace

        def fail_second(source, target):
            if str(target).endswith("Second.java"):
                raise OSError("replacement failed")
            return replace(source, target)

        def decompile(args, **kwargs):
            self.fake_decompile(args, **kwargs)
            (Path(args[-1]) / "p/Second.java").write_text("package p; class Second {}")

        with patch.object(fallback.os, "replace", side_effect=fail_second):
            report = self.recover(decompile)
        self.assertEqual(report["fallback"]["status"], "failed")
        self.assertEqual((self.reference / "p/Bad.java").read_text(), self.original)
        self.assertEqual((self.reference / "p/Second.java").read_bytes(), second_original)

    def test_tampered_tool_is_not_executed_or_redownloaded(self):
        tools = self.root / ".local/tools"
        tools.mkdir()
        (tools / f"vineflower-{fallback.VERSION}.jar").write_bytes(b"tampered")
        with patch.object(fallback.urllib.request, "urlopen") as download:
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                fallback.get_tool(self.root)
            download.assert_not_called()

    def test_download_hash_mismatch_preserves_partial(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = [b"wrong binary", b""]
        with patch.object(fallback.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                fallback.get_tool(self.root)
        self.assertTrue((self.root / f".local/tools/vineflower-{fallback.VERSION}.jar.part").exists())
        self.assertFalse((self.root / f".local/tools/vineflower-{fallback.VERSION}.jar").exists())

    def test_diagnostic_package_is_still_scanned(self):
        path = self.reference / "p/diagnostics/Bad.java"
        path.parent.mkdir()
        path.write_text("Decompilation failed")
        self.assertIn("p/diagnostics/Bad.java", fallback.scan_failures(self.reference))


if __name__ == "__main__":
    unittest.main()
