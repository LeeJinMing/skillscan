"""
Parse skill directory: SKILL.md frontmatter, code fences (shell), and text from globs.
MVP: deterministic extraction only; no LLM.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

# YAML frontmatter between --- ... ---
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
# Code fence: ```bash, ```sh, ```shell, ``` (capture content)
CODE_FENCE_RE = re.compile(
    r"^```(?:bash|sh|shell)?\s*\n(.*?)```",
    re.DOTALL | re.MULTILINE,
)


def _parse_yaml_like(text: str) -> dict[str, str]:
    """Minimal key: value parse (MVP, no PyYAML)."""
    out: dict[str, str] = {}
    for line in text.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip().strip('"\'')
    return out


def read_skill_frontmatter(skill_root: Path) -> dict | None:
    """Extract YAML frontmatter from SKILL.md if present."""
    skill_md = skill_root / "SKILL.md"
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    return _parse_yaml_like(m.group(1)) or None


def read_skill_yaml(skill_root: Path) -> dict | None:
    """Read skill.yaml (or skill.yml) if present; id, title, category, version, entrypoint."""
    for name in ("skill.yaml", "skill.yml"):
        p = skill_root / name
        if p.is_file():
            try:
                return _parse_yaml_like(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return None


def read_skill_metadata(skill_root: Path, repo_slug: str = "") -> dict[str, str | bool]:
    """
    优先 skill.yaml，否则 SKILL.md frontmatter；否则路径派生。
    返回 id, title, category, declared_version（统一 key），以及 invalid_yaml（缺 id/category/version 时 True）。
    """
    yaml = read_skill_yaml(skill_root)
    if yaml:
        sid = (yaml.get("id") or "").strip() or f"{repo_slug}:{skill_root.name}".strip(":") or skill_root.name
        title = (yaml.get("title") or "").strip() or skill_root.name
        category = (yaml.get("category") or "").strip() or "unknown"
        ver = (yaml.get("version") or "").strip() or "unknown"
        invalid_yaml = not (
            (yaml.get("id") or "").strip()
            and (yaml.get("category") or "").strip()
            and (yaml.get("version") or "").strip()
        )
        return {
            "id": sid,
            "title": title,
            "category": category,
            "declared_version": ver,
            "invalid_yaml": invalid_yaml,
        }
    front = read_skill_frontmatter(skill_root)
    if front:
        return {
            "id": (front.get("skill_id") or "").strip() or f"{repo_slug}:{skill_root.name}".strip(":") or skill_root.name,
            "title": (front.get("title") or "").strip() or skill_root.name,
            "category": (front.get("category") or "").strip() or "unknown",
            "declared_version": (front.get("version") or "").strip() or "unknown",
            "invalid_yaml": False,
        }
    slug = f"{repo_slug}:{skill_root.name}".strip(":") or skill_root.name
    return {
        "id": slug,
        "title": skill_root.name,
        "category": "unknown",
        "declared_version": "unknown",
        "invalid_yaml": False,
    }


def iter_shell_snippets(skill_root: Path) -> Iterator[tuple[str, int, str]]:
    """
    Yield (file_path_rel, line_number, line_or_block) for shell-relevant content.
    - SKILL.md and *.md: code fence blocks (bash/sh/shell) + full lines for grep.
    - *.sh, *.ps1, *.py: full lines.
    """
    for path in skill_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_root)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        suf = path.suffix.lower()
        if path.name.upper() == "SKILL.MD" or suf == ".md":
            # Code fences
            for block in CODE_FENCE_RE.finditer(text):
                snippet = block.group(1).strip()
                if not snippet:
                    continue
                # Approximate line: first line of block in file
                line_no = text[: block.start()].count("\n") + 1
                yield str(rel), line_no, snippet
            # Also yield each line for pattern matching (e.g. inline commands)
            for i, line in enumerate(text.splitlines(), start=1):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("```"):
                    yield str(rel), i, line
        elif suf in (".sh", ".ps1", ".py"):
            for i, line in enumerate(text.splitlines(), start=1):
                yield str(rel), i, line.rstrip()


def iter_files_matching(skill_root: Path, globs: list[str]) -> Iterator[Path]:
    """Yield files under skill_root matching any of the globs (e.g. *.md, *.sh)."""
    for g in globs:
        for p in skill_root.rglob(g):
            if p.is_file():
                yield p
