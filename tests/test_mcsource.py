import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

spec = importlib.util.spec_from_file_location("mcsource", Path(__file__).resolve().parents[1] / "scripts/mcsource.py")
mcsource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcsource)


class ReferenceTests(unittest.TestCase):
    def make_jar(self, root, version="26.2", class_name="net/minecraft/client/Minecraft.class", header=b"\xca\xfe\xba\xbe\x00\x00\x00\x45"):
        path = root / "input.jar"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("version.json", json.dumps({"id": version}))
            archive.writestr(class_name, header)
        return path

    def test_identity_hash_and_bytecode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.make_jar(Path(temp))
            result = mcsource.inspect_jar(path)
            self.assertEqual(result["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(result["sha1"], hashlib.sha1(path.read_bytes()).hexdigest())
            self.assertEqual(result["class_major_versions"], [69])
            self.assertEqual(result["minecraft_version"], "26.2")
            self.assertEqual(result["namespace"], "unverified")

    def test_obfuscated_input_remains_unverified(self):
        with tempfile.TemporaryDirectory() as temp:
            result = mcsource.inspect_jar(self.make_jar(Path(temp), class_name="abc.class"))
            self.assertFalse(result["named_client_class_present"])
            self.assertEqual(result["scope"], "unverified")

    def test_corrupt_class_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Invalid class"):
                mcsource.inspect_jar(self.make_jar(Path(temp), header=b"invalid!"))

    def test_metadata_must_be_an_object(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.jar"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("version.json", "[]")
            with self.assertRaisesRegex(ValueError, "must contain an object"):
                mcsource.inspect_jar(path)

    def test_missing_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.jar"
            with zipfile.ZipFile(path, "w"):
                pass
            with self.assertRaises(KeyError):
                mcsource.inspect_jar(path)

    @patch.object(mcsource.shutil, "which", return_value="tool")
    @patch.object(mcsource.subprocess, "check_output", return_value='openjdk version "21.0.1"')
    def test_older_java_is_rejected(self, output, which):
        with self.assertRaisesRegex(ValueError, r"Java 25\+ is required"):
            mcsource.check_jdk(69)

    @patch.object(mcsource.shutil, "which", return_value="tool")
    @patch.object(mcsource.subprocess, "check_output", side_effect=['openjdk version "25.0.1"', 'javac 21.0.1'])
    def test_mixed_jdk_is_rejected(self, output, which):
        with self.assertRaisesRegex(ValueError, "same JDK"):
            mcsource.check_jdk(69)

    def test_existing_reference_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jar = self.make_jar(root)
            identity = mcsource.inspect_jar(jar)
            target = root / ".local/references" / ("26.2-" + identity["sha256"][:12])
            target.mkdir(parents=True)
            sentinel = target / "keep.txt"
            sentinel.write_text("preserve")
            with patch.object(mcsource, "ROOT", root), patch.object(mcsource, "check_jdk"), patch.object(mcsource, "build_cfr") as build:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    mcsource.prepare(jar)
                build.assert_not_called()
            self.assertEqual(sentinel.read_text(), "preserve")

    def test_prepare_records_cfr_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jar = self.make_jar(root)

            def decompile(args, **kwargs):
                output = Path(args[args.index("--outputdir") + 1])
                (output / "Broken.java").write_text('throw new IllegalStateException("Decompilation failed");')
                (output / "summary.txt").write_text("Summary\n----------------------------\nFailure")

            with patch.object(mcsource, "ROOT", root), patch.object(mcsource, "check_jdk"), patch.object(mcsource, "build_cfr", return_value=root / "tool.jar"), patch.object(mcsource, "run", side_effect=decompile), patch("builtins.print"):
                self.assertEqual(mcsource.prepare(jar), 2)
            record = next((root / ".local/references").glob("*/REFERENCE.json"))
            identity = json.loads(record.read_text())
            self.assertEqual(identity["status"], "needs_review")
            self.assertEqual(identity["failure_marker_files"], ["Broken.java"])

    def test_empty_decompiler_result_is_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jar = self.make_jar(root)
            with patch.object(mcsource, "ROOT", root), patch.object(mcsource, "check_jdk"), patch.object(mcsource, "build_cfr", return_value=root / "tool.jar"), patch.object(mcsource, "run"), patch("builtins.print"):
                with self.assertRaisesRegex(ValueError, "no Java source"):
                    mcsource.prepare(jar)
            record = next((root / ".local/references").glob("*/REFERENCE.json"))
            self.assertEqual(json.loads(record.read_text())["status"], "failed")

    def test_prepare_can_invoke_recovery_after_cfr_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jar = self.make_jar(root)

            def decompile(args, **kwargs):
                output = Path(args[args.index("--outputdir") + 1])
                (output / "Broken.java").write_text('throw new IllegalStateException("Decompilation failed");')

            with patch.object(mcsource, "ROOT", root), patch.object(mcsource, "check_jdk") as jdk, patch.object(mcsource, "build_cfr", return_value=root / "tool.jar"), patch.object(mcsource, "run", side_effect=decompile), patch.object(mcsource, "repair_reference", return_value={"status": "generated_unverified"}) as repair, patch("builtins.print"):
                self.assertEqual(mcsource.prepare(jar, repair=True), 0)
                repair.assert_called_once()
                self.assertTrue(jdk.call_args.kwargs["minimum"] == 17)

    @patch.object(mcsource.shutil, "which", return_value="tool")
    @patch.object(mcsource.subprocess, "check_output", return_value='openjdk version "11.0.1"')
    def test_recovery_requires_java_17_even_for_older_bytecode(self, output, which):
        with self.assertRaisesRegex(ValueError, r"Java 17\+ is required"):
            mcsource.check_jdk(52, minimum=17)

    def test_failure_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Broken.java").write_text('throw new IllegalStateException("Decompilation failed");')
            (root / "Good.java").write_text("class Good {}")
            self.assertEqual(mcsource.scan_failures(root), ["Broken.java"])


if __name__ == "__main__":
    unittest.main()
