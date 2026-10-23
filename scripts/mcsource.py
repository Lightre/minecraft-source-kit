"""Prepare local Minecraft source references without editing a mod project."""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFR_COMMIT = "c4145259dfcd8ad3e99004e4d9ecb0aed55dcc5a"
CFR_REPO = "https://github.com/leibnitz27/cfr.git"
FAILURES = re.compile(r"Decompilation failed|Unable to fully structure code|Could not decompile|Loose catch block|bad return control flow|ConfusedCFRException", re.I)


def inspect_jar(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("version.json")
        if info.file_size > 1024 * 1024:
            raise ValueError("version.json exceeds the metadata size limit")
        version = json.loads(archive.read(info))
        version_id = version.get("id")
        if not isinstance(version_id, str) or not version_id:
            raise ValueError("version.json has no valid version id")
        classes = [entry for entry in archive.infolist() if entry.filename.endswith(".class")]
        if not classes:
            raise ValueError("The JAR contains no class files")
        majors = set()
        for entry in classes:
            with archive.open(entry) as stream:
                header = stream.read(8)
            if len(header) != 8 or header[:4] != b"\xca\xfe\xba\xbe":
                raise ValueError("Invalid class header: " + entry.filename)
            majors.add(struct.unpack(">H", header[6:8])[0])
        named = any(e.filename == "net/minecraft/client/Minecraft.class" for e in classes)
        return {
            "schema_version": 1, "minecraft_version": version_id,
            "input_jar": str(path), "sha256": digest.hexdigest(),
            "size_bytes": path.stat().st_size, "class_count": len(classes),
            "class_major_versions": sorted(majors),
            "scope": "client" if named else "unverified",
            "namespace": "unverified",
            "named_client_class_present": named,
            "provenance": "unverified",
        }


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def build_cfr():
    tools = ROOT / ".local/tools"
    source = tools / ("cfr-" + CFR_COMMIT)
    binary = source / "build/cfr.jar"
    for name in ("git", "java", "javac", "jar", "javap"):
        if not shutil.which(name):
            raise ValueError("Required executable is missing: " + name)
    if binary.is_file():
        return binary
    tools.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        source.mkdir()
        run(["git", "init", source])
        run(["git", "-C", source, "fetch", "--depth", "1", CFR_REPO, CFR_COMMIT])
        run(["git", "-C", source, "checkout", "--detach", "FETCH_HEAD"])
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != CFR_COMMIT:
        raise ValueError("CFR checkout does not match the pinned revision; preserve it and use a clean tool directory")
    build = source / "build"
    classes = build / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    template = source / "src-templates/org/benf/cfr/reader/util/CfrVersionInfo.java"
    generated = build / "CfrVersionInfo.java"
    generated.write_text(template.read_text(encoding="utf-8").replace("${project.version}", "0.153-SNAPSHOT").replace("${git.commit.id.abbrev}", CFR_COMMIT[:7]).replace("${git.dirty}", "false"), encoding="utf-8")
    sources = sorted((source / "src").rglob("*.java")) + [generated]
    arguments = build / "sources.txt"
    arguments.write_text("\n".join('"' + p.as_posix() + '"' for p in sources), encoding="utf-8")
    run(["javac", "--release", "8", "-encoding", "UTF-8", "-d", classes, "@" + str(arguments)])
    run(["jar", "--create", "--file", binary, "--main-class", "org.benf.cfr.reader.Main", "-C", classes, "."])
    return binary


def scan_failures(directory):
    return [p.relative_to(directory).as_posix() for p in sorted(directory.rglob("*.java")) if FAILURES.search(p.read_text(encoding="utf-8", errors="replace"))]


def prepare(path):
    identity = inspect_jar(path)
    if not identity["named_client_class_present"]:
        raise ValueError("This baseline requires a named client JAR; obfuscated or other layouts need an explicit mapping workflow")
    binary = build_cfr()
    safe_version = re.sub(r"[^A-Za-z0-9._-]", "_", identity["minecraft_version"])[:80]
    output = ROOT / ".local/references" / (safe_version + "-" + identity["sha256"][:12])
    output.mkdir(parents=True, exist_ok=False)
    identity.update({"created_utc": datetime.now(timezone.utc).isoformat(), "decompiler": {"name": "CFR", "commit": CFR_COMMIT}, "status": "running"})
    record = output / "REFERENCE.json"
    record.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    try:
        with (output / "decompiler.log").open("w", encoding="utf-8") as log:
            run(["java", "-Xmx3G", "-jar", binary, identity["input_jar"], "--outputdir", output, "--silent", "true"], stdout=log, stderr=subprocess.STDOUT)
        identity["java_file_count"] = sum(1 for _ in output.rglob("*.java"))
        identity["failure_marker_files"] = scan_failures(output)
        summary = output / "summary.txt"
        summary_text = summary.read_text(encoding="utf-8", errors="replace") if summary.exists() else ""
        identity["summary_has_findings"] = "----------------------------" in summary_text
        if not identity["java_file_count"]:
            raise ValueError("Decompiler produced no Java source files")
        identity["status"] = "needs_review" if identity["failure_marker_files"] or identity["summary_has_findings"] else "generated_unverified"
    except Exception:
        identity["status"] = "failed"
        raise
    finally:
        record.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reference": str(output), **identity}, indent=2))
    return 2 if identity["status"] == "needs_review" else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "prepare"))
    parser.add_argument("--jar", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            print(json.dumps(inspect_jar(args.jar), indent=2))
            return 0
        return prepare(args.jar)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
