"""SARIF 2.1.0 output for findings; GitHub Code Scanning / VS Code integration."""
from __future__ import annotations

from typing import Any


def _severity_to_sarif_level(sev: str) -> str:
    s = (sev or "medium").lower()
    if s in ("critical", "high"):
        return "error"
    if s == "medium":
        return "warning"
    return "note"


def report_v1_to_sarif(report: dict[str, Any]) -> dict[str, Any]:
    """Convert report-v1 to SARIF 2.1.0 format."""
    scanner = report.get("scanner") or {}
    source = report.get("source") or {}
    findings = report.get("findings") or []
    ruleset_version = scanner.get("ruleset_version", "unknown")

    rules: list[dict[str, Any]] = []
    rule_ids: set[str] = set()
    for f in findings:
        rid = f.get("id") or f.get("rule_id") or "unknown"
        if rid not in rule_ids:
            rule_ids.add(rid)
            rules.append({
                "id": rid,
                "name": f.get("title") or rid,
                "shortDescription": {"text": (f.get("title") or rid)[:200]},
                "defaultConfiguration": {"level": _severity_to_sarif_level(f.get("severity", "medium"))},
            })

    results: list[dict[str, Any]] = []
    for i, f in enumerate(findings):
        rid = f.get("id") or f.get("rule_id") or "unknown"
        ev_list = f.get("evidence") or []
        if not ev_list:
            loc = {"physicalLocation": {"artifactLocation": {"uri": source.get("repo") or "local"}}}
        else:
            first = ev_list[0] if isinstance(ev_list[0], dict) else {}
            uri = first.get("file") or source.get("repo") or "unknown"
            region = {
                "startLine": first.get("line_start") or first.get("line") or 1,
                "endLine": first.get("line_end") or first.get("line_start") or first.get("line") or 1,
            }
            loc = {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": region,
                }
            }
        results.append({
            "ruleId": rid,
            "message": {"text": (f.get("title") or rid)},
            "locations": [loc],
        })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "skillscan",
                        "version": scanner.get("version", "0.1.0"),
                        "rules": rules,
                        "informationUri": "https://github.com/skillscan/skillscan",
                    }
                },
                "results": results,
                "properties": {
                    "ruleset_version": ruleset_version,
                    "repo": source.get("repo"),
                    "commit_sha": source.get("commit_sha"),
                    "verdict": (report.get("verdict") or {}).get("status"),
                },
            }
        ],
    }
