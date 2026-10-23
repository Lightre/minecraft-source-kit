"""Read declared Gradle Minecraft targets without executing project code."""
import hashlib
import re
from pathlib import Path

EXACT_VERSION = re.compile(r"(?:\d+[A-Za-z0-9._-]*|[A-Za-z]+\d+[A-Za-z0-9._-]*)\Z")
PROPERTY = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*[=:]\s*(.*?)\s*\Z")
COORDINATE = re.compile(r'''(?:\bminecraft|\badd\s*\(\s*["']minecraft["']\s*,)\s*\(?\s*(["'])(com\.mojang:minecraft:[^"'\n]+)\1''')
PLACEHOLDER = re.compile(r"\$\{(?:project\.)?([A-Za-z_][A-Za-z0-9_]*)\}|\$(?:project\.)?([A-Za-z_][A-Za-z0-9_]*)")


def strip_comments(text):
    """Remove ordinary Gradle comments while preserving quoted strings and lines."""
    return re.sub(r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|//[^\n]*|/\*[\s\S]*?\*/''', lambda m: m.group(1) or "\n" * m.group(0).count("\n"), text)


def inspect_project(path):
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project path must be a directory")
    evidence = []
    issues = []
    properties = {}
    versions = []
    mapping_hints = set()
    mapping_evidence = []
    loader_hints = set()
    files = []
    builds = []
    for name in ("gradle.properties", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"):
        file = root / name
        if not file.is_file():
            continue
        if file.stat().st_size > 1024 * 1024:
            raise ValueError("Project configuration exceeds the size limit: " + name)
        data = file.read_bytes()
        text = data.decode("utf-8-sig")
        files.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})
        if name == "gradle.properties":
            for number, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith(("#", "!")) or not line.strip():
                    continue
                match = PROPERTY.fullmatch(line.strip())
                if not match:
                    issues.append("Unsupported gradle.properties syntax at line " + str(number))
                    continue
                key, value = match.groups()
                if key in properties:
                    issues.append("Duplicate Gradle property: " + key)
                properties[key] = value
                if key == "minecraft_version":
                    versions.append(value)
                    evidence.append({"file": name, "line": number, "kind": "minecraft_version", "value": value})
        elif name.startswith("build."):
            builds.append((name, strip_comments(text)))
        else:
            clean = strip_comments(text)
            if re.search(r"\binclude(?:Build)?\b", clean):
                issues.append("Multi-project or included-build configuration requires manual review")
    if not builds:
        issues.append("No root build.gradle or build.gradle.kts found")
    if len(builds) > 1:
        issues.append("Both root Gradle build formats exist; the active script is ambiguous")
    dependency_found = False
    for name, text in builds:
        if "fabric-loom" in text or "net.fabricmc.fabric-loom" in text:
            loader_hints.add("fabric")
        if "net.neoforged" in text:
            loader_hints.add("neoforge")
        if "net.minecraftforge" in text:
            loader_hints.add("forge")
        for hint, pattern in (
            ("mojang", r"\bofficialMojangMappings\s*\("),
            ("yarn", r"net\.fabricmc:yarn:"),
            ("intermediary", r"net\.fabricmc:intermediary:"),
            ("parchment", r"org\.parchmentmc(?:\.data)?:|\bparchment\s*\("),
        ):
            for match in re.finditer(pattern, text):
                mapping_hints.add(hint)
                mapping_evidence.append({"file": name, "line": text.count("\n", 0, match.start()) + 1, "hint": hint})
        for match in COORDINATE.finditer(text):
            dependency_found = True
            quote, coordinate = match.groups()
            value = coordinate.split(":", 2)[2]
            # Single-quoted Groovy strings do not interpolate properties.
            if quote == '"':
                value = PLACEHOLDER.sub(lambda m: properties.get(m.group(1) or m.group(2), m.group(0)), value)
            versions.append(value)
            evidence.append({"file": name, "line": text.count("\n", 0, match.start()) + 1, "kind": "minecraft_dependency", "value": value})
        if re.search(r"\bminecraft\s*\(\s*libs\.|\bminecraft\s+libs\.", text):
            issues.append("Version catalog Minecraft dependency requires manual review")
    if not dependency_found:
        issues.append("No supported direct com.mojang:minecraft dependency found; a property alone does not establish the build target")
    if not versions:
        issues.append("No supported Minecraft version declaration found")
    unresolved = [value for value in versions if not EXACT_VERSION.fullmatch(value) or "+" in value or value.lower().startswith("latest")]
    if unresolved:
        issues.append("Computed, ranged, or unresolved Minecraft version declaration")
    exact = sorted(set(value for value in versions if value not in unresolved))
    if len(exact) > 1:
        issues.append("Conflicting Minecraft version declarations: " + ", ".join(exact))
    return {
        "project_path": str(root), "configuration_files": files,
        "declared_minecraft_version": exact[0] if len(exact) == 1 and not issues else None,
        "version_candidates": exact, "evidence": evidence, "issues": issues,
        "mapping_hints": sorted(mapping_hints), "mapping_evidence": mapping_evidence, "loader_hints": sorted(loader_hints),
        "inspection": "static_declarations_only",
    }


def namespace_review(project, identity):
    """Conservative gates from static hints, never a namespace compatibility proof."""
    hints = project["mapping_hints"]
    reasons = []
    if len(hints) > 1:
        reasons.append("multiple_mapping_hints_require_review")
    if any(hint != "mojang" for hint in hints):
        reasons.append("mapping_transformation_not_supported")
    if identity.get("namespace", "unverified") not in ("unverified", "mojang"):
        reasons.append("source_namespace_not_supported")
    if identity.get("named_client_class_present") is False:
        reasons.append("named_client_source_not_established")
    return {
        "status": "needs_review" if reasons else "unverified",
        "blocking": bool(reasons), "reasons": reasons,
        "project_hints": hints, "evidence": project["mapping_evidence"],
        "source_namespace": identity.get("namespace", "unverified"),
        "named_client_class_present": identity.get("named_client_class_present"),
    }


def check_project(path, jar_identity):
    project = inspect_project(path)
    declared = project["declared_minecraft_version"]
    namespace = namespace_review(project, jar_identity)
    if declared is None:
        status = "needs_review"
    elif declared != jar_identity["minecraft_version"]:
        status = "version_mismatch"
    elif namespace["blocking"]:
        status = "needs_review"
    else:
        status = "declared_version_match"
    return {
        "schema_version": 1, "status": status, "project": project,
        "jar": {key: jar_identity[key] for key in ("minecraft_version", "sha256", "namespace", "provenance", "scope")},
        "namespace_review": namespace,
        "api_compatibility": "unverified",
        "review_required": True,
        "limitations": [
            "Gradle is not executed. Conditional configuration, plugins, command-line properties, user properties, and initialization scripts can override declarations.",
            "Mapping and loader hints are not resolved dependencies or proof of namespace compatibility.",
            "Java requirements and runtime behavior are not inferred from the project.",
        ],
    }
