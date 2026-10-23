"""Binding snapshots must never write to or silently retarget mod projects."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import project_binding as binding


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root / "kit"
        self.project = self.root / "mod"
        self.project.mkdir()
        (self.project / "gradle.properties").write_text("minecraft_version=26.2\n", encoding="utf-8")
        (self.project / "build.gradle").write_text('dependencies { minecraft "com.mojang:minecraft:${project.minecraft_version}" }\n', encoding="utf-8")
        self.reference = self.kit / ".local/references/26.2-test"
        (self.reference / "p").mkdir(parents=True)
        (self.reference / "p/Good.java").write_text("package p; class Good {}", encoding="utf-8")
        self.record = self.reference / "REFERENCE.json"
        self.record.write_text(json.dumps({"schema_version": 1, "minecraft_version": "26.2", "sha256": "a" * 64, "namespace": "unverified", "provenance": "unverified", "scope": "client", "status": "generated_unverified", "java_file_count": 1}), encoding="utf-8")

    def bind(self, **kwargs):
        return binding.bind_project(self.kit, self.project, self.reference, **kwargs)

    def resolve(self):
        return binding.resolve_project(self.kit, self.project)

    def change_identity(self, **changes):
        record = json.loads(self.record.read_text())
        record.update(changes)
        self.record.write_text(json.dumps(record), encoding="utf-8")

    def test_bind_and_resolve_never_claim_api_compatibility(self):
        self.assertEqual(self.bind()["status"], "located_unverified")
        report = self.resolve()
        self.assertEqual(report["status"], "located_unverified")
        self.assertTrue(report["review_required"])
        self.assertEqual(report["project_check"]["api_compatibility"], "unverified")
        self.assertTrue(Path(report["reference"]).samefile(self.reference))
        self.assertIn(self.reference.resolve(strict=True).as_posix(), report["instruction"])

    def test_missing_binding_does_not_create_directories(self):
        self.assertEqual(self.resolve()["status"], "binding_missing")
        self.assertFalse((self.kit / ".local/bindings").exists())

    def test_project_files_are_unchanged(self):
        before = {p.relative_to(self.project): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.project.rglob("*") if p.is_file()}
        self.bind()
        self.resolve()
        after = {p.relative_to(self.project): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_project_version_change_is_stale(self):
        self.bind()
        (self.project / "gradle.properties").write_text("minecraft_version=26.1\n")
        report = self.resolve()
        self.assertEqual(report["status"], "stale")
        self.assertIn("project_configuration_changed", report["reasons"])
        self.assertNotIn("instruction", report)

    def test_added_or_deleted_config_is_stale(self):
        self.bind()
        (self.project / "settings.gradle").write_text("rootProject.name='test'\n")
        self.assertEqual(self.resolve()["status"], "stale")

    def test_reference_identity_change_is_stale(self):
        self.bind()
        self.change_identity(provenance="verified_official_client")
        self.assertIn("reference_identity_changed", self.resolve()["reasons"])

    def test_source_change_without_identity_change_is_stale(self):
        self.bind()
        (self.reference / "p/Good.java").write_text("package p; class Good { int changed; }")
        self.assertIn("reference_sources_changed", self.resolve()["reasons"])

    def test_missing_source_is_stale(self):
        self.bind()
        (self.reference / "p/Good.java").unlink()
        self.assertEqual(self.resolve()["status"], "stale")

    def test_missing_identity_is_stale(self):
        self.bind()
        self.record.unlink()
        self.assertEqual(self.resolve()["status"], "stale")

    def test_diagnostics_do_not_invalidate_active_sources(self):
        self.bind()
        (self.reference / "diagnostics").mkdir()
        (self.reference / "diagnostics/backup.java").write_text("Decompilation failed")
        self.assertEqual(self.resolve()["status"], "located_unverified")

    def test_existing_binding_is_not_overwritten_implicitly(self):
        first = self.bind()
        target = Path(first["binding_file"])
        before = target.read_bytes()
        with self.assertRaisesRegex(ValueError, "Existing binding"):
            self.bind()
        self.assertEqual(target.read_bytes(), before)

    def test_explicit_refresh_preserves_review_requirement(self):
        self.bind()
        (self.project / "build.gradle").write_text('dependencies { minecraft "com.mojang:minecraft:26.2" }\n')
        self.assertEqual(self.resolve()["status"], "stale")
        self.assertTrue(self.bind(replace=True)["review_required"])
        self.assertEqual(self.resolve()["status"], "located_unverified")

    def test_wrong_version_does_not_write_binding(self):
        self.change_identity(minecraft_version="26.1")
        with self.assertRaisesRegex(ValueError, "matching supported"):
            self.bind()
        self.assertFalse((self.kit / ".local/bindings").exists())

    def test_unresolved_reference_is_not_bound(self):
        self.change_identity(status="needs_review")
        with self.assertRaisesRegex(ValueError, "completed"):
            self.bind()

    def test_known_failure_markers_are_not_bound(self):
        (self.reference / "p/Good.java").write_text("Decompilation failed")
        with self.assertRaisesRegex(ValueError, "failure marker"):
            self.bind()

    def test_incomplete_source_tree_is_not_bound(self):
        self.change_identity(java_file_count=2)
        with self.assertRaisesRegex(ValueError, "file count"):
            self.bind()

    def test_external_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            binding.bind_project(self.kit, self.project, self.project)

    def test_invalid_binding_file_has_a_clean_error(self):
        result = self.bind()
        Path(result["binding_file"]).write_text("[]")
        with self.assertRaisesRegex(ValueError, "Invalid local"):
            self.resolve()

    def test_failed_atomic_refresh_preserves_old_binding(self):
        first = self.bind()
        target = Path(first["binding_file"])
        before = target.read_bytes()
        with patch.object(binding.os, "replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.bind(replace=True)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_project_change_during_binding_is_rejected(self):
        with patch.object(binding, "inspect_project", return_value={"configuration_files": []}):
            with self.assertRaisesRegex(ValueError, "changed during binding"):
                self.bind()
        self.assertFalse((self.kit / ".local/bindings").exists())

    def test_mapping_review_blocks_binding_without_writing(self):
        with (self.project / "build.gradle").open("a") as stream:
            stream.write('\nmappings "net.fabricmc:yarn:26.2+build.1:v2"\n')
        with self.assertRaisesRegex(ValueError, "matching supported"):
            self.bind()
        self.assertFalse((self.kit / ".local/bindings").exists())

    def test_legacy_binding_is_rechecked_against_current_mapping_gates(self):
        first = self.bind()
        with (self.project / "build.gradle").open("a") as stream:
            stream.write('\nmappings "net.fabricmc:yarn:26.2+build.1:v2"\n')
        target = Path(first["binding_file"])
        legacy = json.loads(target.read_text())
        # Simulate an earlier kit accepting the same unchanged Yarn configuration.
        legacy["project_check"]["project"] = binding.inspect_project(self.project)
        target.write_text(json.dumps(legacy), encoding="utf-8")
        report = self.resolve()
        self.assertEqual(report["status"], "stale")
        self.assertIn("project_reference_review_required", report["reasons"])
        self.assertNotIn("project_configuration_changed", report["reasons"])
        self.assertNotIn("instruction", report)

    def test_cli_resolve_missing_binding(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "mcsource.py"), "resolve", "--project", str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "binding_missing")


if __name__ == "__main__":
    unittest.main()
