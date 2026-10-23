"""Kit-local reference bindings; target mod projects are never written."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from project_target import check_project, inspect_project
from vineflower_fallback import FAILURES, contained, source_path


def binding_path(root, project):
    project = Path(project).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("Project path must be a directory")
    key = hashlib.sha256(os.path.normcase(str(project)).encode("utf-8")).hexdigest()
    directory = contained(Path(root).resolve(), Path(root).resolve() / ".local/bindings")
    return project, directory / (key + ".json")


def read_reference(root, reference):
    directory = contained(Path(root).resolve(), Path(root).resolve() / ".local/references")
    reference = contained(directory, reference)
    record = reference / "REFERENCE.json"
    if record.is_symlink() or record.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Reference identity is a symlink or exceeds the size limit")
    raw = record.read_bytes()
    identity = json.loads(raw)
    if not isinstance(identity, dict) or any(not isinstance(identity.get(key), str) or not identity[key] for key in ("minecraft_version", "sha256", "namespace", "provenance", "scope")):
        raise ValueError("Reference identity is missing required string fields")
    if identity.get("schema_version") != 1 or identity.get("status") != "generated_unverified" or identity.get("validation_fixture"):
        raise ValueError("Binding requires a completed, non-fixture reference without unresolved findings")
    if type(identity.get("java_file_count")) is not int or identity["java_file_count"] <= 0:
        raise ValueError("Reference identity has no valid Java file count")
    return reference, identity, hashlib.sha256(raw).hexdigest()


def source_snapshot(reference):
    digest = hashlib.sha256()
    count = 0
    for file in sorted(Path(reference).rglob("*.java")):
        relative = file.relative_to(reference).as_posix()
        if relative.split("/", 1)[0] == "diagnostics":
            continue
        raw = source_path(reference, relative).read_bytes()
        if FAILURES.search(raw.decode("utf-8", errors="replace")):
            raise ValueError("Reference still contains a source failure marker: " + relative)
        digest.update(relative.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        count += 1
    if not count:
        raise ValueError("Reference contains no Java source files")
    return {"sha256": digest.hexdigest(), "java_file_count": count}


def instruction(root, project, reference):
    return ("Use Minecraft Source Kit at " + json.dumps(Path(root).resolve().as_posix()) +
            " to resolve the local reference binding for project " + json.dumps(project.as_posix()) +
            " before using Minecraft APIs in each session. The current reference is " + json.dumps(reference.as_posix()) +
            ". Do not use a missing or stale binding. A located reference is unverified reconstructed source; review effective target, mappings, and diagnostics, then verify each API symbol from source. Do not modify the reference or include it in the build.")


def bind_project(root, project, reference, replace=False):
    root = Path(root).resolve()
    project, target = binding_path(root, project)
    reference, identity, record_hash = read_reference(root, reference)
    report = check_project(project, identity)
    if report["status"] != "declared_version_match":
        raise ValueError("Binding requires matching supported project declarations; run check-project for evidence")
    sources = source_snapshot(reference)
    if sources["java_file_count"] != identity["java_file_count"]:
        raise ValueError("Reference Java file count does not match its identity")
    if inspect_project(project)["configuration_files"] != report["project"]["configuration_files"]:
        raise ValueError("Project configuration changed during binding; no binding was written")
    if hashlib.sha256((reference / "REFERENCE.json").read_bytes()).hexdigest() != record_hash:
        raise ValueError("Reference identity changed during binding; no binding was written")
    if target.exists() and not replace:
        raise ValueError("Existing binding is preserved; use --replace-binding only after reviewing the new target")
    target.parent.mkdir(parents=True, exist_ok=True)
    contained(root / ".local/bindings", target)
    binding = {
        "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "project_path": str(project), "reference": reference.relative_to(root).as_posix(),
        "reference_identity_sha256": record_hash, "source_snapshot": sources,
        "project_check": report,
    }
    # Stage in the binding directory; never truncate an existing valid binding.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix="binding-", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            json.dump(binding, file, indent=2)
            file.write("\n")
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return {"status": "located_unverified", "binding_file": str(target), "reference": str(reference), "review_required": True, "instruction": instruction(root, project, reference)}


def resolve_project(root, project):
    root = Path(root).resolve()
    project, target = binding_path(root, project)
    if not target.exists():
        return {"status": "binding_missing", "project_path": str(project), "review_required": True}
    contained(root / ".local/bindings", target)
    if target.is_symlink() or target.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Binding file is a symlink or exceeds the size limit")
    binding = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(binding, dict) or binding.get("schema_version") != 1 or not isinstance(binding.get("project_path"), str) or os.path.normcase(binding["project_path"]) != os.path.normcase(str(project)) or not isinstance(binding.get("reference"), str):
        raise ValueError("Invalid local binding identity")
    reasons = []
    saved_check = binding.get("project_check")
    if not isinstance(saved_check, dict) or saved_check.get("status") != "declared_version_match" or not isinstance(saved_check.get("project"), dict):
        raise ValueError("Binding has no project configuration snapshot")
    current = inspect_project(project)
    if current["issues"] or current["declared_minecraft_version"] != saved_check["project"].get("declared_minecraft_version"):
        reasons.append("project_target_needs_review")
    if current["configuration_files"] != saved_check["project"].get("configuration_files"):
        reasons.append("project_configuration_changed")
    try:
        reference, identity, record_hash = read_reference(root, root / binding["reference"])
        if record_hash != binding.get("reference_identity_sha256"):
            reasons.append("reference_identity_changed")
        elif not reasons and source_snapshot(reference) != binding.get("source_snapshot"):
            reasons.append("reference_sources_changed")
    except (OSError, ValueError):
        reasons.append("reference_unavailable_or_invalid")
        reference = None
    if reasons:
        return {"status": "stale", "project_path": str(project), "reasons": reasons, "review_required": True}
    return {"status": "located_unverified", "binding_file": str(target), "reference": str(reference), "project_check": saved_check, "review_required": True, "instruction": instruction(root, project, reference)}
