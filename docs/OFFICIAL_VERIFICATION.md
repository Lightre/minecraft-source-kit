# Official client verification

The kit can check whether a user-supplied JAR matches the client artifact recorded in Mojang's version metadata. It does not download the Minecraft JAR or execute it.

```text
python scripts/mcsource.py verify --jar /path/to/client.jar
python scripts/mcsource.py prepare --jar /path/to/client.jar --project /path/to/mod --verify-official
```

## What is checked

1. Offline inspection calculates SHA-256 and SHA-1 and reads the JAR's version ID.
2. The verifier reads the HTTPS version manifest at `https://piston-meta.mojang.com/mc/game/version_manifest_v2.json` and selects that exact ID.
3. It reads the selected version metadata and checks its SHA-1 against the manifest entry.
4. It compares the local JAR's SHA-1 and byte size with `downloads.client`.

SHA-1 is used because that is the fingerprint supplied by Mojang metadata; the local identity also retains SHA-256. This is an official metadata fingerprint comparison, not a digital-signature verification or a proof of namespace/API compatibility.

Only Mojang metadata HTTPS hosts are requested (`piston-meta.mojang.com` and legacy `launchermeta.mojang.com`). Redirects cannot leave those hosts or downgrade to HTTP. Responses are limited to 4 MiB and network operations have a 10-second timeout. There is no retry loop, disk metadata cache, or automatic fallback to an unverified result.

## Results

- `verified` (exit 0): both client SHA-1 and size match. The report includes actual and expected fingerprints, metadata URLs, metadata SHA-1, and check time.
- `mismatch` (exit 1): valid official metadata was retrieved, but the input fingerprint differs. This may be a modified JAR, another artifact such as a server, or a mislabeled input; the tool does not guess the cause.
- `unverified` (exit 2): verification could not be established. Reasons distinguish unavailable metadata, an unlisted version ID, and invalid/inconsistent metadata. An offline result is not a mismatch and never counts as verified.

Invalid local input produces an error diagnostic and exit 1 before network verification.

## Preparation boundary

`prepare --verify-official` requires `verified` and saves the report inside `REFERENCE.json` as `official_verification`, with provenance `verified_official_client`. A mismatch or inconclusive result stops preparation before tool downloads or reference creation. Existing references are not overwritten or retroactively updated.

`inspect`, `check-project`, and plain `prepare` retain their offline provenance behavior. Plain preparation may still need network access to fetch CFR on first use. Omitting `--verify-official` must be a deliberate offline or modified-input workflow; the agent guide recommends requiring it for official client inputs.

Verification covers the exact input bytes inspected at that time. Reverify changed inputs. Client verification does not authenticate server JARs, resolve mappings, remove obfuscation, or establish that every decompiled method is correct. Older official clients can verify successfully while remaining unsupported by the current named-client preparation flow.

## Tests

Unit tests mock metadata transport and never depend on Mojang availability. A separate local smoke check verified the user-supplied Minecraft 26.2 client against the live official service. Live availability is not required in CI.
