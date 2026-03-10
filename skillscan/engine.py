"""
Rule engine: load ruleset, run patterns over parsed snippets, collect evidence, compute verdict.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

from . import __version__
from .explanations import build_explanations

# Verdict 四态（契约收口；禁止散落裸字符串）
VERDICT_ALLOWED = "allowed"
VERDICT_NEEDS_APPROVAL = "needs_approval"
VERDICT_APPROVED = "approved"
VERDICT_BLOCKED = "blocked"


def load_ruleset(rules_path: Path) -> dict[str, Any]:
    with open(rules_path, encoding="utf-8") as f:
        return json.load(f)


def run_rules(
    ruleset: dict[str, Any],
    snippets: list[tuple[str, int, str]],
) -> list[dict[str, Any]]:
    """
    For each rule, run patterns over snippets; return risk_summary items with evidence.
    """
    risk: list[dict[str, Any]] = []
    for rule in ruleset.get("rules", []):
        rid = rule["id"]
        severity = rule["severity"]
        patterns = rule.get("patterns", [])
        for file_rel, line_no, line in snippets:
            for pat in patterns:
                try:
                    if re.search(pat, line, re.IGNORECASE):
                        entry = next(
                            (r for r in risk if r["rule_id"] == rid),
                            None,
                        )
                        if not entry:
                            entry = {
                                "rule_id": rid,
                                "severity": severity,
                                "evidence": [],
                            }
                            risk.append(entry)
                        entry["evidence"].append({
                            "file": file_rel,
                            "line": line_no,
                            "snippet": line[:200] + ("..." if len(line) > 200 else ""),
                        })
                        break
                except re.error:
                    continue
    return risk


def compute_verdict(risk_summary: list[dict[str, Any]]) -> str:
    priority = ["Blocked", "NeedsApproval", "Allowed"]
    severities = {r["severity"] for r in risk_summary}
    for s in priority:
        if s in severities:
            return s
    return "Allowed"


def _verdict_reason_and_endorsement(
    verdict: str,
    risk_summary: list[dict[str, Any]],
    ruleset: dict[str, Any],
) -> tuple[str | None, str]:
    """Resolve verdict_reason (when Blocked) and endorsement_level."""
    block_reasons = ruleset.get("block_reasons") or {}
    rule_by_id = {r["id"]: r for r in ruleset.get("rules", []) if "id" in r}

    if verdict == "Blocked":
        reason = None
        for r in risk_summary:
            if r.get("severity") == "Blocked":
                reason = block_reasons.get(r["rule_id"]) or rule_by_id.get(r["rule_id"], {}).get("block_reason")
                break
        return (reason, "None")
    if verdict == "NeedsApproval":
        return (None, "Restricted")
    return (None, "Full")


def _offensive_security_capability(
    risk_summary: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """If block-offsec-ad-playbook hit, return offensive_security capability block for report."""
    offsec = next((r for r in risk_summary if r.get("rule_id") == "block-offsec-ad-playbook"), None)
    if not offsec:
        return None
    return {
        "offensive_security": True,
        "targets_identity_systems": True,
        "credential_access": True,
        "lateral_movement": True,
        "privilege_escalation": True,
        "exploitation_guidance": True,
        "tooling_required": ["impacket", "mimikatz", "bloodhound", "rubeus", "crackmapexec", "responder"],
        "evidence": offsec.get("evidence", []),
    }


def build_report(
    skill_id: str,
    skill_version: str,
    ecosystem: str,
    input_type: str,
    input_hash: str,
    ruleset_version: str,
    risk_summary: list[dict[str, Any]],
    ruleset: dict[str, Any],
    commit_sha: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    verdict = compute_verdict(risk_summary)
    verdict_reason, endorsement_level = _verdict_reason_and_endorsement(verdict, risk_summary, ruleset)
    capabilities: dict[str, Any] = {}
    offsec_cap = _offensive_security_capability(risk_summary)
    if offsec_cap:
        capabilities["offensive_security"] = offsec_cap

    out = {
        "scan_version": __version__,
        "ruleset_version": ruleset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_type": input_type,
        "input_hash": input_hash,
        "commit_sha": commit_sha or "",
        "skill_id": skill_id,
        "skill_version": skill_version,
        "ecosystem": ecosystem,
        "verdict": verdict,
        "risk_summary": risk_summary,
    }
    if verdict_reason is not None:
        out["verdict_reason"] = verdict_reason
    out["endorsement_level"] = endorsement_level
    out["execution"] = {
        "mode": "suggest_only",
        "enforced_by": "policy",
        "requested": False,
    }
    if capabilities:
        out["capabilities"] = capabilities
    return out


def build_attestation(
    ruleset_version: str,
    input_hash: str,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "scan_version": __version__,
        "ruleset_version": ruleset_version,
        "input_hash": input_hash,
        "commit_sha": commit_sha or "",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- Report v1 (SaaS contract): findings with line_start/line_end/match ---

# rule_id → signal (for policy.requires_approval_signals)
RULE_ID_TO_SIGNAL: dict[str, str] = {
    "block-offsec-ad-playbook": "offsec_hit",
    "approval-sudo": "uses_sudo",
    "approval-service": "service_control",
    "approval-write-config": "writes_system_paths",
    "approval-permission": "chmod_chown",
    "approval-network": "network_download_exec",
}

# rule_id → supports (offsec_override | approval_signal | info | blocked_other)
def _rule_id_to_supports(rule_id: str) -> str:
    if rule_id == "block-offsec-ad-playbook":
        return "offsec_override"
    if rule_id.startswith("approval-"):
        return "approval_signal"
    if rule_id.startswith("allow-"):
        return "info"
    if rule_id.startswith("block-"):
        return "blocked_other"
    return "approval_signal"


def aggregate_verdict(verdicts: list[str]) -> str:
    """Repo 级聚合：任一层 blocked ⇒ blocked；否则 needs_approval ⇒ needs_approval；否则 approved ⇒ approved；否则 allowed。未知 verdict 显式拒绝。"""
    if not verdicts:
        return VERDICT_ALLOWED
    s = {v.lower() for v in verdicts}
    known = {VERDICT_ALLOWED, VERDICT_NEEDS_APPROVAL, VERDICT_APPROVED, VERDICT_BLOCKED}
    unknown = s - known
    if unknown:
        raise ValueError(f"Unknown verdict(s): {unknown}")
    if VERDICT_BLOCKED in s:
        return VERDICT_BLOCKED
    if VERDICT_NEEDS_APPROVAL in s:
        return VERDICT_NEEDS_APPROVAL
    if VERDICT_APPROVED in s:
        return VERDICT_APPROVED
    return VERDICT_ALLOWED


def apply_approval_elevation(repo_verdict: str, has_approval: bool) -> str:
    """
    SaaS 侧审批提升：仅 needs_approval + has_approval ⇒ approved；blocked 永不提升。
    契约：任意 blocked 不可被 approval 放行（对抗性测试锁死）。
    """
    if repo_verdict == VERDICT_BLOCKED:
        return VERDICT_BLOCKED
    if repo_verdict == VERDICT_NEEDS_APPROVAL and has_approval:
        return VERDICT_APPROVED
    return repo_verdict


# reason_code 注册表（禁止散落字符串；blocked 时由 _block_reason_code 产出，其余由 _verdict_to_reason_code）
REASON_CODE_OK_ALLOWED = "OK_ALLOWED"
REASON_CODE_OK_APPROVED = "OK_APPROVED"
REASON_CODE_REQUIRES_APPROVAL = "REQUIRES_APPROVAL_HIGH_RISK_SIGNALS"
REASON_CODE_POLICY_OFFSEC_BLOCKED = "POLICY_OFFSEC_BLOCKED_IN_GENERAL"
REASON_CODE_POLICY_BLOCK_REMOTE_PIPE = "POLICY_BLOCK_REMOTE_PIPE"
REASON_CODE_POLICY_BLOCK_DESTRUCTIVE_FS = "POLICY_BLOCK_DESTRUCTIVE_FS"
REASON_CODE_POLICY_BLOCK_PRIV_SSH = "POLICY_BLOCK_PRIV_SSH"
REASON_CODE_POLICY_BLOCKED_OTHER = "POLICY_BLOCKED_OTHER"

# blocked_other 按 rule_id 细分为 reason_code（审计/报表/告警聚合）
BLOCK_REASON_CODE_BY_RULE_ID: dict[str, str] = {
    "block-destructive-fs": REASON_CODE_POLICY_BLOCK_DESTRUCTIVE_FS,
    "block-priv-ssh": REASON_CODE_POLICY_BLOCK_PRIV_SSH,
}
# 显式允许归类为 POLICY_BLOCKED_OTHER 的 block-* rule_id（新增 block-* 须在映射表或本集合二选一，见 test_block_reason_code_mapping_coverage）。allowlist 是债务清单、不是垃圾桶，每次往里加都要在 PR 里解释为什么不细分 reason_code。
ALLOWED_AS_POLICY_BLOCKED_OTHER: frozenset[str] = frozenset()


def validate_verdict_reason(verdict_status: str, reason_code: str) -> bool:
    """
    校验 verdict.status 与 reason_code 的合法组合，防止脏数据流出。
    allowed→OK_ALLOWED；approved→OK_APPROVED；needs_approval→REQUIRES_APPROVAL_*；blocked→POLICY_*。
    """
    v = (verdict_status or "").lower()
    rc = (reason_code or "").strip()
    if v == "allowed":
        return rc == REASON_CODE_OK_ALLOWED
    if v == "approved":
        return rc == REASON_CODE_OK_APPROVED
    if v == "needs_approval":
        return rc.startswith("REQUIRES_APPROVAL_")
    if v == "blocked":
        return rc.startswith("POLICY_")
    return False


def _verdict_to_reason_code(verdict: str) -> str:
    """Stable machine-readable reason; do not change names after release. reason_code 必须来自此映射。blocked 时用 _block_reason_code。"""
    m = {
        VERDICT_ALLOWED: REASON_CODE_OK_ALLOWED,
        VERDICT_APPROVED: REASON_CODE_OK_APPROVED,
        VERDICT_NEEDS_APPROVAL: REASON_CODE_REQUIRES_APPROVAL,
        VERDICT_BLOCKED: REASON_CODE_POLICY_OFFSEC_BLOCKED,  # fallback when no findings
    }
    return m.get(verdict.lower() if isinstance(verdict, str) else verdict, REASON_CODE_OK_ALLOWED)


def _block_reason_code(
    skills_data: list[dict[str, Any]],
    repo_findings: list[dict[str, Any]],
) -> str:
    """
    blocked 时根据 findings 确定 reason_code；必须来自注册表常量。
    顺序：① offsec_override → POLICY_OFFSEC_BLOCKED；② blocked_other 时先按 finding 的 code/id 识别 BLOCK_REMOTE_PIPE（直接触发信号，优先级高于 rule_id 映射）；③ rule_id in BLOCK_REASON_CODE_BY_RULE_ID → 细分；④ 无证据但 effective_category=offsec → POLICY_OFFSEC_BLOCKED；⑤ else POLICY_BLOCKED_OTHER。
    finding 的“触发码”统一用 code 优先、兼容旧 id：fid = f.get("code") or f.get("id") or ""；只改其一会导致 reason_code 未细分而隐性回归。
    """
    def iter_findings() -> Iterator[dict[str, Any]]:
        for s in skills_data:
            for f in s.get("findings", []):
                yield f
        for f in repo_findings or []:
            yield f

    for f in iter_findings():
        sup = f.get("supports", "")
        if sup == "offsec_override":
            return REASON_CODE_POLICY_OFFSEC_BLOCKED
    for f in iter_findings():
        sup = f.get("supports", "")
        if sup == "blocked_other":
            fid = (f.get("code") or f.get("id") or "").upper()
            if fid == "BLOCK_REMOTE_PIPE":
                return REASON_CODE_POLICY_BLOCK_REMOTE_PIPE
            rid = f.get("rule_id", "")
            if rid in BLOCK_REASON_CODE_BY_RULE_ID:
                return BLOCK_REASON_CODE_BY_RULE_ID[rid]
            return REASON_CODE_POLICY_BLOCKED_OTHER
    if any(s.get("effective_category") == "offsec" for s in skills_data):
        return REASON_CODE_POLICY_OFFSEC_BLOCKED
    return REASON_CODE_POLICY_BLOCKED_OTHER


def _severity_to_finding_severity(rule_severity: str) -> str:
    m = {"Blocked": "critical", "NeedsApproval": "high", "Allowed": "info"}
    return m.get(rule_severity, "medium")


def _rule_id_to_short_id(rule_id: str) -> str:
    if rule_id == "block-offsec-ad-playbook":
        return "OFFSEC_AD"
    return rule_id.upper().replace("-", "_")[:32]


def _recommendation_for_rule(rule_id: str) -> str | None:
    if rule_id == "block-offsec-ad-playbook":
        return "Move to RedTeam repository; restrict visibility to redteam group; keep suggest-only"
    return None


def risk_summary_to_findings(
    risk_summary: list[dict[str, Any]],
    ruleset: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert risk_summary to v1 findings with file, line_start, line_end, match."""
    rule_by_id = {r["id"]: r for r in ruleset.get("rules", []) if "id" in r}
    findings: list[dict[str, Any]] = []
    for r in risk_summary:
        rid = r["rule_id"]
        rule = rule_by_id.get(rid, {})
        ev_list = []
        for e in r.get("evidence", []):
            line = e.get("line", 0)
            ev_list.append({
                "file": e.get("file", ""),
                "line_start": line,
                "line_end": line,
                "match": (e.get("snippet") or "")[:500],
            })
        if not ev_list:
            continue
        finding = {
            "id": _rule_id_to_short_id(rid),
            "rule_id": rid,
            "severity": _severity_to_finding_severity(r.get("severity", "")),
            "title": rule.get("name", rid),
            "evidence": ev_list,
            "signal": RULE_ID_TO_SIGNAL.get(rid, ""),
            "supports": _rule_id_to_supports(rid),
        }
        rec = _recommendation_for_rule(rid)
        if rec:
            finding["recommendation"] = rec
        findings.append(finding)
    return findings


