import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import multipart from "@fastify/multipart";
import crypto from "crypto";
import pLimit from "p-limit";
import { mkdtemp, rm, writeFile } from "fs/promises";
import path from "path";
import { tmpdir } from "os";
import { extractReportGovernanceFields, findApprovalMatch, resolveFinalVerdict, buildConsoleUrl } from "../governance.js";
import { recordReportsUploaded } from "../metrics.js";
import { applyRateLimitHeaders, checkRateLimit, getClientIp } from "../rate-limit.js";
import { validateReportData, summaryFromReportV1 } from "../report-schema.js";
import { runVerifyScript, sha256Buffer } from "../verify-attestation.js";
import { insertAudit } from "../audit.js";
import type { ErrorBody } from "../types.js";

const SHARE_EXPIRY_DAYS = 7;

/** 从 workflow_ref 解析 workflow_path，如 ".github/workflows/skillscan.yml" */
function parseWorkflowRef(ref: string): { org: string; repo: string; workflow_path: string } | null {
  const m = ref.match(/github\.com\/([^/]+)\/([^/]+)\/(\.github\/workflows\/[^@]+\.yml)/);
  if (m) return { org: m[1], repo: m[2], workflow_path: m[3] };
  const m2 = ref.match(/^([^/]+)\/([^/]+)\/(\.github\/workflows\/[^@]+\.yml)/);
  if (m2) return { org: m2[1], repo: m2[2], workflow_path: m2[3] };
  return null;
}
const REPORTS_RATE_LIMIT_PER_MIN = Number(process.env.REPORTS_RATE_LIMIT_PER_MIN) || 30;
const REPORT_VERIFY_CONCURRENCY = Number(process.env.REPORT_VERIFY_CONCURRENCY) || 3;
const REPORT_VERIFY_TIMEOUT_MS = Number(process.env.REPORT_VERIFY_TIMEOUT_MS) || 20_000;
const SKIP_COSIGN_VERIFY = process.env.SKIP_COSIGN_VERIFY === "1";

const reportVerifyLimit = pLimit(REPORT_VERIFY_CONCURRENCY);

