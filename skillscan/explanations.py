"""
Explanation templates (English-first). Top 3 from verdict-attributed findings only; stable sort; snippet safety.
Action prints: repo + explanations_top + "See console for full details: <url>".
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Severity weight (higher = more important)
SEVERITY_WEIGHT: dict[str, int] = {
    "critical": 400,
    "high": 300,
    "medium": 200,
    "low": 100,
    "info": 0,
}

# Signal priority (same severity: offsec first, then by this order)
SIGNAL_PRIORITY = [
    "offsec_hit",
    "credential_access",
    "network_download_exec",
    "writes_system_paths",
    "process_injection",
    "persistence",
    "uses_sudo",
    "service_control",
    "chmod_chown",
    "shell_exec",
]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _snippet_safe(match: str, max_lines: int = 3, max_chars_per_line: int = 200) -> str:
    """Max 3 lines, 200 chars per line; mask likely secrets (Bearer, AWS key, long hex)."""
    if not match:
        return ""
    lines = (match or "").strip().splitlines()[:max_lines]
    out: list[str] = []
    for line in lines:
        s = line[:max_chars_per_line]
        # Simple mask: Bearer tokens, AWS key prefix, long alphanumeric runs
        s = re.sub(r"Bearer\s+\S+", "Bearer ***", s, flags=re.IGNORECASE)
        s = re.sub(r"AKIA[A-Z0-9]{16}", "AKIA***", s)
        s = re.sub(r"(-----BEGIN\s+\w+\s+KEY-----)[\s\S]*", r"\1***", s)
        if len(line) > max_chars_per_line or re.search(r"[a-f0-9]{40,}", s):
            s = s[:80] + "..." if len(s) > 80 else s
        out.append(s)
    return "\n".join(out)


# reason_code 注册表（与 engine 常量一致；分流条件只查此集合，不靠 startswith）
REASON_CODE_OFFSEC = frozenset(["POLICY_OFFSEC_BLOCKED_IN_GENERAL"])
REASON_CODE_BLOCK_REASONS = frozenset([
    "POLICY_BLOCK_REMOTE_PIPE",
    "POLICY_BLOCK_DESTRUCTIVE_FS",
    "POLICY_BLOCK_PRIV_SSH",
    "POLICY_BLOCKED_OTHER",
])


def _blocked_subtype_from_reason_code(reason_code: str) -> str:
    """blocked 时分流：基于 reason_code 注册表，不靠猜字符串。返回 "offsec" | "block_reasons"。"""
    if reason_code in REASON_CODE_OFFSEC:
        return "offsec"
    if reason_code in REASON_CODE_BLOCK_REASONS:
        return "block_reasons"
    return "block_reasons"  # 未知 blocked reason 默认按硬阻断处理


def explanations_mode_from(verdict_status: str, reason_code: str) -> str:
    """
    explanations_mode 唯一收口：只查 verdict_status + reason_code 注册表，单测覆盖。
    防止 CLI/服务端/库里各写一份导致口径漂移。
    """
    v = (verdict_status or "").lower()
    if v == "blocked":
        if reason_code in REASON_CODE_OFFSEC:
            return "OFFSEC_ONLY"
        if reason_code in REASON_CODE_BLOCK_REASONS:
            return "BLOCK_REASONS_ONLY"
        return "BLOCK_REASONS_ONLY"  # 未知 blocked reason 默认硬阻断
    if v in ("needs_approval", "approved"):
        return "APPROVAL_SIGNALS_ONLY"
    return "NONE"


def _attribution_candidates(
    repo_verdict: str,
    finding_entries: list[dict[str, Any]],
    blocked_subtype: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """
    Only findings that caused the verdict.
    blocked: 分流由 reason_code 决定（caller 传入 blocked_subtype）；offsec ⇒ offsec_override，block_reasons ⇒ blocked_other。
    needs_approval: APPROVAL_SIGNALS_ONLY.
    Returns (candidates, blocked_subtype).
    """
    if repo_verdict == "allowed":
        return [], ""
    if repo_verdict == "blocked":
        support_need = "offsec_override" if blocked_subtype == "offsec" else "blocked_other"
        return [e for e in finding_entries if e.get("supports") == support_need], blocked_subtype
    return [e for e in finding_entries if e.get("supports") == "approval_signal"], ""


def _sort_key(entry: dict[str, Any]) -> tuple[int, int, str, int, str]:
    """Stable sort: severity desc, signal priority desc, file asc, line_start asc, code asc. 缺失 file/line 排后。"""
    sev = entry.get("severity", "info")
    weight = SEVERITY_WEIGHT.get(sev, 0)
    sig = entry.get("signal", "")
    try:
        pri = len(SIGNAL_PRIORITY) - SIGNAL_PRIORITY.index(sig) if sig in SIGNAL_PRIORITY else -1
    except ValueError:
        pri = -1
    file_ = entry.get("file") or "\uffff"  # 缺失的排最后
    line_raw = entry.get("line_start")
    line = line_raw if isinstance(line_raw, int) and line_raw > 0 else 10**9
    code = entry.get("code", "")
    return (-weight, -pri, file_, line, code)


def _finding_id(e: dict[str, Any]) -> tuple[str, str, str, int, str, str]:
    """Stable finding identity for dedup (avoid dict equality). 含 rule_id 避免同 file/line/code 多 pattern 被误去重。"""
    return (
        e.get("code", ""),
        e.get("signal", ""),
        e.get("file", ""),
        e.get("line_start", 0),
        e.get("supports", ""),
        e.get("rule_id", ""),
    )


def _top3_select(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick up to 3: always sort first (deterministic); prefer different signal, then different file, then fill. 去重用 _finding_id。"""
    sorted_c = sorted(candidates, key=_sort_key)
    if len(sorted_c) <= 3:
        return sorted_c[:3]
    selected: list[dict[str, Any]] = []
    used_signal: set[str] = set()
    used_file: set[str] = set()
    used_ids: set[tuple[str, str, str, int, str, str]] = set()

    for e in sorted_c:
        if len(selected) >= 3:
            break
        fid = _finding_id(e)
        if fid in used_ids:
            continue
        sig = e.get("signal", "")
        file_ = e.get("file", "")
        if sig and sig not in used_signal:
            selected.append(e)
            used_signal.add(sig)
            used_file.add(file_)
            used_ids.add(fid)

    for e in sorted_c:
        if len(selected) >= 3:
            break
        fid = _finding_id(e)
        if fid in used_ids:
            continue
        file_ = e.get("file", "")
        if file_ not in used_file:
            selected.append(e)
            used_file.add(file_)
            used_ids.add(fid)

    for e in sorted_c:
        if len(selected) >= 3:
            break
        fid = _finding_id(e)
        if fid not in used_ids:
            selected.append(e)
            used_ids.add(fid)

    return selected[:3]