def build_report_v1(
    skill_id: str,
    skill_version: str,
    ecosystem: str,
    ruleset_version: str,
    risk_summary: list[dict[str, Any]],
    ruleset: dict[str, Any],
    input_hash_sha256: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
    *,
    source_provider: str = "local",
    source_repo: str | None = None,
    source_ref: str | None = None,
    source_commit_sha: str | None = None,
    source_default_branch: str | None = None,
    skill_path: str | None = None,
    skill_author: str | None = None,
    skill_title: str | None = None,
    policy_version: str | None = None,
) -> dict[str, Any]:
    """Build report in v1 contract shape for SaaS / GitHub Action."""
    verdict = compute_verdict(risk_summary)
    verdict_reason, _ = _verdict_reason_and_endorsement(verdict, risk_summary, ruleset)
    _v1_status = {"Blocked": "blocked", "NeedsApproval": "needs_approval", "Allowed": "allowed"}
    verdict_status = _v1_status.get(verdict, verdict.lower())
    findings = risk_summary_to_findings(risk_summary, ruleset)

    # Capabilities flat summary
    capabilities: dict[str, Any] = {}
    offsec_cap = _offensive_security_capability(risk_summary)
    if offsec_cap:
        capabilities["offensive_security"] = True
        capabilities["credential_access"] = offsec_cap.get("credential_access", True)
        capabilities["lateral_movement"] = offsec_cap.get("lateral_movement", True)
        capabilities["exploitation_guidance"] = offsec_cap.get("exploitation_guidance", True)
        capabilities["exec_shell"] = {"level": "suggest"}
        capabilities["privilege"] = {"requires_sudo": False}
    else:
        has_sudo = any(r.get("rule_id") == "approval-sudo" for r in risk_summary)
        capabilities["exec_shell"] = {"level": "suggest"}
        capabilities["privilege"] = {"requires_sudo": has_sudo}

    skill_category = "offsec" if offsec_cap else ""

    return {
        "schema_version": "1.0",
        "scanner": {
            "name": "skillscan",
            "version": __version__,
            "ruleset_version": ruleset_version,
            "execution_mode": "suggest_only",
        },
        "source": {
            "provider": source_provider,
            "repo": source_repo or "",
            "ref": source_ref or "",
            "commit_sha": source_commit_sha or "",
            "default_branch": source_default_branch or "",
        },
        "input_fingerprint": {
            "type": "content-hash",
            "sha256": input_hash_sha256,
        },
        "skill": {
            "ecosystem": ecosystem,
            "path": skill_path or "",
            "id": skill_id,
            "author": skill_author or "",
            "declared_version": skill_version,
            "title": skill_title or skill_id,
            "category": skill_category,
        },
        "verdict": {
            "status": verdict_status,
            "reason": verdict_reason or ("OffSec skills are not allowed in General repository" if verdict == "Blocked" else ""),
            "policy_version": policy_version or f"policy@{ruleset_version}",
        },
        "capabilities": capabilities,
        "findings": findings,
        "skills": [
            {
                "path": skill_path or "",
                "id": skill_id,
                "category": skill_category,
                "verdict": {"status": verdict_status},
            }
        ],
        "timing": {
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
        },
    }


