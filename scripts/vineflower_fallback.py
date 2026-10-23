"""Conservative, per-class Vineflower recovery for kit-owned CFR references."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

VERSION = "1.12.0"
URL = f"https://github.com/Vineflower/vineflower/releases/download/{VERSION}/vineflower-{VERSION}.jar"
SHA256 = "1dfcfe974395734fa467ce620661c7623d05ba83670de0529b1fbd63ff548b9d"
MAX_DOWNLOAD = 16 * 1024 * 1024
FAILURES = re.compile(r"Decompilation failed|Unable to fully structure code|Could not decompile|Loose catch block|bad return control flow|ConfusedCFRException|\$VF:|couldn't be decompiled", re.I)
LOG_FAILURE = re.compile(r"\b(?:WARN|ERROR|FATAL)\s*:|Exception in thread|couldn't be decompiled", re.I)
SUMMARY_CLASS = re.compile(r"^([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\r?\n-{3,}\s*$", re.M)


def contained(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Path is outside its allowed directory")
    return path


def source_path(reference, relative):
    part = PurePosixPath(relative)
    if part.is_absolute() or ".." in part.parts or "\\" in relative or ":" in relative or part.suffix != ".java":
        raise ValueError("Invalid recovery source path")
    candidate = Path(reference) / relative
    resolved = contained(reference, candidate)
    if resolved != candidate.absolute():
        raise ValueError("Symbolic-link recovery sources are not supported")
    return resolved


def scan_failures(directory):
    directory = Path(directory)
    return [p.relative_to(directory).as_posix() for p in sorted(directory.rglob("*.java")) if p.relative_to(directory).parts[0] != "diagnostics" and FAILURES.search(p.read_text(encoding="utf-8", errors="replace"))]


def get_tool(root):
    tools = Path(root) / ".local/tools"
    tools.mkdir(parents=True, exist_ok=True)
    binary = tools / f"vineflower-{VERSION}.jar"
    if binary.exists():
        if hashlib.sha256(binary.read_bytes()).hexdigest() != SHA256:
            raise ValueError("Cached Vineflower SHA-256 mismatch; preserve it for inspection")
        return binary
    temporary = tools / f"vineflower-{VERSION}.jar.part"
    # A failed download is preserved; retries require deliberate removal of that partial file.
    with temporary.open("xb") as target:
        with urllib.request.urlopen(URL, timeout=30) as response:
            digest = hashlib.sha256()
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD:
                    raise ValueError("Vineflower download exceeds the size limit")
                digest.update(chunk)
                target.write(chunk)
    if digest.hexdigest() != SHA256:
        raise ValueError("Downloaded Vineflower SHA-256 mismatch; partial file retained")
    os.replace(temporary, binary)
    return binary


def find_targets(reference):
    targets = set(scan_failures(reference))
    summary = Path(reference) / "summary.txt"
    text = summary.read_text(encoding="utf-8", errors="replace") if summary.exists() else ""
    names = SUMMARY_CLASS.findall(text)
    for name in names:
        targets.add(name.split("$", 1)[0].replace(".", "/") + ".java")
    unknown_summary = sum(1 for line in text.splitlines() if re.fullmatch(r"-{3,}", line)) != len(names)
    return sorted(targets), unknown_summary


def extract_targets(jar, targets, directory):
    stems = [relative[:-5] for relative in targets]
    seen = set()
    found = set()
    total = 0
    with zipfile.ZipFile(jar) as archive:
        for entry in archive.infolist():
            stem = next((s for s in stems if entry.filename == s + ".class" or (entry.filename.startswith(s + "$") and entry.filename.endswith(".class"))), None)
            if stem is None:
                continue
            if entry.filename in seen:
                raise ValueError("Duplicate class entry in the input JAR")
            seen.add(entry.filename)
            part = PurePosixPath(entry.filename)
            if part.is_absolute() or ".." in part.parts or "\\" in entry.filename or ":" in entry.filename:
                raise ValueError("Unsafe class path in the input JAR")
            if entry.file_size > 16 * 1024 * 1024:
                raise ValueError("Recovery class exceeds the size limit")
            total += entry.file_size
            if total > 128 * 1024 * 1024:
                raise ValueError("Recovery inputs exceed the size limit")
            target = contained(directory, Path(directory) / entry.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            if entry.filename == stem + ".class":
                found.add(stem)
    if found != set(stems):
        raise ValueError("A recovery target has no matching outer class in the input JAR")


def validate_output(file, relative):
    if not file.is_file():
        raise ValueError("Vineflower did not produce an expected source: " + relative)
    text = file.read_text(encoding="utf-8")
    name = PurePosixPath(relative).stem
    package = str(PurePosixPath(relative).parent).replace("/", ".")
    if not text.strip() or FAILURES.search(text):
        raise ValueError("Vineflower output contains a recovery failure marker: " + relative)
    if package != "." and not re.search(r"(?m)^\s*package\s+" + re.escape(package) + r"\s*;", text):
        raise ValueError("Vineflower output package does not match the target")
    if not re.search(r"\b(?:class|interface|enum|record)\s+" + re.escape(name) + r"\b", text):
        raise ValueError("Vineflower output has no expected type declaration")
    return hashlib.sha256(file.read_bytes()).hexdigest()


def repair_reference(root, reference, identity):
    reference = contained(Path(root) / ".local/references", reference)
    record = contained(reference, reference / "REFERENCE.json")
    if record.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Reference identity exceeds the size limit")
    metadata = json.loads(record.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Reference identity must be an object")
    if metadata.get("sha256") != identity["sha256"]:
        raise ValueError("Recovery JAR SHA-256 does not match the original reference")
    decompiler = metadata.get("decompiler")
    if not isinstance(decompiler, dict) or decompiler.get("name") != "CFR" or metadata.get("status") not in ("needs_review", "generated_unverified"):
        raise ValueError("Recovery requires a completed CFR reference")
    if "fallback" in metadata:
        raise ValueError("A recovery attempt is already recorded; inspect its diagnostics before any retry")
    targets, unknown_summary = find_targets(reference)
    if not targets:
        if unknown_summary:
            raise ValueError("CFR summary has unrecognized findings; manual review is required")
        return metadata
    for relative in targets:
        if not source_path(reference, relative).is_file():
            raise ValueError("A recovery target has no original CFR source: " + relative)
    diagnostics = contained(reference, reference / "diagnostics/vineflower")
    diagnostics.mkdir(parents=True, exist_ok=False)
    work = contained(diagnostics, diagnostics / "workspace")
    work.mkdir()
    inputs, outputs = work / "classes", work / "output"
    inputs.mkdir()
    outputs.mkdir()
    report = {"tool": "Vineflower", "version": VERSION, "sha256": SHA256, "url": URL, "started_utc": datetime.now(timezone.utc).isoformat(), "status": "running", "targets": targets, "input_sha256": identity["sha256"], "replaced": [], "workspace": "retained", "unknown_summary_findings": unknown_summary}
    metadata.update(fallback=report, status="needs_review")
    record.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    replaced = []
    try:
        # Preserve every original before any replacement. Backups do not end in .java.
        originals = diagnostics / "cfr-original"
        originals.mkdir()
        for relative in targets:
            backup = contained(originals, originals / (relative + ".cfr"))
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path(reference, relative), backup)
        report["original_sha256"] = {relative: hashlib.sha256((originals / (relative + ".cfr")).read_bytes()).hexdigest() for relative in targets}
        extract_targets(identity["input_jar"], targets, inputs)
        binary = get_tool(root)
        log_path = diagnostics / "vineflower.log"
        with log_path.open("w", encoding="utf-8") as log:
            subprocess.run(["java", "-Xmx2G", "-jar", str(binary), "--thread-count=2", "--folder", "-e=" + identity["input_jar"], str(inputs), str(outputs)], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        if LOG_FAILURE.search(log_path.read_text(encoding="utf-8", errors="replace")):
            raise ValueError("Vineflower logged a warning or error; originals retained")
        hashes = {relative: validate_output(source_path(outputs, relative), relative) for relative in targets}
        if scan_failures(outputs):
            raise ValueError("Vineflower output contains additional failure markers")
        for relative in targets:
            os.replace(source_path(outputs, relative), source_path(reference, relative))
            replaced.append(relative)
        report.update(status="recovered_unverified", replaced=targets, output_sha256=hashes)
        metadata["failure_marker_files"] = scan_failures(reference)
        metadata["status"] = "needs_review" if metadata["failure_marker_files"] or unknown_summary else "generated_unverified"
        # Delete only this attempt's temporary workspace. Keep original sources, summaries, and logs.
        try:
            shutil.rmtree(contained(diagnostics, work))
            report["workspace"] = "removed"
        except OSError as error:
            report["cleanup_error"] = type(error).__name__
    except (Exception, KeyboardInterrupt) as error:
        rollback_errors = []
        for relative in replaced:
            try:
                shutil.copy2(diagnostics / "cfr-original" / (relative + ".cfr"), source_path(reference, relative))
            except OSError as rollback_error:
                rollback_errors.append({"file": relative, "error": str(rollback_error)})
        report.update(status="failed", replaced=[item["file"] for item in rollback_errors], error=str(error))
        if rollback_errors:
            report["rollback_errors"] = rollback_errors
        metadata["status"] = "needs_review"
        if isinstance(error, KeyboardInterrupt):
            report["status"] = "interrupted"
            raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        record.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata
