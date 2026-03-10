import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import crypto from "crypto";
import { insertAudit } from "../audit.js";
import {
  buildConsoleUrl,
  buildRepoCommitScope,
  extractReportGovernanceFields,
  findApprovalMatch,
  resolveFinalVerdict,
} from "../governance.js";
import { getSessionUserId } from "../session.js";
import type { ErrorBody } from "../types.js";

async function getUserTenantIds(app: FastifyInstance, userId: string): Promise<string[]> {
  const pool = app.db;
  if (!pool) return [];
  const res = await pool.query<{ id: string }>(
    `SELECT id FROM tenants WHERE owner_user_id = $1::uuid
     UNION
     SELECT tenant_id AS id FROM tenant_members WHERE user_id = $1::uuid`,
    [userId],
  );
  return res.rows.map((row) => row.id);
}

async function getUserRoleInTenant(
  app: FastifyInstance,
  userId: string,
  tenantId: string,
): Promise<string | null> {
  const pool = app.db;
  if (!pool) return null;
  const ownerRes = await pool.query<{ owner_user_id: string }>(
    `SELECT owner_user_id FROM tenants WHERE id = $1::uuid`,
    [tenantId],
  );
  if (ownerRes.rows[0]?.owner_user_id === userId) return "admin";
  const memberRes = await pool.query<{ role: string }>(
    `SELECT role FROM tenant_members WHERE tenant_id = $1::uuid AND user_id = $2::uuid`,
    [tenantId, userId],
  );
  return memberRes.rows[0]?.role ?? null;
}

function parsePositiveInt(value: unknown, fallback: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.min(Math.trunc(parsed), max);
}

function ensureDb(app: FastifyInstance, reply: { status: (code: number) => { send: (body: ErrorBody) => unknown } }) {
  if (!app.db) {
    reply.status(503).send({ code: "internal_error" });
    return false;
  }
  return true;
}

