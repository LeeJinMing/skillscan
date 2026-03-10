import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import { applyRateLimitHeaders, checkRateLimit, getClientIp } from "../rate-limit.js";

const SHARE_RATE_LIMIT_PER_MIN = Number(process.env.SHARE_RATE_LIMIT_PER_MIN) || 120;

/** GET /r/:share_token — 分享页；404 不存在、410 已过期、200 返回 ReportSummaryV1 或 HTML */
export async function shareRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  app.get<{ Params: { share_token: string } }>("/r/:share_token", async (req, reply) => {
    const ip = getClientIp(req);
    const rateLimit = await checkRateLimit(app.db, `share:${ip}`, SHARE_RATE_LIMIT_PER_MIN);
    applyRateLimitHeaders(reply, rateLimit);
    if (!rateLimit.allowed) {
      return reply.status(429).send();
    }
    const { share_token } = req.params;
    if (!share_token) {
      return reply.status(404).send();
    }
    const pool = app.db;
    if (!pool) {
      return reply.status(404).send();
    }
    const res = await pool.query<{
      summary: { v?: number; overall_pass?: boolean; violations_count?: number; top_rules?: string[]; commit_sha?: string; run_url?: string | null };
      share_expires_at: Date;
    }>(
      `SELECT summary, share_expires_at FROM reports WHERE share_token = $1`,
      [share_token],
    );
    const row = res.rows[0];
    if (!row) return reply.status(404).send();
    if (new Date(row.share_expires_at) <= new Date()) return reply.status(410).send();
    const summary = row.summary ?? {};
    const accept = req.headers.accept ?? "";
    if (accept.includes("application/json")) {
      const out = {
        v: summary.v ?? 1,
        overall_pass: summary.overall_pass ?? true,
        violations_count: summary.violations_count ?? 0,
        top_rules: summary.top_rules ?? [],
        commit_sha: summary.commit_sha ?? "",
        run_url: summary.run_url ?? null,
      };
      return reply.type("application/json").send(out);
    }
    const pass = summary.overall_pass ?? true;
    const violations = summary.violations_count ?? 0;
    const topRules = Array.isArray(summary.top_rules) ? summary.top_rules : [];
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>SkillScan Report</title></head><body style="font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;"><h1>SkillScan Report</h1><p><strong>Status:</strong> ${pass ? "Pass" : "Fail"}</p><p><strong>Violations:</strong> ${violations}</p><p><strong>Commit:</strong> ${summary.commit_sha ?? ""}</p><p><strong>Top rules:</strong> ${topRules.join(", ") || "none"}</p></body></html>`;
    return reply.type("text/html").send(html);
  });
}