def build_report_v1_from_skills(
    skills_data: list[dict[str, Any]],
    repo_verdict: str,
    ruleset_version: str,
    input_hash_sha256: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
    *,
    source_provider: str = "local",
    source_repo: str | None = None,
    source_ref: str | None = None,
    source_commit_sha: str | None = None,
    source_default_branch: str | None = None,
    policy_version: str | None = None,
    ecosystem: str = "clawdbot",
    repo_findings: list[dict[str, Any]] | None = None,
    templates_dir: Path | None = None,
) -> dict[str, Any]:
    """多 skill repo：skills_data 每项含 path, root, anchor_type, id, fingerprint, findings, verdict；repo_verdict 已聚合。"""
    reason = ""
    if repo_verdict == "blocked":
        reason = "OffSec skills are not allowed in General repository"
    skills_out = []
    all_findings: list[dict[str, Any]] = []
    for f in repo_findings or []:
        all_findings.append(dict(f))
    for s in skills_data:
        path = s.get("path", "")
        root = s.get("root", "")
        anchor_type = s.get("anchor_type", "skill_md")
        sid = s.get("id", "")
        title = s.get("title", sid)
        category = s.get("category", "")
        declared_category = s.get("declared_category", category)
        effective_category = s.get("effective_category", category)
        signals = s.get("signals", [])
        ver = s.get("declared_version", "unknown")
        fp_val = s.get("fingerprint", "")
        fingerprint = {"algo": "sha256", "value": fp_val} if isinstance(fp_val, str) else fp_val
        findings = s.get("findings", [])
        vstatus = s.get("verdict", "allowed")
        skills_out.append({
            "path": path,
            "root": root,
            "anchor_type": anchor_type,
            "id": sid,
            "title": title,
            "category": effective_category,
            "declared_category": declared_category,
            "effective_category": effective_category,
            "signals": signals,
            "declared_version": ver,
            "fingerprint": fingerprint,
            "findings": findings,
            "verdict": {"status": vstatus},
        })
        prefix = (path.rsplit("/", 1)[0] if "/" in path else "") or (path.rsplit("\\", 1)[0] if "\\" in path else "")
        for f in findings:
            fcopy = dict(f)
            fcopy["evidence"] = []
            for e in f.get("evidence", []):
                ec = dict(e)
                if prefix and ec.get("file"):
                    ec["file"] = prefix + "/" + ec["file"]
                fcopy["evidence"].append(ec)
            all_findings.append(fcopy)
    first = skills_data[0] if skills_data else {}
    _templates_dir = templates_dir or Path(__file__).resolve().parents[1] / "policy"
    _reason_code = (
        _block_reason_code(skills_data, repo_findings or [])
        if repo_verdict == VERDICT_BLOCKED
        else _verdict_to_reason_code(repo_verdict)
    )
    _explanations_full, _explanations_top, _explanations_mode, _repo_explanation, _blocked_subtype = build_explanations(
        repo_verdict,
        skills_data,
        repo_findings or [],
        _templates_dir,
        ruleset_version=ruleset_version,
        reason_code=_reason_code,
    )
    if not validate_verdict_reason(repo_verdict, _reason_code):
        raise ValueError(
            f"invalid verdict/reason_code pair: status={repo_verdict!r} reason_code={_reason_code!r}"
        )
    return {
        "schema_version": "1.0",
        "scanner": {
            "name": "skillscan",
            "version": __version__,
            "ruleset_version": ruleset_version,
            "execution_mode": "suggest_only",
        },
        "source": {
            "provider": source_provider,
            "repo": source_repo or "",
            "ref": source_ref or "",
            "commit_sha": source_commit_sha or "",
            "default_branch": source_default_branch or "",
        },
        "input_fingerprint": {"type": "content-hash", "sha256": input_hash_sha256},
        "skill": {
            "ecosystem": ecosystem,
            "path": first.get("path", ""),
            "id": first.get("id", ""),
            "author": "",
            "declared_version": first.get("declared_version", ""),
            "title": first.get("title", ""),
            "category": first.get("category", ""),
        },
        "contract_version": "2026-02-01",
        "verdict": {
            "status": repo_verdict,
            "reason": reason,
            "reason_code": _reason_code,
            "policy_version": policy_version or f"policy@{ruleset_version}",
        },
        "explanations_mode": _explanations_mode,
        "repo_explanation": _repo_explanation,
        "capabilities": {},
        "findings": all_findings,
        "skills": skills_out,
        "explanations": _explanations_full,
        "explanations_top": _explanations_top,
        "timing": {"started_at": started_at, "finished_at": finished_at, "duration_ms": duration_ms},
        "debug": {
            "blocked_subtype": _blocked_subtype or "",
            "mode_source": "explanations_mode_from",
        },
    }