/** 扫描/审批/审计主链：/scans /verdict /approve /reject /audit */
export async function governanceRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  app.get("/scans", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    if (!ensureDb(app, reply)) return;
    const tenantIds = await getUserTenantIds(app, userId);
    if (tenantIds.length === 0) return reply.send({ items: [] });
    const q = req.query as { status?: string; limit?: string };
    const statusFilter = (q.status ?? "").trim().toLowerCase();
    const limit = parsePositiveInt(q.limit, 20, 100);
    const values: unknown[] = [tenantIds, limit];
    let where = `WHERE s.org_id = ANY($1::uuid[])`;
    if (statusFilter) {
      values.push(statusFilter);
      where += ` AND s.verdict_status = $3`;
    }
    const res = await app.db!.query<{
      id: string;
      org_id: string;
      repo: string;
      commit_sha: string;
      verdict_status: string;
      verdict_reason: string;
      created_at: Date;
      report_json: Record<string, unknown>;
    }>(
      `SELECT s.id, s.org_id, s.repo, s.commit_sha, s.verdict_status, s.verdict_reason, s.created_at, s.report_json
       FROM scans s
       ${where}
       ORDER BY s.created_at DESC
       LIMIT $2`,
      values,
    );
    const baseUrl = process.env.PUBLIC_BASE_URL ?? "http://localhost:3000";
    const items = [];
    for (const row of res.rows) {
      const approval = await findApprovalMatch(app.db!, row.org_id, row.repo, row.commit_sha);
      const finalVerdict = resolveFinalVerdict(
        extractReportGovernanceFields(row.report_json).verdictStatus,
        approval,
      );
      items.push({
        id: row.id,
        repo: row.repo,
        commit_sha: row.commit_sha,
        verdict: {
          status: finalVerdict.status,
          base_status: row.verdict_status,
          reason: row.verdict_reason,
        },
        approval,
        created_at: new Date(row.created_at).toISOString(),
        console_url: buildConsoleUrl(baseUrl, row.id),
      });
    }
    return reply.send({ items });
  });

  app.get<{ Params: { scan_id: string } }>("/scans/:scan_id", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    if (!ensureDb(app, reply)) return;
    const tenantIds = await getUserTenantIds(app, userId);
    if (tenantIds.length === 0) return reply.status(404).send({ code: "invalid_request" } satisfies ErrorBody);
    const res = await app.db!.query<{
      id: string;
      org_id: string;
      repo: string;
      commit_sha: string;
      verdict_status: string;
      verdict_reason: string;
      report_json: Record<string, unknown>;
      created_at: Date;
    }>(
      `SELECT id, org_id, repo, commit_sha, verdict_status, verdict_reason, report_json, created_at
       FROM scans
       WHERE id = $1::uuid AND org_id = ANY($2::uuid[])
       LIMIT 1`,
      [req.params.scan_id, tenantIds],
    );
    const row = res.rows[0];
    if (!row) return reply.status(404).send({ code: "invalid_request" } satisfies ErrorBody);
    const approval = await findApprovalMatch(app.db!, row.org_id, row.repo, row.commit_sha);
    const finalVerdict = resolveFinalVerdict(
      extractReportGovernanceFields(row.report_json).verdictStatus,
      approval,
    );
    const accept = (req.headers.accept ?? "").toLowerCase();
    const payload = {
      scan_id: row.id,
      repo: row.repo,
      commit_sha: row.commit_sha,
      created_at: new Date(row.created_at).toISOString(),
      verdict: {
        status: finalVerdict.status,
        base_status: row.verdict_status,
        reason: row.verdict_reason,
      },
      approval,
      report: row.report_json,
    };
    if (accept.includes("text/html")) {
      const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>SkillScan Scan</title></head><body style="font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;"><h1>Scan ${row.id}</h1><p><strong>Repo:</strong> ${row.repo}</p><p><strong>Commit:</strong> ${row.commit_sha}</p><p><strong>Final verdict:</strong> ${finalVerdict.status}</p><pre style="white-space:pre-wrap;background:#f6f8fa;padding:1rem;border-radius:8px;">${JSON.stringify(payload, null, 2)}</pre></body></html>`;
      return reply.type("text/html").send(html);
    }
    return reply.send(payload);
  });

  app.get("/approvals", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    if (!ensureDb(app, reply)) return;
    const tenantIds = await getUserTenantIds(app, userId);
    if (tenantIds.length === 0) return reply.send({ items: [] });
    const res = await app.db!.query<{
      id: string;
      org_id: string;
      repo: string;
      commit_sha: string;
      verdict_reason: string;
      created_at: Date;
      report_json: Record<string, unknown>;
    }>(
      `SELECT id, org_id, repo, commit_sha, verdict_reason, created_at, report_json
       FROM scans
       WHERE org_id = ANY($1::uuid[]) AND verdict_status = 'needs_approval'
       ORDER BY created_at DESC
       LIMIT 100`,
      [tenantIds],
    );
    const items = [];
    for (const row of res.rows) {
      const approval = await findApprovalMatch(app.db!, row.org_id, row.repo, row.commit_sha);
      const finalVerdict = resolveFinalVerdict("needs_approval", approval);
      items.push({
        scan_id: row.id,
        repo: row.repo,
        commit_sha: row.commit_sha,
        verdict: finalVerdict.status,
        reason: row.verdict_reason,
        approval,
        created_at: new Date(row.created_at).toISOString(),
      });
    }
    return reply.send({ items });
  });

  app.post("/approve", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    if (!ensureDb(app, reply)) return;
    const body = (req.body ?? {}) as { repo?: string; commit_sha?: string; comment?: string };
    const repo = String(body.repo ?? "").trim();
    const commitSha = String(body.commit_sha ?? "").trim();
    if (!repo || !commitSha) {
      return reply.status(400).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const tenantIds = await getUserTenantIds(app, userId);
    const scanRes = await app.db!.query<{ id: string; org_id: string; report_json: Record<string, unknown> }>(
      `SELECT id, org_id, report_json
       FROM scans
       WHERE org_id = ANY($1::uuid[]) AND repo = $2 AND commit_sha = $3
       ORDER BY created_at DESC
       LIMIT 1`,
      [tenantIds, repo, commitSha],
    );
    const scan = scanRes.rows[0];
    if (!scan) {
      return reply.status(404).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const role = await getUserRoleInTenant(app, userId, scan.org_id);
    if (role !== "admin" && role !== "approver") {
      return reply.status(403).send({ code: "forbidden" } satisfies ErrorBody);
    }
    const scope = buildRepoCommitScope(repo, commitSha);
    const approvalId = crypto.randomUUID();
    const comment = body.comment ? String(body.comment) : null;
    const approvalRes = await app.db!.query<{ id: string; decided_at: Date }>(
      `INSERT INTO approvals (id, org_id, scope_type, scope_key, repo, commit_sha, skill_path, status, decided_by, comment)
       VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, null, 'approved', $7, $8)
       ON CONFLICT (org_id, scope_type, scope_key, commit_sha)
       DO UPDATE SET status = 'approved', decided_by = EXCLUDED.decided_by, decided_at = now(), comment = EXCLUDED.comment
       RETURNING id, decided_at`,
      [approvalId, scan.org_id, scope.type, scope.key, repo, commitSha, userId, comment],
    );
    await insertAudit(app.db!, {
      org_id: scan.org_id,
      actor: userId,
      action: "APPROVED_BY_USER",
      target_type: "approval",
      target_id: approvalRes.rows[0]?.id ?? approvalId,
      metadata: { repo, commit_sha: commitSha, scope },
    });
    return reply.send({
      ok: true,
      approval_id: approvalRes.rows[0]?.id ?? approvalId,
      scope,
      verdict: resolveFinalVerdict(
        extractReportGovernanceFields(scan.report_json).verdictStatus,
        {
          id: approvalRes.rows[0]?.id ?? approvalId,
          status: "approved",
          comment,
          decided_at: new Date(approvalRes.rows[0]?.decided_at ?? new Date()).toISOString(),
          decided_by: userId,
          scope,
        },
      ).status,
    });
  });

  app.post("/reject", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    if (!ensureDb(app, reply)) return;
    const body = (req.body ?? {}) as { repo?: string; commit_sha?: string; comment?: string };
    const repo = String(body.repo ?? "").trim();
    const commitSha = String(body.commit_sha ?? "").trim();
    if (!repo || !commitSha) {
      return reply.status(400).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const tenantIds = await getUserTenantIds(app, userId);
    const scanRes = await app.db!.query<{ id: string; org_id: string }>(
      `SELECT id, org_id
       FROM scans
       WHERE org_id = ANY($1::uuid[]) AND repo = $2 AND commit_sha = $3
       ORDER BY created_at DESC
       LIMIT 1`,
      [tenantIds, repo, commitSha],
    );
    const scan = scanRes.rows[0];
    if (!scan) {
      return reply.status(404).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const role = await getUserRoleInTenant(app, userId, scan.org_id);
    if (role !== "admin" && role !== "approver") {
      return reply.status(403).send({ code: "forbidden" } satisfies ErrorBody);
    }
    const scope = buildRepoCommitScope(repo, commitSha);
    const approvalId = crypto.randomUUID();
    const comment = body.comment ? String(body.comment) : null;
    const approvalRes = await app.db!.query<{ id: string }>(
      `INSERT INTO approvals (id, org_id, scope_type, scope_key, repo, commit_sha, skill_path, status, decided_by, comment)
       VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, null, 'rejected', $7, $8)
       ON CONFLICT (org_id, scope_type, scope_key, commit_sha)
       DO UPDATE SET status = 'rejected', decided_by = EXCLUDED.decided_by, decided_at = now(), comment = EXCLUDED.comment
       RETURNING id`,
      [approvalId, scan.org_id, scope.type, scope.key, repo, commitSha, userId, comment],
    );
    await insertAudit(app.db!, {
      org_id: scan.org_id,
      actor: userId,
      action: "REJECTED_BY_USER",
      target_type: "approval",
      target_id: approvalRes.rows[0]?.id ?? approvalId,
      metadata: { repo, commit_sha: commitSha, scope },
    });
    return reply.send({ ok: true, approval_id: approvalRes.rows[0]?.id ?? approvalId, scope, verdict: "needs_approval" });
  });

  app.get("/verdict", async (req, reply) => {
    if (!ensureDb(app, reply)) return;
    const q = req.query as { repo?: string; commit_sha?: string };
    const repo = String(q.repo ?? "").trim();
    const commitSha = String(q.commit_sha ?? "").trim();
    if (!repo || !commitSha) {
      return reply.status(400).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const scanRes = await app.db!.query<{
      id: string;
      org_id: string;
      verdict_status: string;
      verdict_reason: string;
      report_json: Record<string, unknown>;
    }>(
      `SELECT id, org_id, verdict_status, verdict_reason, report_json
       FROM scans
       WHERE repo = $1 AND commit_sha = $2
       ORDER BY created_at DESC
       LIMIT 1`,
      [repo, commitSha],
    );
    const scan = scanRes.rows[0];
    if (!scan) {
      return reply.status(404).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const approval = await findApprovalMatch(app.db!, scan.org_id, repo, commitSha);
    const finalVerdict = resolveFinalVerdict(
      extractReportGovernanceFields(scan.report_json).verdictStatus,
      approval,
    );
    return reply.send({
      scan_id: scan.id,
      repo,
      commit_sha: commitSha,
      verdict: {
        status: finalVerdict.status,
        base_status: scan.verdict_status,
        reason: scan.verdict_reason,
      },
      approval_elevation_applied: finalVerdict.approvalElevationApplied,
      approval_scope_matched: finalVerdict.approvalScopeMatched,
    });
  });

  app.post<{ Params: { approval_id: string } }>("/approvals/:approval_id/revoke", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    if (!ensureDb(app, reply)) return;
    const approvalId = req.params.approval_id;
    const res = await app.db!.query<{ org_id: string }>(
      `SELECT org_id FROM approvals WHERE id = $1::uuid AND status = 'approved' AND revoked_at IS NULL`,
      [approvalId],
    );
    const row = res.rows[0];
    if (!row) {
      return reply.status(404).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const role = await getUserRoleInTenant(app, userId, row.org_id);
    if (role !== "admin" && role !== "approver") {
      return reply.status(403).send({ code: "forbidden" } satisfies ErrorBody);
    }
    await app.db!.query(
      `UPDATE approvals SET revoked_at = now() WHERE id = $1::uuid`,
      [approvalId],
    );
    await insertAudit(app.db!, {
      org_id: row.org_id,
      actor: userId,
      action: "APPROVAL_REVOKED",
      target_type: "approval",
      target_id: approvalId,
      metadata: {},
    });
    return reply.send({ ok: true });
  });

  app.get("/audit", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    if (!ensureDb(app, reply)) return;
    const tenantIds = await getUserTenantIds(app, userId);
    if (tenantIds.length === 0) return reply.send({ items: [] });
    const limit = parsePositiveInt((req.query as { limit?: string }).limit, 50, 200);
    const res = await app.db!.query<{
      id: string;
      org_id: string;
      actor: string;
      action: string;
      target_type: string;
      target_id: string;
      created_at: Date;
      metadata: Record<string, unknown>;
    }>(
      `SELECT id, org_id, actor, action, target_type, target_id, created_at, metadata
       FROM audit_log
       WHERE org_id = ANY($1::uuid[])
       ORDER BY created_at DESC
       LIMIT $2`,
      [tenantIds, limit],
    );
    return reply.send({
      items: res.rows.map((row) => ({
        ...row,
        created_at: new Date(row.created_at).toISOString(),
      })),
    });
  });
}
