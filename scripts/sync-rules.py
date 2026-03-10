#!/usr/bin/env python3
"""Sync rules and schema between skillscan package and repo root for dev consistency."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PKG_RULES = REPO_ROOT / "skillscan" / "rules"
PKG_SCHEMA = REPO_ROOT / "skillscan" / "schema"
ROOT_RULES = REPO_ROOT / "rules"
ROOT_SCHEMA = REPO_ROOT / "schema"


def sync_pkg_to_root() -> None:
    """Copy skillscan/rules and skillscan/schema to repo root (source of truth: package)."""
    for src, dst in [(PKG_RULES, ROOT_RULES), (PKG_SCHEMA, ROOT_SCHEMA)]:
        if not src.is_dir():
            print(f"Skip: {src} not found", file=sys.stderr)
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)
                print(f"Copied {f.name} -> {dst}")


def sync_root_to_pkg() -> None:
    """Copy repo root rules/schema to skillscan package (source of truth: root)."""
    for src, dst in [(ROOT_RULES, PKG_RULES), (ROOT_SCHEMA, PKG_SCHEMA)]:
        if not src.is_dir():
            print(f"Skip: {src} not found", file=sys.stderr)
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)
                print(f"Copied {f.name} -> {dst}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("pkg-to-root", "root-to-pkg"):
        print("Usage: python scripts/sync-rules.py pkg-to-root | root-to-pkg", file=sys.stderr)
        print("  pkg-to-root: copy skillscan/rules,schema -> rules,schema (before release)", file=sys.stderr)
        print("  root-to-pkg: copy rules,schema -> skillscan/ (after editing root)", file=sys.stderr)
        sys.exit(1)
    if sys.argv[1] == "pkg-to-root":
        sync_pkg_to_root()
    else:
        sync_root_to_pkg()


if __name__ == "__main__":
    main()
