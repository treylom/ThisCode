#!/usr/bin/env python3
"""Classify push diff scope for pre-push smoke selection.

docs-only -> subset gate
code      -> full gate
none      -> no gate
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

DOC_NAMES = {
    "README",
    "README.md",
    "README.ko.md",
    "CHANGELOG",
    "CHANGELOG.md",
    "LICENSE",
    "LICENSE.md",
    "NOTICE",
    "NOTICE.md",
}
DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".typ", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
DOC_DIRS = {"docs", "assets"}


def changed_paths_from_git(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_docs_only_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return True
    name = normalized.rsplit("/", 1)[-1]
    if name in DOC_NAMES:
        return True
    first = normalized.split("/", 1)[0]
    suffix = Path(name).suffix.lower()
    return first in DOC_DIRS and suffix in DOC_SUFFIXES


def classify(paths: list[str]) -> dict:
    clean = [p for p in paths if p]
    if not clean:
        classification = "none"
    elif all(is_docs_only_path(p) for p in clean):
        classification = "docs-only"
    else:
        classification = "code"
    gate = {"none": "none", "docs-only": "subset", "code": "full"}[classification]
    return {"classification": classification, "required_gate": gate, "paths": clean}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", nargs="*", help="Explicit path list. If omitted, use git diff --name-only HEAD.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    paths = args.paths if args.paths is not None else changed_paths_from_git(root)
    result = classify(paths)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['classification']}\t{result['required_gate']}")
        for path in result["paths"]:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
