import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

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

    def test_failure_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Broken.java").write_text('throw new IllegalStateException("Decompilation failed");')
            (root / "Good.java").write_text("class Good {}")
            self.assertEqual(mcsource.scan_failures(root), ["Broken.java"])


if __name__ == "__main__":
    unittest.main()
