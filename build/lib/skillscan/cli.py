"""
skillscan CLI: team-friendly scanner for local folders, zip files, and GitHub repos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from . import __version__
from .discovery import (
    MAX_ANCHORS,
    MAX_SKILL_BYTES,
    MAX_SKILL_FILES,
    discover_skills_with_fallback,
    get_skill_file_set,
    is_nested,
    skill_fingerprint,
)
from .engine import (
    VERDICT_ALLOWED,
    VERDICT_BLOCKED,
    VERDICT_NEEDS_APPROVAL,
    aggregate_verdict,
    build_attestation,
    build_report,
    build_report_v1,
    build_report_v1_from_skills,
    compute_verdict,
    load_ruleset,
    risk_summary_to_findings,
    run_rules,
)
from .parser import iter_shell_snippets, read_skill_frontmatter, read_skill_metadata
from .render import render_report_html, render_report_markdown

# rule_id → policy signal（与 policy requires_approval_signals 对齐）
RULE_ID_TO_SIGNAL = {
    "block-offsec-ad-playbook": "offsec_hit",
    "approval-sudo": "uses_sudo",
    "approval-service": "service_control",
    "approval-write-config": "writes_system_paths",
    "approval-permission": "chmod_chown",
    "approval-network": "network_download_exec",
}


def _risk_summary_to_signals(risk_summary: list[dict[str, Any]]) -> list[str]:
    """从 risk_summary 推导 signals 列表（可解释、可审计）。"""
    signals: set[str] = set()
    for r in risk_summary:
        rid = r.get("rule_id", "")
        if rid in RULE_ID_TO_SIGNAL:
            signals.add(RULE_ID_TO_SIGNAL[rid])
    return sorted(signals)


def input_hash_from_path(skill_root: Path) -> str:
    """Stable hash of relevant file contents (SKILL.md + *.sh, *.ps1, *.py, *.md)."""
    return _content_hasher(skill_root).hexdigest()[:32]


def input_hash_sha256_full(skill_root: Path) -> str:
    """Full SHA256 for input_fingerprint.sha256 in v1 report."""
    return _content_hasher(skill_root).hexdigest()


def _content_hasher(skill_root: Path) -> hashlib._Hash:
    h = hashlib.sha256()
    for p in sorted(skill_root.rglob("*")):
        if not p.is_file():
            continue
        suf = p.suffix.lower()
        if p.name.upper() == "SKILL.MD" or suf in (".md", ".sh", ".ps1", ".py"):
            try:
                h.update(p.read_bytes())
            except OSError:
                pass
    return h


def scan_dir(
    skill_root: Path,
    rules_path: Path,
    *,
    source_repo: str | None = None,
    source_ref: str | None = None,
    source_commit_sha: str | None = None,
    source_default_branch: str | None = None,
    skill_path_rel: str | None = None,
) -> tuple[dict, dict, dict[str, Any]]:
    from datetime import datetime, timezone

    t0 = datetime.now(timezone.utc)
    front = read_skill_frontmatter(skill_root)
    skill_id = (front and front.get("skill_id")) or skill_root.name
    skill_version = (front and front.get("version")) or "unknown"
    ecosystem = (front and front.get("ecosystem")) or "clawdbot"
    skill_author = (front and front.get("author")) or None
    skill_title = (front and front.get("title")) or None

    snippets = list(iter_shell_snippets(skill_root))
    ruleset = load_ruleset(rules_path)
    risk_summary = run_rules(ruleset, snippets)
    inp_hash = input_hash_from_path(skill_root)
    inp_hash_full = input_hash_sha256_full(skill_root)
    ruleset_version = ruleset.get("ruleset_version", "unknown")
    t1 = datetime.now(timezone.utc)
    duration_ms = int((t1 - t0).total_seconds() * 1000)
    started_at = t0.isoformat()
    finished_at = t1.isoformat()

    report = build_report(
        skill_id=skill_id,
        skill_version=skill_version,
        ecosystem=ecosystem,
        input_type="directory",
        input_hash=inp_hash,
        ruleset_version=ruleset_version,
        risk_summary=risk_summary,
        ruleset=ruleset,
        commit_sha=source_commit_sha,
    )
    attestation = build_attestation(
        ruleset_version=ruleset_version,
        input_hash=inp_hash,
        commit_sha=source_commit_sha,
    )
    report_v1 = build_report_v1(
        skill_id=skill_id,
        skill_version=skill_version,
        ecosystem=ecosystem,
        ruleset_version=ruleset_version,
        risk_summary=risk_summary,
        ruleset=ruleset,
        input_hash_sha256=inp_hash_full,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        source_provider="github" if source_repo else "local",
        source_repo=source_repo,
        source_ref=source_ref,
        source_commit_sha=source_commit_sha,
        source_default_branch=source_default_branch,
        skill_path=skill_path_rel,
        skill_author=skill_author,
        skill_title=skill_title,
    )
    return report, attestation, report_v1


def scan_repo_multi(
    repo_root: Path,
    rules_path: Path,
    *,
    source_repo: str | None = None,
    source_ref: str | None = None,
    source_commit_sha: str | None = None,
    source_default_branch: str | None = None,
) -> tuple[dict, dict, dict[str, Any]]:
    """多 skill repo：约定 skills/ primary，fallback 全 repo → 逐 skill 扫描 → 聚合 verdict → v1 report。"""
    from datetime import datetime, timezone

    t0 = datetime.now(timezone.utc)
    repo_root = repo_root.resolve()
    anchors, used_fallback = discover_skills_with_fallback(repo_root)
    ruleset = load_ruleset(rules_path)
    ruleset_version = ruleset.get("ruleset_version", "unknown")
    repo_slug = source_repo or repo_root.name
    repo_findings: list[dict[str, Any]] = []

    if not anchors:
        return scan_dir(
            repo_root,
            rules_path,
            source_repo=source_repo,
            source_ref=source_ref,
            source_commit_sha=source_commit_sha,
            source_default_branch=source_default_branch,
        )

    if used_fallback:
        repo_findings.append({
            "id": "SKILL_OUTSIDE_SKILLS_DIR",
            "rule_id": "skill-outside-skills-dir",
            "severity": "medium",
            "title": "Skills found outside skills/ directory (repo not following convention)",
            "evidence": [{"file": "", "line_start": 0, "line_end": 0, "match": "Move anchors under skills/"}],
            "recommendation": "Place all skills under skills/** for governance and discovery.",
            "signal": "",
            "supports": "approval_signal",
        })
    if len(anchors) > MAX_ANCHORS:
        repo_findings.append({
            "id": "REPO_TOO_MANY_SKILLS",
            "rule_id": "repo-too-many-skills",
            "severity": "high",
            "title": f"Repo has more than {MAX_ANCHORS} skills",
            "evidence": [{"file": "", "line_start": 0, "line_end": 0, "match": f"anchors={len(anchors)}"}],
            "recommendation": f"Split repo or reduce to <{MAX_ANCHORS} skills.",
            "signal": "",
            "supports": "approval_signal",
        })
        anchors = anchors[:MAX_ANCHORS]

    skill_roots = [a[0] for a in anchors]
    skills_data: list[dict[str, Any]] = []
    verdicts: list[str] = []
    all_fingerprints: list[str] = []

    for (skill_root, anchor_rel, anchor_type, had_dup_anchor) in anchors:
        paths, count, total_bytes = get_skill_file_set(skill_root, repo_root)
        root_rel = str(skill_root.relative_to(repo_root)) if skill_root != repo_root else "."
        metadata = read_skill_metadata(skill_root, repo_slug)
        snippets = list(iter_shell_snippets(skill_root))
        risk_summary = run_rules(ruleset, snippets)
        verdict = compute_verdict(risk_summary)
        _v1_status = {"Blocked": VERDICT_BLOCKED, "NeedsApproval": VERDICT_NEEDS_APPROVAL, "Allowed": VERDICT_ALLOWED}
        vstatus = _v1_status.get(verdict, verdict.lower())
        verdicts.append(vstatus)
        findings = risk_summary_to_findings(risk_summary, ruleset)

        if metadata.get("invalid_yaml"):
            findings.append({
                "id": "SKILL_YAML_INVALID",
                "rule_id": "skill-yaml-invalid",
                "severity": "high",
                "title": "skill.yaml missing required fields (id, category, version)",
                "evidence": [{"file": anchor_rel, "line_start": 0, "line_end": 0, "match": "id/category/version"}],
                "recommendation": "Add id, category, version to skill.yaml",
                "signal": "",
                "supports": "approval_signal",
            })
            if vstatus == VERDICT_ALLOWED:
                vstatus = VERDICT_NEEDS_APPROVAL
            verdicts[-1] = vstatus
        if had_dup_anchor:
            findings.append({
                "id": "SKILL_DUP_ANCHOR",
                "rule_id": "skill-dup-anchor",
                "severity": "info",
                "title": "Same directory has both skill.yaml and SKILL.md (skill.yaml used)",
                "evidence": [{"file": anchor_rel, "line_start": 0, "line_end": 0, "match": root_rel}],
                "signal": "",
                "supports": "info",
            })
        if count > MAX_SKILL_FILES or total_bytes > MAX_SKILL_BYTES:
            findings.append({
                "id": "SKILL_TOO_LARGE",
                "rule_id": "skill-too-large",
                "severity": "high",
                "title": "Skill file set exceeds limit",
                "evidence": [{"file": anchor_rel, "line_start": 0, "line_end": 0, "match": f"files={count}, bytes={total_bytes}"}],
                "recommendation": f"Reduce to <{MAX_SKILL_FILES} files and <{MAX_SKILL_BYTES // (1024*1024)}MB",
                "signal": "",
                "supports": "approval_signal",
            })
            if vstatus == VERDICT_ALLOWED:
                verdicts[-1] = VERDICT_NEEDS_APPROVAL
                vstatus = VERDICT_NEEDS_APPROVAL
        if is_nested(skill_root, skill_roots):
            findings.append({
                "id": "SKILL_NESTED_DETECTED",
                "rule_id": "skill-nested-detected",
                "severity": "medium",
                "title": "Nested skill detected (governance risk)",
                "evidence": [{"file": anchor_rel, "line_start": 0, "line_end": 0, "match": f"root={root_rel}"}],
                "recommendation": "Flatten structure or document nested scope",
                "signal": "",
                "supports": "approval_signal",
            })
            if vstatus == VERDICT_ALLOWED:
                verdicts[-1] = VERDICT_NEEDS_APPROVAL
                vstatus = VERDICT_NEEDS_APPROVAL

        fp = skill_fingerprint(paths, repo_root)
        all_fingerprints.append(fp)
        signals = _risk_summary_to_signals(risk_summary)
        declared_category = (metadata.get("category") or "unknown").strip() or "unknown"
        effective_category = "offsec" if "offsec_hit" in signals else declared_category
        skills_data.append({
            "path": anchor_rel,
            "root": root_rel,
            "anchor_type": anchor_type,
            "id": metadata["id"],
            "title": metadata["title"],
            "category": effective_category,
            "declared_category": declared_category,
            "effective_category": effective_category,
            "signals": signals,
            "declared_version": metadata["declared_version"],
            "fingerprint": fp,
            "findings": findings,
            "verdict": vstatus,
        })

    # 同一次扫描内重复 id ⇒ SKILL_ID_DUPLICATE（blocked）
    from collections import Counter
    id_counts = Counter(s["id"] for s in skills_data)
    for s in skills_data:
        if id_counts.get(s["id"], 0) > 1:
            s["findings"].append({
                "id": "SKILL_ID_DUPLICATE",
                "rule_id": "skill-id-duplicate",
                "severity": "critical",
                "title": "Duplicate skill id (cannot uniquely identify for approval/registry)",
                "evidence": [{"file": s["path"], "line_start": 0, "line_end": 0, "match": s["id"]}],
                "recommendation": "Ensure unique id per skill in skill.yaml",
                "signal": "",
                "supports": "blocked_other",
            })
            s["verdict"] = VERDICT_BLOCKED
        for i, d in enumerate(skills_data):
            if id_counts.get(d["id"], 0) > 1:
                verdicts[i] = VERDICT_BLOCKED

    repo_verdict = aggregate_verdict(verdicts)
    h = hashlib.sha256()
    for x in sorted(all_fingerprints):
        h.update(x.encode() if isinstance(x, str) else x)
    input_hash_sha256 = h.hexdigest()
    t1 = datetime.now(timezone.utc)
    duration_ms = int((t1 - t0).total_seconds() * 1000)
    started_at = t0.isoformat()
    finished_at = t1.isoformat()

    report_v1 = build_report_v1_from_skills(
        skills_data,
        repo_verdict,
        ruleset_version,
        input_hash_sha256,
        started_at,
        finished_at,
        duration_ms,
        source_provider="github" if source_repo else "local",
        source_repo=source_repo,
        source_ref=source_ref,
        source_commit_sha=source_commit_sha,
        source_default_branch=source_default_branch,
        repo_findings=repo_findings,
    )
    report = build_report(
        skill_id=skills_data[0]["id"] if skills_data else repo_root.name,
        skill_version=skills_data[0]["declared_version"] if skills_data else "unknown",
        ecosystem="clawdbot",
        input_type="directory",
        input_hash=input_hash_sha256[:32],
        ruleset_version=ruleset_version,
        risk_summary=[],
        ruleset=ruleset,
        commit_sha=source_commit_sha,
    )
    attestation = build_attestation(
        ruleset_version=ruleset_version,
        input_hash=input_hash_sha256[:32],
        commit_sha=source_commit_sha,
    )
    return report, attestation, report_v1


def _default_rules_path() -> Path:
    # Installed: skillscan/rules/mvp-rules.json; dev: repo root rules/
    pkg_rules = Path(__file__).resolve().parent / "rules" / "mvp-rules.json"
    if pkg_rules.is_file():
        return pkg_rules
    return Path(__file__).resolve().parents[1] / "rules" / "mvp-rules.json"


def _source_metadata(args: argparse.Namespace) -> tuple[str | None, str | None, str | None, str | None]:
    source_repo = args.repo or os.environ.get("GOV_REPO") or os.environ.get("GITHUB_REPOSITORY")
    source_ref = args.ref or os.environ.get("GOV_REF") or os.environ.get("GITHUB_REF", "")
    source_commit_sha = args.commit_sha or os.environ.get("GOV_SHA") or os.environ.get("GITHUB_SHA")
    source_default_branch = args.default_branch or os.environ.get("GOV_DEFAULT_BRANCH") or os.environ.get("GITHUB_BASE_REF", "main")
    return source_repo, source_ref, source_commit_sha, source_default_branch


def _looks_like_repo_ref(value: str) -> bool:
    if value.startswith(("https://github.com/", "git@github.com:")):
        return True
    if value.count("/") == 1 and not value.startswith(".") and not Path(value).exists():
        owner, repo = value.split("/", 1)
        return bool(owner and repo and "." not in owner and "\\" not in value)
    return False


def _normalize_repo_url(value: str) -> str:
    if value.startswith("git@github.com:"):
        slug = value.split(":", 1)[1]
        if slug.endswith(".git"):
            slug = slug[:-4]
        return f"https://github.com/{slug}"
    if value.startswith("https://github.com/"):
        return value[:-4] if value.endswith(".git") else value
    return f"https://github.com/{value}"


def _prepare_scan_target(input_value: str) -> tuple[Path, str | None]:
    raw = Path(input_value)
    if raw.is_dir():
        return raw.resolve(), None
    if raw.is_file() and raw.suffix.lower() == ".zip":
        temp_dir = tempfile.mkdtemp(prefix="skillscan-zip-")
        with zipfile.ZipFile(raw) as zf:
            zf.extractall(temp_dir)
        extracted_root = Path(temp_dir)
        items = [p for p in extracted_root.iterdir()]
        if len(items) == 1 and items[0].is_dir():
            return items[0].resolve(), temp_dir
        return extracted_root.resolve(), temp_dir
    if _looks_like_repo_ref(input_value):
        repo_url = _normalize_repo_url(input_value)
        temp_dir = tempfile.mkdtemp(prefix="skillscan-repo-")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, temp_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return Path(temp_dir).resolve(), temp_dir
    raise SystemExit(f"Unsupported input: {input_value}")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_outputs(
    *,
    args: argparse.Namespace,
    report: dict[str, Any],
    attestation: dict[str, Any],
    report_v1: dict[str, Any],
) -> None:
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.json"
    if args.format == "v1":
        report_path.write_text(json.dumps(report_v1, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Verdict: {report_v1['verdict']['status']}")
        print(f"Report: {report_path}")
    else:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        attestation_path = out_dir / "attestation.json"
        attestation_path.write_text(json.dumps(attestation, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Verdict: {report['verdict']}")
        print(f"Report: {report_path}")
        print(f"Attestation: {attestation_path}")

    render_source = report_v1 if args.format == "v1" else report_v1
    if args.html:
        html_path = out_dir / "report.html"
        _write_text(html_path, render_report_html(render_source))
        print(f"HTML: {html_path}")
    if args.markdown:
        markdown_path = out_dir / "report.md"
        _write_text(markdown_path, render_report_markdown(render_source))
        print(f"Markdown: {markdown_path}")


def run_scan(args: argparse.Namespace) -> None:
    rules_path = args.rules or _default_rules_path()
    if not rules_path.is_file():
        raise SystemExit(f"Rules file not found: {rules_path}")

    skill_root: Path | None = None
    cleanup_dir: str | None = None
    try:
        skill_root, cleanup_dir = _prepare_scan_target(str(args.input))
        source_repo, source_ref, source_commit_sha, source_default_branch = _source_metadata(args)
        if not source_repo and _looks_like_repo_ref(str(args.input)):
            value = str(args.input)
            if value.startswith("https://github.com/"):
                source_repo = value.removeprefix("https://github.com/").removesuffix(".git")
            elif value.startswith("git@github.com:"):
                source_repo = value.split(":", 1)[1].removesuffix(".git")
            elif value.count("/") == 1:
                source_repo = value

        anchors, _ = discover_skills_with_fallback(skill_root)
        if len(anchors) >= 1:
            report, attestation, report_v1 = scan_repo_multi(
                skill_root,
                rules_path,
                source_repo=source_repo,
                source_ref=source_ref,
                source_commit_sha=source_commit_sha,
                source_default_branch=source_default_branch,
            )
        else:
            report, attestation, report_v1 = scan_dir(
                skill_root,
                rules_path,
                source_repo=source_repo,
                source_ref=source_ref,
                source_commit_sha=source_commit_sha,
                source_default_branch=source_default_branch,
                skill_path_rel=args.skill_path,
            )
        _write_outputs(args=args, report=report, attestation=attestation, report_v1=report_v1)
    finally:
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def run_demo(args: argparse.Namespace) -> None:
    # Installed: skillscan/fixtures/; dev: repo root fixtures/
    pkg_dir = Path(__file__).resolve().parent
    repo_root = pkg_dir.parents[1]
    fixture_map = {
        "allowed": (pkg_dir / "fixtures" / "fixture_allowed", repo_root / "fixtures" / "fixture_allowed"),
        "needs-approval": (pkg_dir / "fixtures" / "fixture_needs_approval", repo_root / "fixtures" / "fixture_needs_approval"),
        "blocked": (pkg_dir / "fixtures" / "fixture_blocked", repo_root / "fixtures" / "fixture_blocked"),
    }
    pkg_path, repo_path = fixture_map[args.fixture]
    target = pkg_path if pkg_path.is_dir() else repo_path
    demo_args = argparse.Namespace(
        input=str(target),
        output_dir=args.output_dir,
        format="v1",
        rules=None,
        repo=f"demo/{args.fixture}",
        ref="refs/heads/demo",
        commit_sha="demo-sha",
        default_branch="main",
        skill_path=None,
        execution_mode="suggest-only",
        html=True,
        markdown=True,
    )
    run_scan(demo_args)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Scan skills and produce governance reports.")
    sub = ap.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Scan a local dir, zip, or GitHub repo.")
    scan.add_argument("input", help="Directory, .zip, GitHub URL, or owner/repo")
    scan.add_argument("-o", "--output-dir", type=Path, default=Path("."), help="Write report(s) here")
    scan.add_argument("-f", "--format", choices=["default", "v1"], default="v1", help="default=report+attestation; v1=single report.json")
    scan.add_argument("-r", "--rules", type=Path, default=None, help="Path to rules JSON")
    scan.add_argument("--repo", type=str, default=None, help="Source repo (e.g. org/repo); or use GITHUB_REPOSITORY")
    scan.add_argument("--ref", type=str, default=None, help="Source ref (e.g. refs/pull/123/merge)")
    scan.add_argument("--commit-sha", type=str, default=None, help="Commit SHA")
    scan.add_argument("--default-branch", type=str, default=None, help="Default branch")
    scan.add_argument("--skill-path", type=str, default=None, help="Skill path relative to repo root")
    scan.add_argument("--execution-mode", type=str, default="suggest-only", help="Unused; always suggest_only")
    scan.add_argument("--html", action="store_true", help="Also write report.html")
    scan.add_argument("--markdown", action="store_true", help="Also write report.md")

    demo = sub.add_parser("demo", help="Generate a demo report from bundled fixtures.")
    demo.add_argument("-o", "--output-dir", type=Path, default=Path("./demo-out"), help="Write demo output here")
    demo.add_argument(
        "--fixture",
        choices=["allowed", "needs-approval", "blocked"],
        default="needs-approval",
        help="Fixture to render",
    )
    return ap


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Backward compatibility: `python -m skillscan.cli path/to/dir ...`
    if argv and argv[0] not in {"scan", "demo", "-h", "--help"}:
        argv = ["scan", *argv]
    ap = _build_parser()
    args = ap.parse_args(argv)
    if args.command == "demo":
        run_demo(args)
        return
    if args.command == "scan":
        run_scan(args)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
