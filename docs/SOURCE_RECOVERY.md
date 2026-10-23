# Source recovery and temporary files

CFR can produce readable files while failing to recover individual method bodies. Recovery applies a second decompiler only to the classes reported by CFR, preserving the primary output for diagnosis.

## Usage

```text
python scripts/mcsource.py prepare --jar /path/to/client.jar --project /path/to/mod --verify-official --repair
python scripts/mcsource.py repair --jar /path/to/client.jar --reference /path/to/kit/.local/references/version-hash
```

Recovery requires JDK 17 or newer and a JDK capable of reading the input bytecode. Normal preparation remains available without `--repair`; it reports CFR findings without downloading Vineflower. No recovery tool is downloaded when preparation has no findings.

Standalone repair accepts only a completed CFR reference under this kit's `.local/references/`. It compares the current JAR's SHA-256 with the original identity before modifying files. A reference with an existing recovery attempt requires manual review rather than an automatic retry. Other source directories are not accepted.

## Tool identity

- Version: Vineflower 1.12.0, regular JAR.
- Source: `https://github.com/Vineflower/vineflower/releases/download/1.12.0/vineflower-1.12.0.jar`
- SHA-256: `1dfcfe974395734fa467ce620661c7623d05ba83670de0529b1fbd63ff548b9d`

The checksum is pinned from the official release asset metadata. Both fresh downloads and cached binaries must match before execution. Downloads have a size limit and network timeout; bad or partial downloads are preserved and not executed or retried automatically. This does not authenticate arbitrary Minecraft input; use official JAR verification separately.

## Recovery behavior

1. Collect source files with known failure markers and class sections in CFR's summary. Unrecognized summary findings remain unresolved.
2. Back up targeted original sources under `diagnostics/vineflower/cfr-original/` with `.java.cfr` suffixes. The original `summary.txt` is retained.
3. Extract only matching outer classes and their `$` inner classes into a dedicated workspace. Reject unsafe paths, duplicate selected entries, missing outer classes, and oversized inputs.
4. Run Vineflower with two threads, a 2 GiB heap limit, the original JAR as an external classpath, and a five-minute process timeout.
5. Require a zero exit, no warning/error log messages, and every expected Java output. Check package/type names, nonempty content, and known failure markers before replacing any source.
6. Replace only the requested files. If a replacement fails, attempt to restore originals already changed. A rollback failure is explicitly recorded; backups remain available.
7. Record targets, original/output SHA-256 values, tool identity, times, and outcome in `REFERENCE.json`. Remove only the attempt's temporary workspace after successful recovery.

`fallback.status = recovered_unverified` means the expected outputs passed these structural checks. It does not prove semantic equivalence, compilability, or runtime correctness. If no known failure markers remain and all parsed CFR findings were covered, the reference returns to `generated_unverified`. The original summary may still contain its historical findings; use the recovery record to see which files were replaced. Otherwise the reference remains `needs_review` (exit 2).

Warnings or incomplete output reject the whole candidate set. Failed/interrupted attempts retain their workspace and log. If automatic recovery cannot start because of invalid input or JDK requirements, its diagnostic must be resolved; do not silently bypass it.

## Retained and temporary data

- Keep: repository, user JAR, reference identity, final sources, tool cache, original CFR backups, and decompiler logs.
- Remove automatically after success: only `diagnostics/vineflower/workspace/`, created by that attempt.
- Keep on failure: the workspace and any partial tool download, for inspection.

A cleanup failure leaves the workspace in place and is recorded; it does not trigger broad deletion. No command currently performs general cache cleanup. Do not instruct an agent to guess which repository files are unnecessary.