def build_explanations(
    repo_verdict: str,
    skills_data: list[dict[str, Any]],
    repo_findings: list[dict[str, Any]],
    templates_dir: Path,
    ruleset_version: str = "",
    reason_code: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, dict[str, Any], str]:
    """
    Returns (explanations_full, explanations_top, explanations_mode, repo_explanation, blocked_subtype).
    explanations_top: only from findings that caused the verdict; max 3; stable sort; for Action/API.
    repo_explanation: { title, text, checklist } for Action/UI.
    """
    finding_tpl = _load_json(templates_dir / "finding-templates.json")
    signal_tpl = _load_json(templates_dir / "signal-templates.json")
    by_code = {f["code"]: f for f in finding_tpl.get("finding_templates", finding_tpl.get("findings", [])) if "code" in f}
    by_signal = {s["name"]: s for s in signal_tpl.get("signal_templates", signal_tpl.get("signals", [])) if "name" in s}

    out: list[dict[str, Any]] = []
    finding_entries: list[dict[str, Any]] = []  # with signal, supports, file, severity for attribution/sort

    # Repo level (blocked: fixed wording; needs_approval: dynamic checklist)
    if repo_verdict == "blocked":
        out.append({
            "level": "repo",
            "title": "Release blocked by policy (OffSec content in General)",
            "text": "This repository contains skills classified as OffSec. OffSec distribution is blocked in the General profile by policy.",
            "checklist": [
                "If this is for a sanctioned security exercise, move it to a RedTeam repo/profile with stricter RBAC and audit.",
                "Remove or refactor OffSec content from the General repository.",
                "Re-run the scan and re-attempt the release.",
            ],
        })
    elif repo_verdict == "needs_approval":
        sig_names = set()
        for s in skills_data:
            sig_names.update(s.get("signals", []))
        checklist: list[str] = []
        seen: set[str] = set()
        for name in sorted(sig_names):
            if name in by_signal:
                for item in by_signal[name].get("approval_checklist", []):
                    if item not in seen:
                        seen.add(item)
                        checklist.append(item)
        out.append({
            "level": "repo",
            "title": "Release requires approval",
            "text": "High-risk operational behaviors were detected. Approval is required before publishing.",
            "checklist": checklist[:6] or [
                "Confirm scope is limited (hosts/env).",
                "Confirm rollback is documented and tested.",
                "Confirm integrity/audit controls are in place.",
            ],
        })

    def add_finding_entry(
        code: str,
        title: str,
        text: str,
        snippet: str,
        signal: str,
        supports: str,
        file_: str,
        line_start: int,
        severity: str,
        path_prefix: str = "",
        rule_id: str = "",
    ) -> None:
        full_file = f"{path_prefix}/{file_}".lstrip("/") if path_prefix else file_
        entry: dict[str, Any] = {
            "level": "finding",
            "code": code,
            "title": title,
            "text": text,
            "snippet": snippet,
            "signal": signal,
            "supports": supports,
            "file": full_file,
            "line_start": line_start,
            "severity": severity,
            "rule_id": rule_id,
        }
        t = by_code.get(code, {})
        if t.get("approval_checklist"):
            entry["checklist"] = t["approval_checklist"][:3]
        out.append(entry)
        finding_entries.append(entry)

    # Finding level (full list)
    for s in skills_data:
        anchor_rel = s.get("path", "") or ""
        path_prefix = str(Path(anchor_rel).parent) if anchor_rel and Path(anchor_rel).parent != Path(".") else ""
        for f in s.get("findings", []):
            code = f.get("id", "")
            t = by_code.get(code, {})
            title = t.get("title", code)
            risk = t.get("risk_summary", "")
            impact = t.get("impact_summary", "")
            detail_tpl = t.get("detail_tpl", "Evidence: {file}:{line_start}-{line_end}.")
            ev_list = f.get("evidence", [])
            snippet = ""
            detail = ""
            file_ = ""
            line_start = 0
            if ev_list:
                ev = ev_list[0]
                file_ = ev.get("file", "")
                line_start = ev.get("line_start", 0)
                line_end = ev.get("line_end", 0)
                match = ev.get("match", "")
                snippet = _snippet_safe(match)
                try:
                    detail = detail_tpl.format(
                        file=file_,
                        line_start=line_start,
                        line_end=line_end,
                        match=match,
                    )
                except KeyError:
                    detail = f"{file_}:{line_start}-{line_end}"
            text_parts = [p for p in [risk, impact, detail] if p]
            text = " ".join(text_parts).strip() or title
            sev = f.get("severity", "high")
            sig = f.get("signal", "")
            sup = f.get("supports", "approval_signal")
            add_finding_entry(code, title, text, snippet, sig, sup, file_, line_start, sev, path_prefix, rule_id=f.get("rule_id", ""))

    for f in repo_findings:
        code = f.get("id", "")
        t = by_code.get(code, {})
        title = t.get("title", code)
        risk = t.get("risk_summary", "")
        impact = t.get("impact_summary", "")
        ev_list = f.get("evidence", [])
        match = ev_list[0].get("match", "") if ev_list else ""
        snippet = _snippet_safe(match)
        text = " ".join([p for p in [risk, impact] if p]).strip() or title
        add_finding_entry(
            code, title, text, snippet,
            "", "approval_signal", "", 0,
            f.get("severity", "medium"),
            rule_id=f.get("rule_id", ""),
        )

    # Attribution: blocked 分流基于 reason_code 注册表（不靠 startswith）；needs_approval 取 approval_signal
    if repo_verdict == "blocked":
        blocked_subtype = _blocked_subtype_from_reason_code(reason_code)
    else:
        blocked_subtype = ""
    candidates, blocked_subtype = _attribution_candidates(repo_verdict, finding_entries, blocked_subtype)

    # Blocked(OffSec): fill up to 3 with synthetic OffSec findings (one per skill with effective_category=offsec)
    if repo_verdict == "blocked" and blocked_subtype == "offsec" and len(candidates) < 3:
        for s in skills_data:
            if len(candidates) >= 3:
                break
            if s.get("effective_category") != "offsec":
                continue
            skill_path = s.get("path", "") or ""
            synth: dict[str, Any] = {
                "level": "finding",
                "code": "OFFSEC_OVERRIDE_SYNTH",
                "rule_id": "offsec-override-synth",
                "title": "OffSec classification override",
                "text": f"OffSec classification override triggered by ruleset {ruleset_version or 'unknown'}. See console for details.",
                "snippet": "",
                "signal": "offsec_hit",
                "supports": "offsec_override",
                "file": skill_path,
                "line_start": 1,
                "severity": "critical",
            }
            out.append(synth)
            finding_entries.append(synth)
            candidates.append(synth)
        # Still none: add one generic synth
        if not candidates:
            synth = {
                "level": "finding",
                "code": "OFFSEC_OVERRIDE_SYNTH",
                "rule_id": "offsec-override-synth",
                "title": "OffSec classification override",
                "text": f"OffSec classification override triggered by ruleset {ruleset_version or 'unknown'}. See console for details.",
                "snippet": "",
                "signal": "offsec_hit",
                "supports": "offsec_override",
                "file": "",
                "line_start": 0,
                "severity": "critical",
            }
            out.append(synth)
            candidates.append(synth)

    # Top 3 from candidates only (blocked: prefer different file; same signal ok)
    top3 = _top3_select(candidates)
    explanations_top = [
        {k: v for k, v in e.items() if k in ("level", "code", "title", "text", "snippet", "checklist")}
        for e in top3
    ]

    # explanations_mode: 唯一收口；mode 仅由 reason_code 驱动，override 只改 reason_code（engine 侧）
    explanations_mode = explanations_mode_from(repo_verdict, reason_code)

    # Blocked(block_reasons): 替换 repo 级文案为“硬阻断”说明（remote-pipe 等）
    if repo_verdict == "blocked" and blocked_subtype == "block_reasons":
        for i, e in enumerate(out):
            if e.get("level") == "repo":
                out[i] = {
                    "level": "repo",
                    "title": "Release blocked by policy (hard block)",
                    "text": "This repository triggered a hard block rule (e.g. remote pipe execution). See findings below.",
                    "checklist": [
                        "Remove or refactor the blocked pattern (e.g. curl|wget ... | bash/sh).",
                        "Re-run the scan and re-attempt the release.",
                    ],
                }
                break

    # repo_explanation: dedicated object for Action/UI (title, text, checklist)
    repo_explanation: dict[str, Any] = {}
    for e in out:
        if e.get("level") == "repo":
            repo_explanation = {
                "title": e.get("title", ""),
                "text": e.get("text", ""),
                "checklist": e.get("checklist", []),
            }
            break

    return (out, explanations_top, explanations_mode, repo_explanation, blocked_subtype)
