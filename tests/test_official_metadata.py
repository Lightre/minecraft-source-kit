"""Offline tests for Mojang client fingerprint verification and preparation gates."""
import hashlib
import json
import io
from contextlib import redirect_stdout
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mcsource
import official_metadata as official


class OfficialMetadataTests(unittest.TestCase):
    def setUp(self):
        self.identity = {"minecraft_version": "26.2", "sha1": "a" * 40, "sha256": "b" * 64, "size_bytes": 32}
        self.url = "https://piston-meta.mojang.com/v1/packages/test/26.2.json"
        self.version = {"id": "26.2", "downloads": {"client": {"sha1": "a" * 40, "size": 32}}}

    def payloads(self, version=None):
        data = json.dumps(self.version if version is None else version).encode()
        manifest = {"versions": [{"id": "26.2", "url": self.url, "sha1": hashlib.sha1(data).hexdigest()}]}
        return json.dumps(manifest).encode(), data

    def verify(self, version=None):
        with patch.object(official, "fetch_metadata", side_effect=self.payloads(version)):
            return official.verify_official(self.identity)

    def test_matching_fingerprint_is_verified(self):
        report = self.verify()
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["actual"]["sha256"], "b" * 64)
        self.assertEqual(report["version_metadata_url"], self.url)

    def test_wrong_hash_is_mismatch(self):
        self.identity["sha1"] = "c" * 40
        self.assertEqual(self.verify()["status"], "mismatch")

    def test_wrong_size_is_mismatch(self):
        self.identity["size_bytes"] = 33
        self.assertEqual(self.verify()["status"], "mismatch")

    def test_metadata_hash_mismatch_is_unverified(self):
        manifest, data = self.payloads()
        with patch.object(official, "fetch_metadata", side_effect=[manifest, data + b" "]):
            report = official.verify_official(self.identity)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["reason"], "invalid_metadata")

    def test_metadata_id_must_match(self):
        self.version["id"] = "26.1"
        self.assertEqual(self.verify()["reason"], "invalid_metadata")

    def test_unknown_version_is_not_a_mismatch(self):
        with patch.object(official, "fetch_metadata", return_value=b'{"versions": []}') as fetch:
            report = official.verify_official(self.identity)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["reason"], "version_not_listed")
        self.assertEqual(fetch.call_count, 1)

    def test_offline_is_unverified_without_retries(self):
        with patch.object(official, "fetch_metadata", side_effect=urllib.error.URLError("offline")) as fetch:
            report = official.verify_official(self.identity)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["reason"], "metadata_unavailable")
        self.assertEqual(fetch.call_count, 1)

    def test_malformed_json_and_schema_are_unverified(self):
        for data in (b"not JSON", b"[]", b"{}", b'{"versions":[1]}'):
            with self.subTest(data=data), patch.object(official, "fetch_metadata", return_value=data):
                self.assertEqual(official.verify_official(self.identity)["reason"], "invalid_metadata")

    def test_duplicate_version_id_is_unverified(self):
        manifest, data = self.payloads()
        obj = json.loads(manifest)
        obj["versions"] *= 2
        with patch.object(official, "fetch_metadata", return_value=json.dumps(obj).encode()):
            self.assertEqual(official.verify_official(self.identity)["reason"], "invalid_metadata")

    def test_missing_or_invalid_client_record_is_unverified(self):
        for downloads in ({}, {"client": []}, {"client": {"sha1": "x", "size": 32}}, {"client": {"sha1": "a"*40, "size": True}}, {"client": {"sha1": "a"*40, "size": -1}}):
            with self.subTest(downloads=downloads):
                self.assertEqual(self.verify({"id": "26.2", "downloads": downloads})["reason"], "invalid_metadata")

    def test_non_official_url_is_not_requested(self):
        for url in ("http://piston-meta.mojang.com/version.json", "https://example.com/version.json", "https://piston-meta.mojang.com.evil.test/file", "https://user@piston-meta.mojang.com/file", "https://piston-meta.mojang.com:8080/file"):
            with self.subTest(url=url):
                self.url = url
                with patch.object(official, "fetch_metadata", side_effect=self.payloads()) as fetch:
                    report = official.verify_official(self.identity)
                self.assertEqual(report["reason"], "invalid_metadata")
                self.assertEqual(fetch.call_count, 1)

    def test_redirect_cannot_leave_official_https_hosts(self):
        with self.assertRaises(official.MetadataError):
            official.OfficialRedirectHandler().redirect_request(None, None, 302, "Found", {}, "https://example.com/metadata")

    def test_download_is_bounded(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = official.MANIFEST_URL
        response.read.return_value = b"x" * (official.MAX_METADATA_BYTES + 1)
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(official.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(official.MetadataError, "size limit"):
                official.fetch_metadata(official.MANIFEST_URL)
        response.read.assert_called_once_with(official.MAX_METADATA_BYTES + 1)

    def test_prepare_blocks_failed_provenance_before_tools(self):
        for status in ("mismatch", "unverified"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                jar = self.make_jar(root)
                with patch.object(mcsource, "ROOT", root), patch.object(mcsource, "verify_official", return_value={"status": status, "reason": "test_reason"}), patch.object(mcsource, "build_cfr") as build, patch.object(mcsource, "check_jdk") as jdk:
                    with self.assertRaisesRegex(ValueError, "Official JAR verification did not pass"):
                        mcsource.prepare(jar, official=True)
                    build.assert_not_called()
                    jdk.assert_not_called()
                self.assertFalse((root / ".local").exists())

    def make_jar(self, root):
        jar = root / "client.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            archive.writestr("version.json", '{"id":"26.2"}')
            archive.writestr("net/minecraft/client/Minecraft.class", b"\xca\xfe\xba\xbe\0\0\0\x45")
        return jar

    def test_verify_cli_status_codes(self):
        for status, expected in (("verified", 0), ("mismatch", 1), ("unverified", 2)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                jar = self.make_jar(Path(temp))
                output = io.StringIO()
                with patch.object(sys, "argv", ["mcsource.py", "verify", "--jar", str(jar)]), patch.object(mcsource, "verify_official", return_value={"status": status}), redirect_stdout(output):
                    self.assertEqual(mcsource.main(), expected)
                self.assertEqual(json.loads(output.getvalue())["status"], status)

    def test_plain_prepare_does_not_verify_over_network(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jar = self.make_jar(root)

            def decompile(args, **kwargs):
                output = Path(args[args.index("--outputdir") + 1])
                (output / "Good.java").write_text("class Good {}", encoding="utf-8")

            with patch.object(mcsource, "ROOT", root), patch.object(mcsource, "verify_official") as verify, patch.object(mcsource, "check_jdk"), patch.object(mcsource, "build_cfr", return_value=root / "tool.jar"), patch.object(mcsource, "run", side_effect=decompile), patch("builtins.print"):
                self.assertEqual(mcsource.prepare(jar), 0)
                verify.assert_not_called()
            record = next((root / ".local/references").glob("*/REFERENCE.json"))
            self.assertEqual(json.loads(record.read_text())["provenance"], "unverified")

    def test_prepare_records_verified_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jar = self.make_jar(root)
            verification = {"status": "verified", "reason": "official_client_fingerprint_match"}

            def decompile(args, **kwargs):
                output = Path(args[args.index("--outputdir") + 1])
                (output / "Good.java").write_text("class Good {}", encoding="utf-8")

            with patch.object(mcsource, "ROOT", root), patch.object(mcsource, "verify_official", return_value=verification), patch.object(mcsource, "check_jdk"), patch.object(mcsource, "build_cfr", return_value=root / "tool.jar"), patch.object(mcsource, "run", side_effect=decompile), patch("builtins.print"):
                self.assertEqual(mcsource.prepare(jar, official=True), 0)
            record = next((root / ".local/references").glob("*/REFERENCE.json"))
            identity = json.loads(record.read_text())
            self.assertEqual(identity["provenance"], "verified_official_client")
            self.assertEqual(identity["official_verification"], verification)
            self.assertEqual(identity["namespace"], "unverified")


if __name__ == "__main__":
    unittest.main()
