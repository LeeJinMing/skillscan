# SkillScan Report

## Summary

- Verdict: Allowed
- Repo: demo/allowed
- Commit: demo-sha
- Ruleset: mvp-1
- Skills scanned: 1

## Why

- Reason: n/a
- Reason code: OK_ALLOWED

## Top Findings

- Skills found outside skills/ directory (repo not following convention) (unknown file) `Move anchors under skills/`
- Read-only diagnostics (SKILL.md:12) `systemctl status nginx
journalctl -u nginx -n 20
ss -tlnp
curl -I http://localhost/`

## Skills

- fixture_allowed | SKILL.md | Allowed
