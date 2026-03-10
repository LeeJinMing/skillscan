# Data Collection (CLI and upload)

This document lists what the CLI reads, what it includes in reports/attestation, and what would be sent to the service on upload. **We do not upload your full source code.**

## What the CLI reads (local / CI)

- **Skill files** — Under the scan root: SKILL.md / skill.yaml, and content matched by rule file_globs (e.g. `*.md`, `*.sh`, `*.ps1`, `*.py`). Used only to compute findings and a content hash.
- **Source context (optional)** — `repo`, `ref`, `commit_sha`, `default_branch` from CLI args or env (`GOV_REPO` / `GITHUB_REPOSITORY`, `GOV_REF` / `GITHUB_REF`, `GOV_SHA` / `GITHUB_SHA`, etc.). Used only as metadata in the report for traceability.

## What is in report.json (v1 contract)

| Category | Fields | Notes |
|----------|--------|--------|
| **Identity** | `source.provider`, `source.repo`, `source.ref`, `source.commit_sha`, `source.default_branch` | Repo/ref/commit only; no file contents. |
| **Fingerprint** | `input_fingerprint.type`, `input_fingerprint.sha256` | SHA256 of relevant file **contents** (which files are in schema/docs). Not reversible to source. |
| **Skill metadata** | `skill.ecosystem`, `skill.path`, `skill.id`, `skill.title`, `skill.category`, etc. | From frontmatter/metadata; no full body. |
| **Verdict** | `verdict.status`, `verdict.reason_code`, `verdict.policy_version` | Outcome and policy version. |
| **Findings** | `findings[]` with `evidence[]`: `file`, `line_start`, `line_end`, `match` | **Matched line snippets** (e.g. one or a few lines per finding). No full repo upload. |
| **Explanations** | `explanations_top`, `repo_explanation` | Top N findings and repo-level text; may reference same snippets. |
| **Timing** | `timing.started_at`, `timing.finished_at`, `timing.duration_ms` | Scan timing. |

**Default: we do not upload full source.** Only the above metadata, content hash, and **snippets of matched lines** (evidence) are present in the report.

## What is in attestation.json

- `scan_version`, `ruleset_version`, `input_hash`, `commit_sha` (if provided), `generated_at`, optional `report_path`. No source code.

## Example: what would be sent (--dry-run style)

When upload is enabled, the client sends a multipart request to `POST /reports` with:

- `report` = `report.json`
- `attestation_bundle` = `attestation.bundle`
- optional `repo_full_name` for local/dev fallback

A **--dry-run**-style preview of the report payload shape (no real hashes) looks like:

```json
{
  "schema_version": "1.0",
  "contract_version": "2026-02-01",
  "scanner": { "name": "skillscan", "version": "0.1.0", "ruleset_version": "mvp-1", "execution_mode": "suggest_only" },
  "source": { "provider": "github", "repo": "org/repo", "ref": "refs/heads/main", "commit_sha": "<commit_sha>", "default_branch": "main" },
  "input_fingerprint": { "type": "content-hash", "sha256": "<sha256 of relevant file contents>" },
  "skill": { "ecosystem": "clawdbot", "path": "skills/foo/SKILL.md", "id": "my-skill", "title": "My Skill", "category": "" },
  "verdict": { "status": "blocked", "reason": "...", "reason_code": "POLICY_BLOCK_REMOTE_PIPE", "policy_version": "policy@mvp-1" },
  "explanations_mode": "BLOCK_REASONS_ONLY",
  "findings": [ { "id": "BLOCK_REMOTE_PIPE", "evidence": [ { "file": "SKILL.md", "line_start": 10, "line_end": 10, "match": "curl ... | bash" } ] } ],
  "timing": { "started_at": "...", "finished_at": "...", "duration_ms": 123 }
}
```

Running the CLI with **--dry-run** (when implemented) will print this shape and the list of fields/hashes that would be uploaded, without performing the upload.

## Retention and deletion

**Service-side (when using SkillScan server)**:

- Reports and scans are stored in Postgres. Default share links expire after 7 days (`share_expires_at`).
- Retention policy: see `docs/RUNBOOK.md` §6. MVP 建议每个 repo 保留最近 N 条或最近 30 天内。
- Deletion: 删除 reports/scans 前确认 `share_expires_at < now()`，避免破坏有效分享链接。
- Audit log: append-only；按 org 与时间可查询；具体保留时长由部署方策略决定。

**Access control**:

- 未登录用户只能访问带有效 share_token 的分享链接。
- 登录用户按 tenant 隔离；审批、审计仅限本 tenant。

## Summary

- **No full source upload.** Only metadata, content hash, and matched-line snippets (evidence) are in the report.
- **Attestation** contains only version and hash identity, no code.
- **--dry-run** will expose “what would be sent” before any network call (planned).
