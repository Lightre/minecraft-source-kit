# Development plan

## Initial baseline

- Agent-led setup without target-project writes.
- Local JAR inspection and SHA-256 recording.
- Pinned official CFR source build.
- Separate output directory with a machine-readable identity and failure report.
- Focused tests for metadata, hashing, and error detection.

## Next acceptance gates

- Resolve project namespace compatibility beyond matching static version declarations and textual mapping hints.
- Validate source/project mismatch handling with a real mod project.
- Compare representative API tasks with and without the kit.
- Add preview-based, user-requested cache cleanup after the preparation workflow stabilizes; never remove active references or user inputs implicitly.

## Explicitly deferred

Mapping conversion, automatic project edits, arbitrary Gradle evaluation, MCP, runtime bridges, a GUI, and claims of universal Minecraft support.

Ship a small tested workflow before expanding the support matrix.

## Baseline validation

On Windows with Python 3.13 and JDK 25, a fresh tool fetch/build and full Minecraft 26.2 client decompilation produced 7,055 Java files. Nine files were recorded as requiring review; the result was correctly marked `needs_review`. The cached tool was reused without a download or rebuild. Eleven unit tests passed locally.

This covers source preparation, not a complete modding workflow. Project binding, official provenance checks, mapping compatibility, fallback decompilation, and in-game validation remain separate acceptance gates. The baseline GitHub Actions matrix passed on Windows and Linux with Python 3.10 and 3.13.

## Official client verification

The `verify` command and optional `prepare --verify-official` gate compare a local client SHA-1 and size with Mojang metadata. The version metadata SHA-1 is also checked against the official manifest. A live check verified the local 26.2 client; offline fixtures cover mismatches, unavailable metadata, invalid schemas, restricted redirects, and setup blocking. This does not establish mappings or runtime compatibility.

## Per-class recovery

Optional preparation recovery and a standalone repair command use pinned Vineflower 1.12.0 with its published SHA-256. Originals and logs are retained, all candidates are validated before replacement, and temporary workspace removal is limited to successful attempts. A repaired reference remains reconstructed, unverified source. General cache cleanup remains deferred; the repository itself stays installed.

Validation on Windows/JDK 25 recovered all nine reported classes from the local 26.2 client. A separate fixture built from the original CFR backups also recovered all nine with recorded input/original/output hashes and successful workspace cleanup. Unit tests cover conservative rejection, retained diagnostics, rollback, input identity, and tool integrity. The full preparation-with-recovery route is covered with mocked decompiler outputs; it was not rerun against the entire client.

## Local project bindings

`bind` stores project configuration hashes, reference identity hash, and an active Java source fingerprint under ignored `.local/bindings/`. `resolve` rechecks these before returning a reference and copyable agent instruction. Missing or stale snapshots do not produce a usable instruction. The target mod project is never written. Namespace/API compatibility remains unverified, and bindings do not automatically install agent instructions.

A local smoke check paired the full 7,055-file 26.2 source reference with a synthetic Gradle project. Binding creation and resolution succeeded; changing its declared version produced `stale`. Target files remained unchanged by both commands. This is not real-mod validation or namespace compatibility testing.
