"""
Skill 发现规则：约定 skills/（primary）+ fallback 全 repo；锚点 skill.yaml / SKILL.md；边界：嵌套、重复 id、超大目录。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterator

# 扫描时跳过的目录（不进入、不计入 file set）
SKIP_DIRS = frozenset({".git", "node_modules", "dist", "build", ".venv", "__pycache__", "target"})

# 单 skill 上限：超过打 SKILL_TOO_LARGE finding
MAX_SKILL_FILES = 2000
MAX_SKILL_BYTES = 50 * 1024 * 1024  # 50MB

# 全 repo anchors 上限：超过打 REPO_TOO_MANY_SKILLS
MAX_ANCHORS = 500

# 约定目录：默认只扫 skills/**
SKILLS_DIR = "skills"

ANCHOR_NAMES = ("skill.yaml", "skill.yml", "SKILL.md")


def _should_skip_dir(part: str) -> bool:
    return part in SKIP_DIRS or part.startswith(".")


def find_skill_anchors(
    repo_root: Path,
    base: str = SKILLS_DIR,
) -> list[tuple[Path, str, str, bool]]:
    """
    在 repo_root/base 下查找锚点；同一目录 skill.yaml 优先于 SKILL.md。
    base="skills/" 为 primary；base="." 为 fallback 全 repo。
    返回 [(skill_root, anchor_path_rel, anchor_type, had_dup_anchor), ...]
    anchor_type: "skill_yaml" | "skill_md"
    had_dup_anchor: 同目录曾同时存在两种锚点（保留 skill.yaml，打 SKILL_DUP_ANCHOR 用）
    """
    repo_root = repo_root.resolve()
    search_root = (repo_root / base) if base and base != "." else repo_root
    if base and base != "." and (not search_root.is_dir() or not search_root.exists()):
        return []

    by_dir: dict[Path, list[str]] = {}
    for path in search_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(repo_root).parts
        except ValueError:
            continue
        if any(_should_skip_dir(p) for p in rel_parts[:-1]):
            continue
        name = path.name
        if name not in ANCHOR_NAMES:
            continue
        parent = path.parent
        by_dir.setdefault(parent, []).append(name)

    result: list[tuple[Path, str, str, bool]] = []
    for parent, names in sorted(by_dir.items(), key=lambda x: str(x[0])):
        if "skill.yaml" in names:
            anchor_name = "skill.yaml"
            anchor_type = "skill_yaml"
        elif "skill.yml" in names:
            anchor_name = "skill.yml"
            anchor_type = "skill_yaml"
        else:
            anchor_name = "SKILL.md"
            anchor_type = "skill_md"
        had_dup = (anchor_type == "skill_yaml" and "SKILL.md" in names) or (
            anchor_type == "skill_md" and any(n.startswith("skill.y") for n in names)
        )
        anchor_path = parent / anchor_name
        rel = str(anchor_path.relative_to(repo_root))
        result.append((parent, rel, anchor_type, had_dup))
    return result


def discover_skills_with_fallback(
    repo_root: Path,
) -> tuple[list[tuple[Path, str, str, bool]], bool]:
    """
    Primary: 只扫 skills/；若无任何 skill 则 fallback 全 repo 扫。
    返回 (anchors, used_fallback)。
    """
    anchors = find_skill_anchors(repo_root, base=SKILLS_DIR)
    if anchors:
        return (anchors, False)
    anchors = find_skill_anchors(repo_root, base=".")
    return (anchors, True)


def get_skill_file_set(skill_root: Path, repo_root: Path | None = None) -> tuple[list[Path], int, int]:
    """
    返回 skill_root 下归属文件列表（递归），排除 SKIP_DIRS。
    返回 (paths, total_file_count, total_bytes)。
    """
    skill_root = skill_root.resolve()
    base = repo_root.resolve() if repo_root else skill_root
    paths: list[Path] = []
    total_bytes = 0
    for p in skill_root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(skill_root).parts
        if any(_should_skip_dir(part) for part in rel_parts[:-1]):
            continue
        if _should_skip_dir(rel_parts[-1]):
            continue
        paths.append(p)
        try:
            total_bytes += p.stat().st_size
        except OSError:
            pass
    return (paths, len(paths), total_bytes)


def is_nested(skill_root: Path, all_roots: list[Path]) -> bool:
    """当前 skill_root 是否被其他已发现的 skill_root 包含（即嵌套在内层）。"""
    try:
        skill_root = skill_root.resolve()
        for other in all_roots:
            if other == skill_root:
                continue
            try:
                skill_root.relative_to(other.resolve())
                return True  # skill_root 在 other 之下
            except ValueError:
                pass
    except Exception:
        pass
    return False


def skill_fingerprint(file_paths: list[Path], repo_root: Path) -> str:
    """
    可复现 hash：对归属文件集，路径排序后逐文件 sha256(path + "\\0" + sha256(content)) 再合并。
    用于 registry 去重/缓存与审计。
    """
    parts: list[bytes] = []
    for p in sorted(file_paths, key=lambda x: str(x)):
        try:
            rel = p.relative_to(repo_root)
            path_str = rel.as_posix()
            content = p.read_bytes()
            content_sha = hashlib.sha256(content).hexdigest()
            parts.append(hashlib.sha256((path_str + "\0" + content_sha).encode()).digest())
        except (OSError, ValueError):
            pass
    return hashlib.sha256(b"".join(parts)).hexdigest()
