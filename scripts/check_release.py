"""Validate curated metadata for a stable kit release without network access."""
import argparse
import ast
from datetime import date
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check_release(root, tag):
    if not re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", tag):
        raise ValueError("Release tag must use stable vMAJOR.MINOR.PATCH format")
    root = Path(root)
    tree = ast.parse((root / "scripts/mcsource.py").read_text(encoding="utf-8"))
    versions = [node.value.value for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    if versions != [tag[1:]]:
        raise ValueError("Release tag does not match the CLI VERSION constant")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    entries = re.findall(r"^## " + re.escape(tag) + r" - (.+)$", changelog, re.MULTILINE)
    if len(entries) != 1 or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", entries[0]):
        raise ValueError("Changelog must contain exactly one dated heading for this release")
    date.fromisoformat(entries[0])
    notes = root / "docs/releases" / (tag + ".md")
    lines = notes.read_text(encoding="utf-8").strip().splitlines()
    if not lines or lines[0] != "# " + tag or not any(line.strip() for line in lines[1:]):
        raise ValueError("Release notes require the matching title and a nonempty body")
    return notes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Stable release tag to validate")
    args = parser.parse_args()
    try:
        notes = check_release(ROOT, args.tag)
    except (OSError, ValueError, SyntaxError) as error:
        parser.exit(1, f"Release validation failed: {error}\n")
    print(f"Release metadata validated: {args.tag} ({notes.relative_to(ROOT).as_posix()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
