# Development plan

## Initial baseline

- Agent-led setup without target-project writes.
- Local JAR inspection and SHA-256 recording.
- Pinned official CFR source build.
- Separate output directory with a machine-readable identity and failure report.
- Focused tests for metadata, hashing, and error detection.

## Next acceptance gates

- Authenticate supported official JARs against Mojang metadata.
- Detect CFR failures and add a pinned, verified per-class fallback.
- Record project target and namespace in a separate local binding file.
- Validate source/project mismatch handling with a real mod project.
- Compare representative API tasks with and without the kit.

## Explicitly deferred

Mapping conversion, automatic project edits, arbitrary Gradle evaluation, MCP, runtime bridges, a GUI, and claims of universal Minecraft support.

Ship a small tested workflow before expanding the support matrix.

## Baseline validation

On Windows with Python 3.13 and JDK 25, a fresh tool fetch/build and full Minecraft 26.2 client decompilation produced 7,055 Java files. Nine files were recorded as requiring review; the result was correctly marked `needs_review`. The cached tool was reused without a download or rebuild. Eleven unit tests passed locally.

This covers source preparation, not a complete modding workflow. Project binding, official provenance checks, mapping compatibility, fallback decompilation, and in-game validation remain separate acceptance gates. CI has been configured but has not run on GitHub yet.
