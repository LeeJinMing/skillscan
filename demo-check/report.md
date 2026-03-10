# SkillScan Report

## Summary

- Verdict: Needs Approval
- Repo: demo/needs-approval
- Commit: demo-sha
- Ruleset: mvp-1
- Skills scanned: 1

## Why

- Reason: n/a
- Reason code: REQUIRES_APPROVAL_HIGH_RISK_SIGNALS

## Top Findings

- Skills found outside skills/ directory (repo not following convention) (unknown file) `Move anchors under skills/`
- Network egress / download binary (SKILL.md:12) `curl -sSL -o /tmp/install.sh https://example.com/install.sh
bash /tmp/install.sh`

## Skills

- fixture_needs_approval | SKILL.md | Needs Approval
