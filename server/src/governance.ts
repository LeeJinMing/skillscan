import type { Pool } from "pg";

export type VerdictStatus = "allowed" | "needs_approval" | "approved" | "blocked";
export type ApprovalStatus = "approved" | "rejected";

export interface ApprovalScope {
  type: "repo_commit";
  key: string;
  commit_sha: string;
}

export interface ApprovalMatch {
  id: string;
  status: ApprovalStatus;
  comment: string | null;
  decided_at: string;
  decided_by: string;
  scope: ApprovalScope;
}

export interface ReportGovernanceFields {
  repo: string;
  commitSha: string;
  verdictStatus: VerdictStatus;
  verdictReason: string;
  reasonCode: string;
  policyVersion: string;
  skillPaths: Array<{ path: string; id: string; category: string; verdict: string }>;
}

function normalizeVerdictStatus(value: unknown): VerdictStatus {
  const status = String(value ?? "").trim().toLowerCase();
  if (status === "blocked") return "blocked";
  if (status === "needs_approval") return "needs_approval";
  if (status === "approved") return "approved";
  return "allowed";
}

export function buildRepoCommitScope(repo: string, commitSha: string): ApprovalScope {
  return {
    type: "repo_commit",
    key: `repo=${repo}`,
    commit_sha: commitSha,
  };
}

export function extractReportGovernanceFields(report: Record<string, unknown>): ReportGovernanceFields {
  const source = (report.source ?? {}) as { repo?: string; commit_sha?: string };
  const verdict = (report.verdict ?? {}) as {
    status?: string;
    reason?: string;
    reason_code?: string;
    policy_version?: string;
  };
  const skillsRaw = Array.isArray(report.skills) ? report.skills : [];
  const skillPaths = skillsRaw
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      path: String(item.path ?? ""),
      id: String(item.id ?? ""),
      category: String(item.category ?? ""),
      verdict: String(((item.verdict as Record<string, unknown> | undefined) ?? {}).status ?? ""),
    }));
  return {
    repo: String(source.repo ?? ""),
    commitSha: String(source.commit_sha ?? ""),
    verdictStatus: normalizeVerdictStatus(verdict.status),
    verdictReason: String(verdict.reason ?? ""),
    reasonCode: String(verdict.reason_code ?? ""),
    policyVersion: String(verdict.policy_version ?? ""),
    skillPaths,
  };
}

export function resolveFinalVerdict(
  baseVerdict: VerdictStatus,
  approval: ApprovalMatch | null,
): {
  status: VerdictStatus;
  approvalElevationApplied: boolean;
  approvalScopeMatched: ApprovalScope | null;
} {
  if (baseVerdict === "needs_approval" && approval?.status === "approved") {
    return {
      status: "approved",
      approvalElevationApplied: true,
      approvalScopeMatched: approval.scope,
    };
  }
  return {
    status: baseVerdict,
    approvalElevationApplied: false,
    approvalScopeMatched: approval?.scope ?? null,
  };
}

export async function findApprovalMatch(
  pool: Pool,
  orgId: string,
  repo: string,
  commitSha: string,
): Promise<ApprovalMatch | null> {
  if (!repo || !commitSha) return null;
  const scope = buildRepoCommitScope(repo, commitSha);
  const res = await pool.query<{
    id: string;
    status: ApprovalStatus;
    comment: string | null;
    decided_at: Date;
    decided_by: string;
    expires_at: Date | null;
  }>(
    `SELECT id, status, comment, decided_at, decided_by, expires_at
     FROM approvals
     WHERE org_id = $1::uuid AND scope_type = $2 AND scope_key = $3 AND commit_sha = $4
       AND (expires_at IS NULL OR expires_at > now())
       AND revoked_at IS NULL
     ORDER BY decided_at DESC
     LIMIT 1`,
    [orgId, scope.type, scope.key, scope.commit_sha],
  );
  const row = res.rows[0];
  if (!row) return null;
  return {
    id: row.id,
    status: row.status,
    comment: row.comment,
    decided_at: new Date(row.decided_at).toISOString(),
    decided_by: row.decided_by,
    scope,
  };
}

export function buildConsoleUrl(baseUrl: string, scanId: string): string {
  return `${baseUrl.replace(/\/+$/, "")}/scans/${scanId}`;
}
