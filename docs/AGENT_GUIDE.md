# Agent setup and source-use guide

## Setup

1. Identify the target mod project and the user-supplied Minecraft JAR. Ask only for missing paths. Read the project's own instructions first.
2. Inspect only build configuration needed to identify the exact Minecraft version, loader, Java requirements, and mapping namespace. Do not infer values you cannot resolve.
3. Run `check-project --jar <jar> --project <mod directory>` from the kit root. On `version_mismatch`, stop and request the correct input. On `needs_review`, inspect the evidence and resolve the actual target manually; never treat unknown as compatible. On `declared_version_match`, still check the effective configuration and namespace: this is a bounded declaration check, not Gradle evaluation. Review project instructions and any known property overrides. Use `inspect` for standalone JAR metadata and bytecode. For a claimed official client JAR, use `verify --jar <jar>` for standalone provenance diagnostics, or enforce verification during preparation as described below. A successful project check alone does not verify provenance.
4. Check the namespace explicitly. Old obfuscated JARs need matching mappings; this first version cannot remap them. Do not treat raw obfuscated output as matching a named project. Do not silently substitute another Minecraft version.
5. Run `prepare --jar <jar> --project <mod directory> --verify-official --repair` only after the effective target and namespace have been reviewed. The project option adds a version gate and stores its evidence. Official verification requires matching client SHA-1 and size from Mojang metadata. If verification is unavailable, report the reason and stop; do not silently drop the flag. An explicitly requested offline or modified-JAR workflow may use standalone preparation without the flag, with provenance left unverified. A known fingerprint mismatch must be resolved or explicitly identified as a modified input before proceeding. If the static parser cannot handle a project, explain the limitation and verify the actual target with the agent before using standalone `prepare`; do not bypass an unresolved mismatch. It builds the pinned CFR tool and creates a new output directory without modifying the target project.
6. Inspect `REFERENCE.json`, the CFR summary, and a few relevant source files. Report incomplete methods. Verify affected behavior against `javap` or a second official decompiler before relying on it. With `--repair`, reported CFR classes receive one conservative Vineflower attempt. Inspect the `fallback` record; `recovered_unverified` is not a correctness guarantee. If unresolved, stop relying on affected methods. For an existing kit reference use `repair --jar <same jar> --reference <directory>`; it checks the original SHA-256. Do not delete attempt records or retry automatically.
7. Keep diagnostics and original-source backups. Successful recovery removes only its temporary class/output workspace. On failure, preserve it for diagnosis. Do not delete the repository, input JAR, tool cache, or source reference as setup cleanup.
8. Report the reference's absolute location, version, namespace status, limitations, and setup result. Stop setup here. For future sessions, offer a short source-location instruction that the user can add to their project; do not write it automatically.

## Coding with the reference

- Follow the mod project's instructions. Preparing a reference does not authorize unrelated project changes.
- Confirm the reference still matches the project's current target before using it.
- Search exact symbols, then relevant packages, superclasses, interfaces, and call sites. Read narrowly; do not ingest the whole source tree.
- Verify package, declaring class, visibility, static/instance status, parameter types, return type, overloads, and generic constraints before introducing an API call.
- Never invent a replacement name when a symbol is absent. Check mappings, inheritance, inner classes, client/server scope, and the resolved dependency version.
- Minecraft sources do not establish loader or third-party library APIs. Use their exact dependency versions and sources or official version-matched documentation.
- For behavior, inspect bodies and relevant callers, logical side, threading, and lifecycle. Decompiled control-flow failures and synthetic artifacts are not authoritative behavior.
- For Mixins, verify the actual target, descriptor, overload, injection location, and remapping configuration. Compilation alone does not establish runtime injection success.
- Keep references read-only and outside build source sets. Never copy the source tree into mod source folders or publish it.
- Make only the requested code changes. Run existing targeted compilation/tests and appropriate runtime checks. Report what ran and what remains unverified.

## Future-session instruction

The agent may propose this text, replacing placeholders with verified values:

> Minecraft reference: <absolute reference directory>. Read its REFERENCE.json before use. Confirm exact target and namespace compatibility, verify Minecraft symbols from the reference before coding, and report unresolved decompiler failures. Do not modify the reference or include it in the build.
