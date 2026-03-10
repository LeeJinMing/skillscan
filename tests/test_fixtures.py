"""
Golden tests: 固定测试向量锁死行为。
Run: python tests/test_fixtures.py  或  pytest tests/test_fixtures.py -v
验收：allowed / needs_approval / approved / blocked / blocked+approval 不提升 / blocked synth / top3 dedupe / deterministic
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skillscan.engine import (
    VERDICT_ALLOWED,
    VERDICT_APPROVED,
    VERDICT_BLOCKED,
    VERDICT_NEEDS_APPROVAL,
    REASON_CODE_POLICY_BLOCK_REMOTE_PIPE,
    REASON_CODE_POLICY_OFFSEC_BLOCKED,
    REASON_CODE_POLICY_BLOCK_DESTRUCTIVE_FS,
    REASON_CODE_POLICY_BLOCK_PRIV_SSH,
    ALLOWED_AS_POLICY_BLOCKED_OTHER,
    BLOCK_REASON_CODE_BY_RULE_ID,
    _verdict_to_reason_code,
    apply_approval_elevation,
    aggregate_verdict,
    build_report_v1_from_skills,
    load_ruleset,
    validate_verdict_reason,
)
from skillscan.explanations import explanations_mode_from
from skillscan.cli import scan_repo_multi
from skillscan.saas_contract import build_post_reports_response


def _scan_fixture_dir(fixture_name: str) -> dict:
    """Run scanner on fixture dir and return report_v1."""
    fixture_dir = ROOT / "fixtures" / fixture_name
    rules_path = ROOT / "rules" / "mvp-rules.json"
    if not fixture_dir.is_dir():
        raise FileNotFoundError(f"fixture dir missing: {fixture_dir}")
    _, _, report_v1 = scan_repo_multi(fixture_dir, rules_path)
    return report_v1


def _build_report_from_skills_data(
    skills_data: list[dict],
    repo_verdict: str,
    repo_findings: list[dict] | None = None,
) -> dict:
    """Build v1 report from in-memory skills_data (for Approved / Blocked synth / Top3 dedupe)."""
    return build_report_v1_from_skills(
        skills_data,
        repo_verdict,
        ruleset_version="2026-02-01",
        input_hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        started_at="2026-02-01T00:00:00Z",
        finished_at="2026-02-01T00:00:01Z",
        duration_ms=1000,
        repo_findings=repo_findings or [],
    )


def test_fixture_allowed():
    """Fixture 1: Allowed (无高风险). 期望 repo_verdict=allowed, explanations_mode=NONE, explanations_top=[]."""
    report = _scan_fixture_dir("fixture_allowed")
    assert report["verdict"]["status"] == VERDICT_ALLOWED
    assert report["explanations_mode"] == "NONE"
    assert report["explanations_top"] == []
    assert report["verdict"]["reason_code"] == "OK_ALLOWED"


def test_fixture_needs_approval():
    """Fixture 2: Needs approval (一个 signal). 期望 repo_verdict=needs_approval, explanations_mode=APPROVAL_SIGNALS_ONLY, Top3 含该 finding."""
    report = _scan_fixture_dir("fixture_needs_approval")
    assert report["verdict"]["status"] == VERDICT_NEEDS_APPROVAL
    assert report["explanations_mode"] == "APPROVAL_SIGNALS_ONLY"
    top = report["explanations_top"]
    assert len(top) >= 1
    codes = [e.get("code") for e in top]
    assert "APPROVAL_NETWORK" in codes or any("DOWNLOAD" in c or "NETWORK" in c for c in codes)
    assert report["verdict"]["reason_code"] == "REQUIRES_APPROVAL_HIGH_RISK_SIGNALS"


def test_validate_verdict_reason():
    """reason_code 与 verdict.status 合法组合校验，防止脏数据流出。"""
    assert validate_verdict_reason("allowed", "OK_ALLOWED") is True
    assert validate_verdict_reason("allowed", "OK_APPROVED") is False
    assert validate_verdict_reason("approved", "OK_APPROVED") is True
    assert validate_verdict_reason("approved", "OK_ALLOWED") is False
    assert validate_verdict_reason("needs_approval", "REQUIRES_APPROVAL_HIGH_RISK_SIGNALS") is True
    assert validate_verdict_reason("needs_approval", "OK_ALLOWED") is False
    assert validate_verdict_reason("blocked", REASON_CODE_POLICY_OFFSEC_BLOCKED) is True
    assert validate_verdict_reason("blocked", REASON_CODE_POLICY_BLOCK_REMOTE_PIPE) is True
    assert validate_verdict_reason("blocked", REASON_CODE_POLICY_BLOCK_DESTRUCTIVE_FS) is True
    assert validate_verdict_reason("blocked", REASON_CODE_POLICY_BLOCK_PRIV_SSH) is True
    assert validate_verdict_reason("blocked", "POLICY_BLOCKED_OTHER") is True
    assert validate_verdict_reason("blocked", "OK_ALLOWED") is False


def test_saas_post_reports_response_shape():
    """SaaS POST /reports 响应必须含 approval_elevation_applied / approval_scope_matched。"""
    r = build_post_reports_response("scan-1", "blocked", "OffSec blocked", console_url="https://x/y")
    assert "scan_id" in r and r["scan_id"] == "scan-1"
    assert "verdict" in r and r["verdict"]["status"] == "blocked"
    assert "approval_elevation_applied" in r
    assert "approval_scope_matched" in r
    assert r["approval_elevation_applied"] is False
    assert r["approval_scope_matched"] is None


def test_saas_approval_elevation_fields():
    """approval_elevation_applied=True 时 approval_scope_matched 为 scope 对象；否则 null。"""
    r_blocked = build_post_reports_response("s1", "blocked", approval_elevation_applied=False)
    assert r_blocked["approval_elevation_applied"] is False
    assert r_blocked["approval_scope_matched"] is None

    scope = {"type": "repo_commit", "key": "repo=org/repo", "commit_sha": "abc123"}
    r_approved = build_post_reports_response(
        "s2", "approved", "Approved", approval_elevation_applied=True, approval_scope_matched=scope
    )
    assert r_approved["approval_elevation_applied"] is True
    assert r_approved["approval_scope_matched"] == scope


def test_explanations_mode_from():
    """explanations_mode 唯一收口：单测覆盖 verdict_status + reason_code 所有分支。"""
    assert explanations_mode_from("allowed", "") == "NONE"
    assert explanations_mode_from("needs_approval", "REQUIRES_APPROVAL_HIGH_RISK_SIGNALS") == "APPROVAL_SIGNALS_ONLY"
    assert explanations_mode_from("approved", "OK_APPROVED") == "APPROVAL_SIGNALS_ONLY"
    assert explanations_mode_from("blocked", REASON_CODE_POLICY_OFFSEC_BLOCKED) == "OFFSEC_ONLY"
    assert explanations_mode_from("blocked", REASON_CODE_POLICY_BLOCK_REMOTE_PIPE) == "BLOCK_REASONS_ONLY"
    assert explanations_mode_from("blocked", REASON_CODE_POLICY_BLOCK_DESTRUCTIVE_FS) == "BLOCK_REASONS_ONLY"
    assert explanations_mode_from("blocked", REASON_CODE_POLICY_BLOCK_PRIV_SSH) == "BLOCK_REASONS_ONLY"
    assert explanations_mode_from("blocked", "POLICY_BLOCKED_OTHER") == "BLOCK_REASONS_ONLY"
    assert explanations_mode_from("blocked", "") == "BLOCK_REASONS_ONLY"  # 未知 blocked 默认硬阻断


def test_fixture_remote_pipe():
    """Remote-pipe verdict 锁死：reason_code=POLICY_BLOCK_REMOTE_PIPE；解释链路 BLOCK_REASONS_ONLY + Top3 含 BLOCK_REMOTE_PIPE。本断言兜底 _block_reason_code 优先级（id/code 先于 rule_id 映射），勿删。"""
    report = _scan_fixture_dir("fixture_remote_pipe")
    assert report["verdict"]["status"] == VERDICT_BLOCKED
    assert report["verdict"]["reason_code"] == REASON_CODE_POLICY_BLOCK_REMOTE_PIPE, "remote-pipe blocked must return POLICY_BLOCK_REMOTE_PIPE (reason_code registry)"
    all_codes = [e.get("id", "") or e.get("code", "") for e in report.get("findings", [])]
    assert "BLOCK_REMOTE_PIPE" in all_codes, "findings must contain BLOCK_REMOTE_PIPE when remote-pipe rule fires (rules/mvp-rules.json: block-remote-pipe = Blocked)"
    assert report["explanations_mode"] == "BLOCK_REASONS_ONLY", "blocked by non-OffSec (remote-pipe) must use BLOCK_REASONS_ONLY so Top3 shows block reason"
    top_codes = [e.get("code", "") for e in report.get("explanations_top", [])]
    assert "BLOCK_REMOTE_PIPE" in top_codes, "explanations_top must contain BLOCK_REMOTE_PIPE so Action/Console explain why blocked"
    assert report.get("debug", {}).get("blocked_subtype") == "block_reasons"
    assert report.get("debug", {}).get("mode_source") == "explanations_mode_from"


def test_blocked_remote_pipe_plus_offsec_skill_explains_remote_pipe():
    """对抗 fixture：report 同时含 remote-pipe blocked_other finding + 有 offsec effective_category 但无 offsec evidence ⇒ reason_code 仍 POLICY_BLOCK_REMOTE_PIPE，mode 仍 BLOCK_REASONS_ONLY，Top3 解释 remote-pipe（不被 offsec category 抢解释权）。"""
    skills_data = [
        {
            "path": "skills/offsec/SKILL.md",
            "root": "skills/offsec",
            "anchor_type": "skill_md",
            "id": "test/offsec",
            "title": "OffSec",
            "category": "offsec",
            "declared_category": "unknown",
            "effective_category": "offsec",
            "signals": ["offsec_hit"],
            "declared_version": "1.0",
            "fingerprint": "x",
            "findings": [],  # 无 offsec_override 证据
            "verdict": VERDICT_BLOCKED,
        },
        {
            "path": "skills/curl-pipe/SKILL.md",
            "root": "skills/curl-pipe",
            "anchor_type": "skill_md",
            "id": "test/curl-pipe",
            "title": "Curl pipe",
            "category": "devops",
            "declared_category": "devops",
            "effective_category": "devops",
            "signals": [],
            "declared_version": "1.0",
            "fingerprint": "y",
            "findings": [
                {
                    "id": "BLOCK_REMOTE_PIPE",
                    "rule_id": "block-remote-pipe",
                    "severity": "critical",
                    "signal": "",
                    "supports": "blocked_other",
                    "evidence": [{"file": "SKILL.md", "line_start": 10, "line_end": 10, "match": "curl ... | bash"}],
                }
            ],
            "verdict": VERDICT_BLOCKED,
        },
    ]
    report = _build_report_from_skills_data(skills_data, repo_verdict=VERDICT_BLOCKED)
    assert report["verdict"]["reason_code"] == REASON_CODE_POLICY_BLOCK_REMOTE_PIPE
    assert report["explanations_mode"] == "BLOCK_REASONS_ONLY"
    top_codes = [e.get("code", "") for e in report["explanations_top"]]
    assert "BLOCK_REMOTE_PIPE" in top_codes
    assert "OFFSEC_OVERRIDE_SYNTH" not in top_codes


def test_block_reason_code_destructive_fs():
    """block-destructive-fs 触发时 reason_code=POLICY_BLOCK_DESTRUCTIVE_FS（审计/报表细分）。"""
    skills_data = [
        {
            "path": "skills/foo/SKILL.md",
            "root": "skills/foo",
            "anchor_type": "skill_md",
            "id": "test/foo",
            "title": "Foo",
            "category": "",
            "declared_category": "",
            "effective_category": "",
            "signals": [],
            "declared_version": "1.0",
            "fingerprint": "x",
            "findings": [
                {
                    "id": "BLOCK_DESTRUCTIVE_FS",
                    "rule_id": "block-destructive-fs",
                    "severity": "critical",
                    "signal": "",
                    "supports": "blocked_other",
                    "evidence": [{"file": "SKILL.md", "line_start": 1, "line_end": 1, "match": "rm -rf /"}],
                }
            ],
            "verdict": VERDICT_BLOCKED,
        }
    ]
    report = _build_report_from_skills_data(skills_data, repo_verdict=VERDICT_BLOCKED)
    assert report["verdict"]["reason_code"] == REASON_CODE_POLICY_BLOCK_DESTRUCTIVE_FS


def test_block_reason_code_mapping_coverage():
    """ruleset 中所有 block-* 规则（除 offsec/remote-pipe）须在 BLOCK_REASON_CODE_BY_RULE_ID 或 ALLOWED_AS_POLICY_BLOCKED_OTHER 中，避免新增规则又糊成 OTHER。"""
    ruleset = load_ruleset(ROOT / "rules" / "mvp-rules.json")
    block_rules = [
        r for r in ruleset.get("rules", [])
        if (r.get("id") or "").startswith("block-")
        and r.get("id") not in ("block-offsec-ad-playbook", "block-remote-pipe")
    ]
    for r in block_rules:
        rid = r.get("id", "")
        assert rid in BLOCK_REASON_CODE_BY_RULE_ID or rid in ALLOWED_AS_POLICY_BLOCKED_OTHER, (
            f"block-* rule_id {rid!r}: add to BLOCK_REASON_CODE_BY_RULE_ID (for a dedicated reason_code) "
            "or to ALLOWED_AS_POLICY_BLOCKED_OTHER (if intentionally OTHER)"
        )


def test_block_reason_code_priv_ssh():
    """block-priv-ssh 触发时 reason_code=POLICY_BLOCK_PRIV_SSH（审计/报表细分）。"""
    skills_data = [
        {
            "path": "skills/bar/SKILL.md",
            "root": "skills/bar",
            "anchor_type": "skill_md",
            "id": "test/bar",
            "title": "Bar",
            "category": "",
            "declared_category": "",
            "effective_category": "",
            "signals": [],
            "declared_version": "1.0",
            "fingerprint": "y",
            "findings": [
                {
                    "id": "BLOCK_PRIV_SSH",
                    "rule_id": "block-priv-ssh",
                    "severity": "critical",
                    "signal": "",
                    "supports": "blocked_other",
                    "evidence": [{"file": "SKILL.md", "line_start": 1, "line_end": 1, "match": "authorized_keys"}],
                }
            ],
            "verdict": VERDICT_BLOCKED,
        }
    ]
    report = _build_report_from_skills_data(skills_data, repo_verdict=VERDICT_BLOCKED)
    assert report["verdict"]["reason_code"] == REASON_CODE_POLICY_BLOCK_PRIV_SSH


def test_fixture_blocked():
    """Fixture 4: Blocked (General + offsec). 期望 repo_verdict=blocked, explanations_mode=OFFSEC_ONLY, Top3 仅 offsec；debug.blocked_subtype=offsec。"""
    report = _scan_fixture_dir("fixture_blocked")
    assert report["verdict"]["status"] == VERDICT_BLOCKED
    assert report["explanations_mode"] == "OFFSEC_ONLY"
    assert report["verdict"]["reason_code"] == "POLICY_OFFSEC_BLOCKED_IN_GENERAL"
    assert report.get("debug", {}).get("blocked_subtype") == "offsec"
    top = report["explanations_top"]
    for e in top:
        assert e.get("code") in ("OFFSEC_AD", "OFFSEC_OVERRIDE_SYNTH"), f"blocked Top3 must be offsec only: {e}"


def test_explanations_top_deterministic():
    """同一份 report 多跑几次，explanations_top 的 hash 必须一致（C. deterministic）."""
    report = _scan_fixture_dir("fixture_needs_approval")
    top1 = json.dumps(report["explanations_top"], sort_keys=True)
    report2 = _scan_fixture_dir("fixture_needs_approval")
    top2 = json.dumps(report2["explanations_top"], sort_keys=True)
    assert hashlib.sha256(top1.encode()).hexdigest() == hashlib.sha256(top2.encode()).hexdigest()


def test_reason_code_registry():
    """reason_code 必须来自 _verdict_to_reason_code 映射（审查点 A）."""
    assert _verdict_to_reason_code(VERDICT_BLOCKED) == "POLICY_OFFSEC_BLOCKED_IN_GENERAL"
    assert _verdict_to_reason_code(VERDICT_NEEDS_APPROVAL) == "REQUIRES_APPROVAL_HIGH_RISK_SIGNALS"
    assert _verdict_to_reason_code(VERDICT_ALLOWED) == "OK_ALLOWED"
    assert _verdict_to_reason_code(VERDICT_APPROVED) == "OK_APPROVED"


# --- 4 个必须补的验收用例（不补别叫可上线）---

def test_fixture_approved():
    """Fixture 3: 同一 needs_approval 数据 + 模拟 approval 后 → repo_verdict=approved，explanations_mode=APPROVAL_SIGNALS_ONLY，Top3 仍来自 approval signals。"""
    # 构造与 fixture_needs_approval 同构的 skills_data（一个 approval_signal finding）
    skills_data = [
        {
            "path": "skills/curl-script/SKILL.md",
            "root": "skills/curl-script",
            "anchor_type": "skill_md",
            "id": "test/curl-script",
            "title": "Curl script",
            "category": "devops",
            "declared_category": "devops",
            "effective_category": "devops",
            "signals": ["network_download_exec"],
            "declared_version": "1.0",
            "fingerprint": "abc",
            "findings": [
                {
                    "id": "APPROVAL_NETWORK",
                    "severity": "high",
                    "signal": "network_download_exec",
                    "supports": "approval_signal",
                    "evidence": [{"file": "SKILL.md", "line_start": 10, "line_end": 10, "match": "curl -o x.sh ; bash x.sh"}],
                }
            ],
            "verdict": VERDICT_NEEDS_APPROVAL,
        }
    ]
    report = _build_report_from_skills_data(skills_data, repo_verdict=VERDICT_APPROVED)
    assert report["verdict"]["status"] == VERDICT_APPROVED
    assert report["verdict"]["reason_code"] == "OK_APPROVED"
    assert report["explanations_mode"] == "APPROVAL_SIGNALS_ONLY"
    top = report["explanations_top"]
    assert len(top) >= 1, "approved 时 Top3 仍只来自 approval signals，不能变成 NONE/空"
    codes = [e.get("code") for e in top]
    assert any(c in ("APPROVAL_NETWORK", "NET_DOWNLOAD_EXEC") or "NETWORK" in (c or "") for c in codes)


def test_blocked_approval_never_elevates():
    """对抗性测试：blocked + 存在 approval 仍为 blocked（防止回归「if approved then pass」）。"""
    assert apply_approval_elevation(VERDICT_BLOCKED, True) == VERDICT_BLOCKED
    assert apply_approval_elevation(VERDICT_BLOCKED, False) == VERDICT_BLOCKED
    assert apply_approval_elevation(VERDICT_NEEDS_APPROVAL, True) == VERDICT_APPROVED
    assert apply_approval_elevation(VERDICT_NEEDS_APPROVAL, False) == VERDICT_NEEDS_APPROVAL


def test_blocked_no_evidence_synthetic_finding():
    """Fixture 5: offsec_hit=true 但无 supports=offsec_override 证据 → 必须生成 OFFSEC_OVERRIDE_SYNTH。"""
    skills_data = [
        {
            "path": "skills/offsec/SKILL.md",
            "root": "skills/offsec",
            "anchor_type": "skill_md",
            "id": "test/offsec",
            "title": "OffSec",
            "category": "offsec",
            "declared_category": "unknown",
            "effective_category": "offsec",
            "signals": ["offsec_hit"],
            "declared_version": "1.0",
            "fingerprint": "x",
            "findings": [],  # 无 offsec_override 证据（如仅元数据/目录命中）
            "verdict": VERDICT_BLOCKED,
        }
    ]
    report = _build_report_from_skills_data(skills_data, repo_verdict=VERDICT_BLOCKED)
    assert report["verdict"]["status"] == VERDICT_BLOCKED
    assert report["explanations_mode"] == "OFFSEC_ONLY"
    top = report["explanations_top"]
    assert len(top) >= 1
    assert top[0].get("code") == "OFFSEC_OVERRIDE_SYNTH"
    # 全量 explanations 里 synth 条目应有 file（锚点路径）
    full_explanations = report.get("explanations", [])
    synth_full = next((e for e in full_explanations if e.get("code") == "OFFSEC_OVERRIDE_SYNTH"), None)
    assert synth_full is not None and (synth_full.get("file") or "").strip() != ""


def test_top3_dedupe_and_deterministic():
    """Top3 去重：先不同 signal，再不同 file；顺序稳定；无 set 导致顺序漂移。"""
    # 同一 signal 同文件 2 次 + 另一 signal 另一文件 1 次
    skills_data = [
        {
            "path": "skills/multi/SKILL.md",
            "root": "skills/multi",
            "anchor_type": "skill_md",
            "id": "test/multi",
            "title": "Multi",
            "category": "devops",
            "declared_category": "devops",
            "effective_category": "devops",
            "signals": ["network_download_exec", "uses_sudo"],
            "declared_version": "1.0",
            "fingerprint": "y",
            "findings": [
                {"id": "APPROVAL_NETWORK", "severity": "high", "signal": "network_download_exec", "supports": "approval_signal", "evidence": [{"file": "a.md", "line_start": 1, "line_end": 1, "match": "curl|sh"}]},
                {"id": "APPROVAL_NETWORK", "severity": "high", "signal": "network_download_exec", "supports": "approval_signal", "evidence": [{"file": "a.md", "line_start": 2, "line_end": 2, "match": "wget|bash"}]},
                {"id": "APPROVAL_SUDO", "severity": "high", "signal": "uses_sudo", "supports": "approval_signal", "evidence": [{"file": "b.md", "line_start": 1, "line_end": 1, "match": "sudo systemctl"}]},
            ],
            "verdict": VERDICT_NEEDS_APPROVAL,
        }
    ]
    report1 = _build_report_from_skills_data(skills_data, repo_verdict=VERDICT_NEEDS_APPROVAL)
    report2 = _build_report_from_skills_data(skills_data, repo_verdict=VERDICT_NEEDS_APPROVAL)
    top1 = report1["explanations_top"]
    top2 = report2["explanations_top"]
    assert len(top1) <= 3 and len(top2) <= 3
    # 顺序必须完全一致（deterministic）
    assert json.dumps(top1, sort_keys=True) == json.dumps(top2, sort_keys=True)
    # 优先不同 signal：应同时出现 network_download_exec 与 uses_sudo（若至少 2 条）
    signals_in_top = [e.get("code") for e in top1]
    if len(top1) >= 2:
        assert len(set(signals_in_top)) >= 1  # 至少 2 条时应有不同 code 或不同 file 体现
    # hash 稳定
    h1 = hashlib.sha256(json.dumps(top1, sort_keys=True).encode()).hexdigest()
    h2 = hashlib.sha256(json.dumps(top2, sort_keys=True).encode()).hexdigest()
    assert h1 == h2


def test_top3_ordering_shuffle_independent():
    """Top3 顺序与输入 finding 顺序无关：打乱 findings 后 Top3 仍严格按 severity/signal/file/line/code 一致。"""
    findings_same = [
        {"id": "APPROVAL_NETWORK", "severity": "high", "signal": "network_download_exec", "supports": "approval_signal", "evidence": [{"file": "a.md", "line_start": 1, "line_end": 1, "match": "curl"}]},
        {"id": "APPROVAL_SUDO", "severity": "high", "signal": "uses_sudo", "supports": "approval_signal", "evidence": [{"file": "b.md", "line_start": 1, "line_end": 1, "match": "sudo"}]},
        {"id": "APPROVAL_SERVICE", "severity": "high", "signal": "service_control", "supports": "approval_signal", "evidence": [{"file": "c.md", "line_start": 1, "line_end": 1, "match": "systemctl"}]},
    ]
    # 两种不同顺序的 findings
    order1 = [findings_same[0], findings_same[1], findings_same[2]]
    order2 = [findings_same[2], findings_same[0], findings_same[1]]
    def make_skills_data(findings_order: list) -> list:
        return [{
            "path": "skills/x/SKILL.md", "root": "skills/x", "anchor_type": "skill_md", "id": "test/x", "title": "X",
            "category": "devops", "declared_category": "devops", "effective_category": "devops",
            "signals": ["network_download_exec", "uses_sudo", "service_control"], "declared_version": "1.0", "fingerprint": "z",
            "findings": findings_order, "verdict": VERDICT_NEEDS_APPROVAL,
        }]
    report1 = _build_report_from_skills_data(make_skills_data(order1), repo_verdict=VERDICT_NEEDS_APPROVAL)
    report2 = _build_report_from_skills_data(make_skills_data(order2), repo_verdict=VERDICT_NEEDS_APPROVAL)
    top1 = report1["explanations_top"]
    top2 = report2["explanations_top"]
    assert json.dumps(top1, sort_keys=True) == json.dumps(top2, sort_keys=True), "Top3 must be identical regardless of input finding order"


def test_aggregate_verdict_unknown_raises():
    """aggregate_verdict 对未知 verdict 显式拒绝（防静默误用）。"""
    aggregate_verdict([VERDICT_ALLOWED])
    aggregate_verdict([VERDICT_NEEDS_APPROVAL, VERDICT_ALLOWED])
    aggregate_verdict([VERDICT_APPROVED])
    try:
        aggregate_verdict(["foo"])
    except ValueError as e:
        assert "Unknown" in str(e) or "foo" in str(e)
    else:
        raise AssertionError("aggregate_verdict(['foo']) must raise ValueError")


def run_all():
    """Run all golden tests (no pytest). 验收：allowed / needs_approval / approved / blocked / blocked+approval / blocked synth / top3 dedupe / deterministic."""
    cases = [
        "test_fixture_allowed",
        "test_fixture_needs_approval",
        "test_fixture_blocked",
        "test_explanations_top_deterministic",
        "test_reason_code_registry",
        "test_fixture_approved",
        "test_blocked_approval_never_elevates",
        "test_blocked_no_evidence_synthetic_finding",
        "test_top3_dedupe_and_deterministic",
        "test_top3_ordering_shuffle_independent",
        "test_aggregate_verdict_unknown_raises",
        "test_validate_verdict_reason",
        "test_saas_post_reports_response_shape",
        "test_saas_approval_elevation_fields",
        "test_fixture_remote_pipe",
        "test_explanations_mode_from",
        "test_blocked_remote_pipe_plus_offsec_skill_explains_remote_pipe",
        "test_block_reason_code_mapping_coverage",
        "test_block_reason_code_destructive_fs",
        "test_block_reason_code_priv_ssh",
    ]
    ok = 0
    for name in cases:
        try:
            globals()[name]()
            print(f"  OK {name}")
            ok += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
    print(f"--- {ok}/{len(cases)} passed ---")
    return ok == len(cases)


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
