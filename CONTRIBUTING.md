# Contributing

Keep this kit small and focused on version-matched source evidence for coding agents.

- Use English throughout repository content.
- Follow AGENTS.md and preserve the no-target-project-writes setup boundary.
- Use the Python standard library and existing commands before adding infrastructure.
- Explain what a change proves and what remains unverified. Do not equate source generation with API compatibility or runtime correctness.
- Add focused tests for meaningful behavior, and run `python -m unittest discover -s tests -v`.
- Keep Minecraft JARs, generated sources, downloaded tools, credentials, and machine-specific paths out of commits and issue attachments.
- Document tested version, mapping, JDK, and operating system when proposing a new supported workflow.
- Submit original contributions under GPL-3.0-only, the repository license. Preserve existing copyright and license notices. Identify any third-party material and its license before proposing its inclusion; do not assume the kit license covers it.

## Pull requests

Use Conventional Commit formatting for commit messages and PR titles (`feat:`, `fix:`, `docs:`, `test:`, or `chore:` as appropriate). Prefer squash merges with the PR title as the final commit subject.

Coding agents must not monitor external CI or other remote waits in loops. After pushing, report pending checks and yield; the user will report completion. An explicit user request for a status check permits a bounded check, not an ongoing monitor.

The user performs merges manually. Agents prepare and push PRs, then yield. After the user confirms a merge, update local `main`; do not merge through tools without an explicit request.