/** POST /reports — 上报 report + attestation_bundle；验签后归属 tenant；identity 来自 attestation 或表单项 repo_full_name（兜底） */
export async function reportsRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  await app.register(multipart, {
    limits: {
      files: 2,
      fileSize: 2 * 1024 * 1024,
    },
  });

  app.post("/reports", async (req, reply) => {
    const ip = getClientIp(req);
    const rateLimit = await checkRateLimit(app.db, `reports:${ip}`, REPORTS_RATE_LIMIT_PER_MIN);
    applyRateLimitHeaders(reply, rateLimit);
    if (!rateLimit.allowed) {
      return reply.status(429).send({ code: "rate_limited" } satisfies ErrorBody);
    }
    const parts = req.parts();
    let reportBuf: Buffer | null = null;
    let bundleBuf: Buffer | null = null;
    let repoFullName: string | null = null;
    for await (const part of parts) {
      if (part.type === "file") {
        if (part.fieldname === "report") {
          const chunks: Buffer[] = [];
          for await (const c of part.file) chunks.push(Buffer.from(c));
          reportBuf = Buffer.concat(chunks);
        } else if (part.fieldname === "attestation_bundle") {
          const chunks: Buffer[] = [];
          for await (const c of part.file) chunks.push(Buffer.from(c));
          bundleBuf = Buffer.concat(chunks);
        } else {
          return reply.status(422).send({ code: "invalid_request" } satisfies ErrorBody);
        }
      } else if (part.fieldname === "repo_full_name" && part.type === "field") {
        const value = part.value;
        repoFullName = typeof value === "string" ? value.trim() || null : null;
      }
    }
    if (!reportBuf || !bundleBuf) {
      return reply.status(422).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    let reportJson: Record<string, unknown>;
    try {
      reportJson = JSON.parse(reportBuf.toString("utf8")) as Record<string, unknown>;
    } catch {
      return reply.status(422).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    if (!validateReportData(reportJson)) {
      return reply.status(422).send({ code: "schema_invalid" } satisfies ErrorBody);
    }
    const v1Summary = summaryFromReportV1(reportJson);
    const governance = extractReportGovernanceFields(reportJson);
    const summary: {
      v: number;
      overall_pass: boolean;
      violations_count: number;
      top_rules: string[];
      commit_sha: string;
      run_url: string | null;
      repo: string;
      verdict_status: string;
      reason_code: string;
    } = v1Summary
      ? { v: 1, ...v1Summary }
      : {
          v: 1,
          overall_pass: (reportJson.overall_pass as boolean) ?? true,
          violations_count: Number(reportJson.violations_count) || 0,
          top_rules: Array.isArray(reportJson.top_rules) ? (reportJson.top_rules as string[]).slice(0, 5) : [],
          commit_sha: governance.commitSha || (typeof reportJson.commit_sha === "string" ? reportJson.commit_sha : ""),
          run_url: typeof reportJson.run_url === "string" ? reportJson.run_url : null,
          repo: governance.repo,
          verdict_status: governance.verdictStatus,
          reason_code: governance.reasonCode,
        };

    const pool = app.db;
    const baseUrl = process.env.PUBLIC_BASE_URL ?? "https://api.skillscan.example.com";
    if (!pool) {
      const reportId = crypto.randomUUID();
      const shareToken = crypto.randomBytes(32).toString("base64url");
      return reply.send({
        scan_id: reportId,
        report_id: reportId,
        share_url: `${baseUrl}/r/${shareToken}`,
        console_url: `${baseUrl}/r/${shareToken}`,
        verdict: {
          status: governance.verdictStatus,
          base_status: governance.verdictStatus,
          reason: governance.verdictReason,
        },
        final_verdict: governance.verdictStatus,
        approval_elevation_applied: false,
        approval_scope_matched: null,
        overall_pass: summary.overall_pass ?? true,
        violations_count: summary.violations_count ?? 0,
      });
    }

    let resolvedRepoFullName: string | null = null;
    let attestationWorkflowRef: string | undefined;
    if (!SKIP_COSIGN_VERIFY && bundleBuf.length > 0) {
      const dir = await mkdtemp(path.join(tmpdir(), "skillscan-"));
      const reportPath = path.join(dir, "report.json");
      const bundlePath = path.join(dir, "bundle");
      try {
        await writeFile(reportPath, reportBuf);
        await writeFile(bundlePath, bundleBuf);
        const verifyResult = await reportVerifyLimit(() =>
          runVerifyScript(reportPath, bundlePath, REPORT_VERIFY_TIMEOUT_MS),
        );
        if (verifyResult.ok) {
          const reportSha256 = sha256Buffer(reportBuf);
          if (reportSha256 !== verifyResult.subjectDigestSha256) {
            await rm(dir, { recursive: true, force: true });
            return reply.status(422).send({ code: "report_digest_mismatch" } satisfies ErrorBody);
          }
          resolvedRepoFullName = verifyResult.predicateRepo;
          attestationWorkflowRef = verifyResult.workflowRef;
        } else {
          await rm(dir, { recursive: true, force: true });
          if (verifyResult.error === "cosign_error") {
            resolvedRepoFullName = repoFullName;
          } else {
            const code = verifyResult.error === "identity_not_allowed" ? "identity_not_allowed" : "invalid_signature";
            return reply.status(401).send({ code } satisfies ErrorBody);
          }
        }
      } finally {
        await rm(dir, { recursive: true, force: true }).catch(() => {});
      }
    }
    if (!resolvedRepoFullName) resolvedRepoFullName = repoFullName;
    if (!resolvedRepoFullName) {
      return reply.status(401).send({ code: "repo_not_enrolled" } satisfies ErrorBody);
    }

    if (attestationWorkflowRef && pool) {
      const parsed = parseWorkflowRef(attestationWorkflowRef);
      if (parsed) {
        const [org, repo] = resolvedRepoFullName.split("/");
        const allowed = await pool.query<{ workflow_path: string }>(
          `SELECT workflow_path FROM allowed_workflows WHERE org = $1 AND repo = $2 AND enabled = true`,
          [org, repo],
        );
        if (allowed.rows.length > 0) {
          const paths = new Set(allowed.rows.map((r) => r.workflow_path));
          if (!paths.has(parsed.workflow_path)) {
            return reply.status(401).send({ code: "workflow_not_allowed" } satisfies ErrorBody);
          }
        }
      }
    }

    if (!governance.repo && resolvedRepoFullName) {
      governance.repo = resolvedRepoFullName;
      summary.repo = resolvedRepoFullName;
    }
    const repoRow = await pool.query<{ repo_id: string; tenant_id: string }>(
      `SELECT r.repo_id, g.tenant_id FROM repos r
       JOIN github_installations g ON r.installation_id = g.installation_id
       WHERE r.full_name = $1 AND r.enabled = true`,
      [resolvedRepoFullName],
    );
    const repo = repoRow.rows[0];
    if (!repo) {
      return reply.status(401).send({ code: "repo_not_enrolled" } satisfies ErrorBody);
    }

    const reportId = crypto.randomUUID();
    const scanId = crypto.randomUUID();
    const shareToken = crypto.randomBytes(32).toString("base64url");
    const shareExpiresAt = new Date(Date.now() + SHARE_EXPIRY_DAYS * 24 * 60 * 60 * 1000);
    await pool.query(
      `INSERT INTO reports (id, tenant_id, repo_id, status, summary, share_token, share_expires_at)
       VALUES ($1::uuid, $2::uuid, $3, 'ok', $4::jsonb, $5, $6)`,
      [reportId, repo.tenant_id, repo.repo_id, JSON.stringify(summary), shareToken, shareExpiresAt],
    );
    const commitSha = governance.commitSha || summary.commit_sha || "";
    const repoName = governance.repo || resolvedRepoFullName || "";
    await pool.query(
      `INSERT INTO scans (
         id, org_id, repo, commit_sha, scanner_version, ruleset_version, policy_version,
         verdict_status, verdict_reason, report_json, skill_paths
       )
       VALUES (
         $1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb
       )`,
      [
        scanId,
        repo.tenant_id,
        repoName,
        commitSha,
        String(((reportJson.scanner as Record<string, unknown> | undefined) ?? {}).version ?? ""),
        String(((reportJson.scanner as Record<string, unknown> | undefined) ?? {}).ruleset_version ?? ""),
        governance.policyVersion || "policy@unknown",
        governance.verdictStatus,
        governance.verdictReason,
        JSON.stringify(reportJson),
        JSON.stringify(governance.skillPaths),
      ],
    );
    await pool.query(
      `INSERT INTO repo_latest_reports (repo_id, report_id, updated_at) VALUES ($1, $2::uuid, now())
       ON CONFLICT (repo_id) DO UPDATE SET report_id = $2::uuid, updated_at = now()`,
      [repo.repo_id, reportId],
    );
    const approval = await findApprovalMatch(pool, repo.tenant_id, repoName, commitSha);
    const finalVerdict = resolveFinalVerdict(governance.verdictStatus, approval);
    await insertAudit(pool, {
      org_id: repo.tenant_id,
      actor: "ci",
      action: "SCAN_CREATED",
      target_type: "scan",
      target_id: scanId,
      metadata: {
        repo: repoName,
        commit_sha: commitSha,
        report_id: reportId,
        base_verdict: governance.verdictStatus,
        final_verdict: finalVerdict.status,
        ...(attestationWorkflowRef && { workflow_ref: attestationWorkflowRef }),
      },
    });
    recordReportsUploaded();
    return reply.send({
      scan_id: scanId,
      report_id: reportId,
      share_url: `${baseUrl}/r/${shareToken}`,
      console_url: buildConsoleUrl(baseUrl, scanId),
      verdict: {
        status: finalVerdict.status,
        base_status: governance.verdictStatus,
        reason: governance.verdictReason,
      },
      final_verdict: finalVerdict.status,
      approval_elevation_applied: finalVerdict.approvalElevationApplied,
      approval_scope_matched: finalVerdict.approvalScopeMatched,
      overall_pass: summary.overall_pass ?? true,
      violations_count: summary.violations_count ?? 0,
    });
  });
}
