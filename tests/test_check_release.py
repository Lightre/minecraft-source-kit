import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_release import check_release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "docs/releases").mkdir(parents=True)
        (self.root / "scripts/mcsource.py").write_text('VERSION = "0.1.0"\n', encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text("## v0.1.0 - 2026-10-23\n", encoding="utf-8")
        self.notes = self.root / "docs/releases/v0.1.0.md"
        self.notes.write_text("# v0.1.0\n\nInitial release.\n", encoding="utf-8")

    def test_matching_metadata(self):
        self.assertEqual(check_release(self.root, "v0.1.0"), self.notes)

    def test_unsupported_tag_and_version_mismatch(self):
        for tag in ("v0.1.0-rc1", "v01.1.0", "../notes", "v0.2.0"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                check_release(self.root, tag)

    def test_dated_changelog_required(self):
        for text in ("## v0.1.0 - Unreleased", "## v0.1.0 - 2026-02-30",
                     "## v0.1.0 - 2026-10-23\n## v0.1.0 - 2026-10-24"):
            with self.subTest(text=text):
                (self.root / "CHANGELOG.md").write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    check_release(self.root, "v0.1.0")

    def test_missing_wrong_or_empty_notes_rejected(self):
        for text in ("# v0.2.0\nNotes", "# v0.1.0\n\n", ""):
            with self.subTest(text=text):
                self.notes.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    check_release(self.root, "v0.1.0")
        self.notes.unlink()
        with self.assertRaises(FileNotFoundError):
            check_release(self.root, "v0.1.0")
