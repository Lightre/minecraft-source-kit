"""Tests for bounded, read-only project declaration checks."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import mcsource
from project_target import check_project, inspect_project


class ProjectTargetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "mod"
        self.project.mkdir()
        self.jar = self.root / "input.jar"
        with zipfile.ZipFile(self.jar, "w") as archive:
            archive.writestr("version.json", json.dumps({"id": "26.2"}))
            archive.writestr("net/minecraft/client/Minecraft.class", b"\xca\xfe\xba\xbe\0\0\0\x45")
        self.identity = mcsource.inspect_jar(self.jar)

    def write_project(self, version="26.2", dependency='minecraft "com.mojang:minecraft:${project.minecraft_version}"', name="build.gradle"):
        (self.project / "gradle.properties").write_text("minecraft_version=" + version + "\n", encoding="utf-8")
        (self.project / name).write_text('plugins { id "fabric-loom" }\ndependencies {\n' + dependency + '\n mappings loom.officialMojangMappings()\n}\n', encoding="utf-8")

    def report(self):
        return check_project(self.project, self.identity)

    def test_property_backed_groovy_match_is_not_api_verification(self):
        self.write_project()
        report = self.report()
        self.assertEqual(report["status"], "declared_version_match")
        self.assertEqual(report["project"]["mapping_hints"], ["mojang"])
        self.assertTrue(report["review_required"])
        self.assertEqual(report["api_compatibility"], "unverified")
        self.assertEqual(report["project"]["evidence"][1]["line"], 3)

    def test_literal_kotlin_dependency(self):
        self.write_project(dependency='minecraft("com.mojang:minecraft:26.2")', name="build.gradle.kts")
        self.assertEqual(self.report()["status"], "declared_version_match")

    def test_kotlin_property_interpolation(self):
        self.write_project(dependency='minecraft("com.mojang:minecraft:$minecraft_version")', name="build.gradle.kts")
        self.assertEqual(self.report()["status"], "declared_version_match")

    def test_wrong_version(self):
        self.write_project(version="26.1")
        self.assertEqual(self.report()["status"], "version_mismatch")

    def test_conflicting_property_and_dependency(self):
        self.write_project(version="26.1", dependency='minecraft "com.mojang:minecraft:26.2"')
        self.assertEqual(self.report()["status"], "needs_review")

    def test_property_alone_is_not_a_target(self):
        self.write_project(dependency="")
        self.assertEqual(self.report()["status"], "needs_review")

    def test_groovy_single_quotes_do_not_interpolate(self):
        self.write_project(dependency="minecraft 'com.mojang:minecraft:${minecraft_version}'")
        self.assertEqual(self.report()["status"], "needs_review")

    def test_unknown_expression_is_not_guessed(self):
        self.write_project(dependency='minecraft "com.mojang:minecraft:${versions.minecraft}"')
        self.assertEqual(self.report()["status"], "needs_review")

    def test_duplicate_property_is_ambiguous(self):
        self.write_project()
        with (self.project / "gradle.properties").open("a") as stream:
            stream.write("minecraft_version=26.2\n")
        self.assertEqual(self.report()["status"], "needs_review")

    def test_ranges_and_dynamic_versions_are_not_exact(self):
        for version in ("26.+", "[26.1,26.3)", "latest.release"):
            with self.subTest(version=version):
                self.write_project(version=version)
                self.assertEqual(self.report()["status"], "needs_review")

    def test_comments_are_not_dependencies(self):
        self.write_project(dependency='// minecraft "com.mojang:minecraft:26.2"\n/* minecraft "com.mojang:minecraft:26.2" */')
        self.assertEqual(self.report()["status"], "needs_review")

    def test_comments_do_not_create_conflicts(self):
        self.write_project(dependency='// minecraft "com.mojang:minecraft:26.1"\nminecraft "com.mojang:minecraft:26.2"')
        self.assertEqual(self.report()["status"], "declared_version_match")

    def test_multi_project_requires_review(self):
        self.write_project()
        (self.project / "settings.gradle").write_text("include 'common', 'fabric'", encoding="utf-8")
        self.assertEqual(self.report()["status"], "needs_review")

    def test_unknown_layout_requires_review(self):
        self.assertEqual(self.report()["status"], "needs_review")

    def test_yarn_is_only_a_hint(self):
        self.write_project()
        with (self.project / "build.gradle").open("a") as stream:
            stream.write('\nmappings "net.fabricmc:yarn:26.2+build.1:v2"\n')
        report = self.report()
        self.assertIn("yarn", report["project"]["mapping_hints"])
        self.assertEqual(report["api_compatibility"], "unverified")

    def test_yarn_declaration_blocks_same_version_preparation(self):
        self.write_project()
        build = self.project / "build.gradle"
        build.write_text(build.read_text().replace("mappings loom.officialMojangMappings()", 'mappings "net.fabricmc:yarn:26.2+build.1:v2"'))
        report = self.report()
        self.assertEqual(report["status"], "needs_review")
        self.assertTrue(report["namespace_review"]["blocking"])
        self.assertEqual(report["namespace_review"]["evidence"][0], {"file": "build.gradle", "line": 4, "hint": "yarn"})
        with patch.object(mcsource, "ROOT", self.root), patch.object(mcsource, "build_cfr") as build_tool, patch.object(mcsource, "verify_official") as verify:
            with self.assertRaisesRegex(ValueError, "needs_review"):
                mcsource.prepare(self.jar, self.project, official=True)
            build_tool.assert_not_called()
            verify.assert_not_called()
        self.assertFalse((self.root / ".local").exists())

    def test_multiple_mapping_hints_are_not_an_automatic_match(self):
        self.write_project()
        with (self.project / "build.gradle").open("a") as stream:
            stream.write('\nmappings "net.fabricmc:yarn:26.2+build.1:v2"\n')
        report = self.report()
        self.assertEqual(report["status"], "needs_review")
        self.assertIn("multiple_mapping_hints_require_review", report["namespace_review"]["reasons"])

    def test_intermediary_and_parchment_require_review(self):
        for coordinate in ("net.fabricmc:intermediary:26.2", "org.parchmentmc.data:parchment-26.2:2026.10.01@zip"):
            with self.subTest(coordinate=coordinate):
                self.write_project()
                build = self.project / "build.gradle"
                build.write_text(build.read_text().replace("mappings loom.officialMojangMappings()", 'mappings "' + coordinate + '"'))
                self.assertEqual(self.report()["status"], "needs_review")

    def test_commented_mappings_do_not_trigger_review(self):
        self.write_project()
        with (self.project / "build.gradle").open("a") as stream:
            stream.write('\n// mappings "net.fabricmc:yarn:26.2:v2"\n/* parchment("example") */\n')
        self.assertEqual(self.report()["status"], "declared_version_match")

    def test_repository_mention_is_not_a_parchment_mapping(self):
        self.write_project()
        with (self.project / "build.gradle").open("a") as stream:
            stream.write('\nrepositories { maven { url "https://maven.parchmentmc.org" } }\n')
        self.assertEqual(self.report()["project"]["mapping_hints"], ["mojang"])

    def test_absent_mapping_declaration_remains_unverified(self):
        self.write_project()
        build = self.project / "build.gradle"
        build.write_text(build.read_text().replace("mappings loom.officialMojangMappings()", ""))
        report = self.report()
        self.assertEqual(report["status"], "declared_version_match")
        self.assertEqual(report["namespace_review"]["status"], "unverified")
        self.assertEqual(report["namespace_review"]["project_hints"], [])
        self.assertEqual(report["api_compatibility"], "unverified")

    def test_unnamed_input_requires_review(self):
        self.write_project()
        self.identity["named_client_class_present"] = False
        report = self.report()
        self.assertEqual(report["status"], "needs_review")
        self.assertIn("named_client_source_not_established", report["namespace_review"]["reasons"])

    def test_unsupported_source_namespace_requires_review(self):
        self.write_project()
        self.identity["namespace"] = "yarn"
        self.assertEqual(self.report()["status"], "needs_review")

    def test_version_mismatch_stays_visible_with_mapping_warnings(self):
        self.write_project(version="26.1")
        self.identity["namespace"] = "yarn"
        report = self.report()
        self.assertEqual(report["status"], "version_mismatch")
        self.assertTrue(report["namespace_review"]["blocking"])

    def test_project_tree_is_unchanged(self):
        self.write_project()
        before = {p.relative_to(self.project): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.project.rglob("*") if p.is_file()}
        self.report()
        after = {p.relative_to(self.project): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_prepare_blocks_mismatch_before_tools_or_output(self):
        self.write_project(version="26.1")
        with patch.object(mcsource, "ROOT", self.root), patch.object(mcsource, "build_cfr") as build, patch.object(mcsource, "check_jdk") as jdk:
            with self.assertRaisesRegex(ValueError, "version_mismatch"):
                mcsource.prepare(self.jar, self.project)
            build.assert_not_called()
            jdk.assert_not_called()
        self.assertFalse((self.root / ".local").exists())

    def test_prepare_saves_matching_project_evidence(self):
        self.write_project()

        def decompile(args, **kwargs):
            output = Path(args[args.index("--outputdir") + 1])
            (output / "Good.java").write_text("class Good {}", encoding="utf-8")

        with patch.object(mcsource, "ROOT", self.root), patch.object(mcsource, "check_jdk"), patch.object(mcsource, "build_cfr", return_value=self.root / "tool.jar"), patch.object(mcsource, "run", side_effect=decompile), patch("builtins.print"):
            self.assertEqual(mcsource.prepare(self.jar, self.project), 0)
        record = next((self.root / ".local/references").glob("*/REFERENCE.json"))
        saved = json.loads(record.read_text())
        self.assertEqual(saved["project_check"]["status"], "declared_version_match")
        self.assertEqual(saved["project_check"]["api_compatibility"], "unverified")

    def test_cli_reports_mismatch_as_json(self):
        self.write_project(version="26.1")
        result = subprocess.run([sys.executable, str(SCRIPTS / "mcsource.py"), "check-project", "--jar", str(self.jar), "--project", str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "version_mismatch")


if __name__ == "__main__":
    unittest.main()
