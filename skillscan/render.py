from __future__ import annotations

from html import escape
from typing import Any


def _verdict_badge(status: str) -> str:
    s = (status or "").strip().lower()
    if s == "blocked":
        return "Blocked"
    if s == "needs_approval":
        return "Needs Approval"
    if s == "approved":
        return "Approved"
    return "Allowed"


def _top_findings(report: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    findings = report.get("findings") or []
    if not isinstance(findings, list):
        return []
    out: list[dict[str, Any]] = []
    for item in findings[:limit]:
        if isinstance(item, dict):
            out.append(item)
    return out


def render_report_markdown(report: dict[str, Any]) -> str:
    verdict = report.get("verdict") or {}
    verdict_status = verdict.get("status", "allowed")
    source = report.get("source") or {}
    findings = _top_findings(report, limit=10)
    skills = report.get("skills") or []

    lines = [
        "# SkillScan Report",
        "",
        "## Summary",
        "",
        f"- Verdict: {_verdict_badge(str(verdict_status))}",
        f"- Repo: {source.get('repo', '') or 'local'}",
        f"- Commit: {source.get('commit_sha', '') or 'n/a'}",
        f"- Ruleset: {(report.get('scanner') or {}).get('ruleset_version', '') or 'unknown'}",
        f"- Skills scanned: {len(skills) if isinstance(skills, list) else 0}",
        "",
    ]
    reason = verdict.get("reason") or ""
    reason_code = verdict.get("reason_code") or ""
    if reason or reason_code:
        lines.extend([
            "## Why",
            "",
            f"- Reason: {reason or 'n/a'}",
            f"- Reason code: {reason_code or 'n/a'}",
            "",
        ])
    if findings:
        lines.extend([
            "## Top Findings",
            "",
        ])
        for finding in findings:
            evidence = ""
            ev_list = finding.get("evidence") or []
            if isinstance(ev_list, list) and ev_list:
                first = ev_list[0] if isinstance(ev_list[0], dict) else {}
                file_name = first.get("file") or ""
                line_no = first.get("line_start") or first.get("line") or ""
                match = first.get("match") or ""
                where = file_name or "unknown file"
                if line_no:
                    where = f"{where}:{line_no}"
                evidence = f" ({where})"
                if match:
                    evidence += f" `{str(match).strip()[:120]}`"
            lines.append(f"- {finding.get('title') or finding.get('id') or 'Finding'}{evidence}")
        lines.append("")
    if isinstance(skills, list) and skills:
        lines.extend([
            "## Skills",
            "",
        ])
        for skill in skills[:20]:
            if not isinstance(skill, dict):
                continue
            lines.append(
                f"- {(skill.get('title') or skill.get('id') or 'unknown')} | {skill.get('path') or '.'} | {_verdict_badge(str((skill.get('verdict') or {}).get('status', 'allowed')))}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_report_html(report: dict[str, Any]) -> str:
    verdict = report.get("verdict") or {}
    verdict_status = str(verdict.get("status", "allowed"))
    source = report.get("source") or {}
    findings = _top_findings(report, limit=10)
    skills = report.get("skills") or []

    finding_items = []
    for finding in findings:
        evidence_html = ""
        ev_list = finding.get("evidence") or []
        if isinstance(ev_list, list) and ev_list:
            first = ev_list[0] if isinstance(ev_list[0], dict) else {}
            file_name = escape(str(first.get("file") or "unknown file"))
            line_no = escape(str(first.get("line_start") or first.get("line") or ""))
            match = escape(str(first.get("match") or ""))
            location = file_name if not line_no else f"{file_name}:{line_no}"
            evidence_html = f"<div class='meta'>{location}</div>"
            if match:
                evidence_html += f"<pre>{match}</pre>"
        finding_items.append(
            "<li><strong>{}</strong>{}</li>".format(
                escape(str(finding.get("title") or finding.get("id") or "Finding")),
                evidence_html,
            )
        )
    if not finding_items:
        finding_items.append("<li>No findings.</li>")

    skill_items = []
    if isinstance(skills, list):
        for skill in skills[:20]:
            if not isinstance(skill, dict):
                continue
            skill_items.append(
                "<li><strong>{}</strong> <span>{}</span> <span>{}</span></li>".format(
                    escape(str(skill.get("title") or skill.get("id") or "unknown")),
                    escape(str(skill.get("path") or ".")),
                    escape(_verdict_badge(str((skill.get("verdict") or {}).get("status", "allowed")))),
                )
            )
    if not skill_items:
        skill_items.append("<li>No skills found.</li>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SkillScan Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #0b1020; color: #e5e7eb; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 48px; }}
    .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 14px; padding: 20px; margin-bottom: 16px; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: #1f2937; }}
    h1, h2 {{ margin-top: 0; }}
    ul {{ padding-left: 20px; }}
    li {{ margin-bottom: 12px; }}
    .meta {{ color: #93c5fd; margin-top: 4px; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #030712; padding: 10px; border-radius: 8px; overflow-x: auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>SkillScan Report</h1>
      <p class="badge">{escape(_verdict_badge(verdict_status))}</p>
      <div class="grid">
        <div><strong>Repo</strong><div>{escape(str(source.get("repo") or "local"))}</div></div>
        <div><strong>Commit</strong><div>{escape(str(source.get("commit_sha") or "n/a"))}</div></div>
        <div><strong>Ruleset</strong><div>{escape(str((report.get("scanner") or {}).get("ruleset_version") or "unknown"))}</div></div>
        <div><strong>Skills</strong><div>{len(skills) if isinstance(skills, list) else 0}</div></div>
      </div>
    </section>
    <section class="card">
      <h2>Why</h2>
      <p>{escape(str(verdict.get("reason") or "No extra reason."))}</p>
      <p><strong>Reason code:</strong> {escape(str(verdict.get("reason_code") or "n/a"))}</p>
    </section>
    <section class="card">
      <h2>Top Findings</h2>
      <ul>{''.join(finding_items)}</ul>
    </section>
    <section class="card">
      <h2>Skills</h2>
      <ul>{''.join(skill_items)}</ul>
    </section>
  </main>
</body>
</html>
"""
