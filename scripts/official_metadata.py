"""Verify local client fingerprints using Mojang's HTTPS version metadata."""
import hashlib
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
METADATA_HOSTS = {"piston-meta.mojang.com", "launchermeta.mojang.com"}
MAX_METADATA_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 10
SHA1 = re.compile(r"[0-9a-fA-F]{40}\Z")


class MetadataError(ValueError):
    """Official metadata could not be validated."""


def validate_metadata_url(url):
    if not isinstance(url, str):
        raise MetadataError("Metadata URL must be a string")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in METADATA_HOSTS or parsed.fragment:
        raise MetadataError("Metadata URL is outside the allowed Mojang HTTPS hosts")


class OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        validate_metadata_url(new_url)
        return super().redirect_request(request, fp, code, message, headers, new_url)


def fetch_metadata(url):
    validate_metadata_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "Minecraft-Source-Kit", "Accept": "application/json"})
    opener = urllib.request.build_opener(OfficialRedirectHandler())
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        validate_metadata_url(response.geturl())
        data = response.read(MAX_METADATA_BYTES + 1)
    if len(data) > MAX_METADATA_BYTES:
        raise MetadataError("Metadata exceeds the size limit")
    return data


def metadata_object(data):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise MetadataError("Metadata is not valid JSON") from error
    if not isinstance(value, dict):
        raise MetadataError("Metadata must contain an object")
    return value


def verify_official(identity):
    """Return verified, mismatch, or unverified; never download the client JAR."""
    result = {
        "status": "unverified", "reason": None,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_url": MANIFEST_URL,
        "minecraft_version": identity["minecraft_version"],
        "actual": {key: identity[key] for key in ("sha1", "sha256", "size_bytes")},
    }
    try:
        manifest = metadata_object(fetch_metadata(MANIFEST_URL))
        versions = manifest.get("versions")
        if not isinstance(versions, list) or any(not isinstance(v, dict) for v in versions):
            raise MetadataError("Manifest has no valid version list")
        matches = [v for v in versions if v.get("id") == identity["minecraft_version"]]
        if not matches:
            result["reason"] = "version_not_listed"
            return result
        if len(matches) != 1:
            raise MetadataError("Manifest contains duplicate version IDs")
        entry = matches[0]
        url = entry.get("url")
        validate_metadata_url(url)
        metadata_sha1 = entry.get("sha1")
        if not isinstance(metadata_sha1, str) or not SHA1.fullmatch(metadata_sha1):
            raise MetadataError("Version metadata has no valid manifest SHA-1")
        data = fetch_metadata(url)
        if hashlib.sha1(data).hexdigest() != metadata_sha1.lower():
            raise MetadataError("Version metadata SHA-1 does not match the manifest")
        version = metadata_object(data)
        if version.get("id") != identity["minecraft_version"]:
            raise MetadataError("Version metadata ID does not match the requested version")
        downloads = version.get("downloads")
        client = downloads.get("client") if isinstance(downloads, dict) else None
        if not isinstance(client, dict):
            raise MetadataError("Version metadata has no client download record")
        expected_sha1, expected_size = client.get("sha1"), client.get("size")
        if not isinstance(expected_sha1, str) or not SHA1.fullmatch(expected_sha1):
            raise MetadataError("Client record has no valid SHA-1")
        if type(expected_size) is not int or expected_size <= 0:
            raise MetadataError("Client record has no valid size")
        result.update({"version_metadata_url": url, "version_metadata_sha1": metadata_sha1.lower(), "expected": {"sha1": expected_sha1.lower(), "size_bytes": expected_size}})
        if identity["sha1"].lower() == expected_sha1.lower() and identity["size_bytes"] == expected_size:
            result.update(status="verified", reason="official_client_fingerprint_match")
        else:
            result.update(status="mismatch", reason="official_client_fingerprint_mismatch")
    except ValueError as error:
        result.update(reason="invalid_metadata", detail=str(error))
    except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
        result.update(reason="metadata_unavailable", detail=type(error).__name__)
    return result
