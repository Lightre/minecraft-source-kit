# Development plan

## Initial baseline

- Agent-led setup without target-project writes.
- Local JAR inspection and SHA-256 recording.
- Pinned official CFR source build.
- Separate output directory with a machine-readable identity and failure report.
- Focused tests for metadata, hashing, and error detection.

## Next acceptance gates

- Detect CFR failures and add a pinned, verified per-class fallback.
- Resolve project namespace compatibility and record a reusable local project binding. Matching static version evidence is now stored when preparing with `--project`.
- Validate source/project mismatch handling with a real mod project.
- Compare representative API tasks with and without the kit.

## Explicitly deferred

Mapping conversion, automatic project edits, arbitrary Gradle evaluation, MCP, runtime bridges, a GUI, and claims of universal Minecraft support.

Ship a small tested workflow before expanding the support matrix.

## Baseline validation

On Windows with Python 3.13 and JDK 25, a fresh tool fetch/build and full Minecraft 26.2 client decompilation produced 7,055 Java files. Nine files were recorded as requiring review; the result was correctly marked `needs_review`. The cached tool was reused without a download or rebuild. Eleven unit tests passed locally.

This covers source preparation, not a complete modding workflow. Project binding, official provenance checks, mapping compatibility, fallback decompilation, and in-game validation remain separate acceptance gates. The baseline GitHub Actions matrix passed on Windows and Linux with Python 3.10 and 3.13.

## Official client verification

The `verify` command and optional `prepare --verify-official` gate compare a local client SHA-1 and size with Mojang metadata. The version metadata SHA-1 is also checked against the official manifest. A live check verified the local 26.2 client; offline fixtures cover mismatches, unavailable metadata, invalid schemas, restricted redirects, and setup blocking. This does not establish mappings or runtime compatibility.
