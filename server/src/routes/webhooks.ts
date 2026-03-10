import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import crypto from "crypto";
import { Readable } from "stream";

declare module "fastify" {
  interface FastifyRequest {
    rawBody?: Buffer;
  }
}

/** POST /github/webhooks — 验签 + 幂等（X-GitHub-Delivery）；需 raw body 验签 */
export async function webhooksRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  app.addHook("preParsing", async (request, _reply, payload) => {
    const url = (request as { routerPath?: string }).routerPath ?? request.url;
    if (!url || !String(url).startsWith("/github/webhooks")) return payload;
    const chunks: Buffer[] = [];
    for await (const chunk of payload) chunks.push(Buffer.from(chunk));
    const raw = Buffer.concat(chunks);
    request.rawBody = raw;
    return Readable.from(raw);
  });

  app.post("/github/webhooks", async (req, reply) => {
    const deliveryId = req.headers["x-github-delivery"] as string | undefined;
    const event = req.headers["x-github-event"] as string | undefined;
    const signature = req.headers["x-hub-signature-256"] as string | undefined;

    if (!deliveryId || !event || !signature) {
      return reply.status(401).send();
    }

    const rawBody = req.rawBody;
    if (!rawBody) {
      return reply.status(401).send();
    }

    const secret = process.env.GITHUB_WEBHOOK_SECRET ?? "";
    if (!secret) {
      req.log.warn?.("webhook_secret_not_configured");
      return reply.status(401).send();
    }
    const expected = "sha256=" + crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
    if (expected.length !== signature.length || !crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature))) {
      return reply.status(401).send();
    }

    const pool = app.db;
    if (pool) {
      try {
        const ins = await pool.query(
          `INSERT INTO github_webhook_deliveries (delivery_id, event) VALUES ($1, $2) ON CONFLICT (delivery_id) DO NOTHING`,
          [deliveryId, event],
        );
        if (ins.rowCount === 0) return reply.status(200).send();
      } catch (e) {
        req.log.error?.(e);
        return reply.status(500).send();
      }

      let payload: { action?: string; installation?: { id: number }; repositories_added?: { id: number; full_name: string }[]; repositories_removed?: { id: number; full_name: string }[] };
      try {
        payload = JSON.parse(rawBody.toString("utf8"));
      } catch {
        return reply.status(200).send();
      }

      const installationId = payload?.installation?.id;
      if (installationId != null) {
        const hasInstall = await pool.query(
          `SELECT 1 FROM github_installations WHERE installation_id = $1`,
          [installationId],
        );
        if (hasInstall.rows.length > 0) {
          if (event === "installation" && payload.action === "deleted") {
            await pool.query(`UPDATE repos SET enabled = false, updated_at = now() WHERE installation_id = $1`, [installationId]);
          } else if (event === "installation_repositories") {
            const added = payload.repositories_added ?? [];
            const removed = payload.repositories_removed ?? [];
            for (const r of added) {
              const fullName = r.full_name as string;
              await pool.query(
                `INSERT INTO repos (repo_id, full_name, installation_id, enabled, updated_at)
                 VALUES ($1, $2, $3, true, now())
                 ON CONFLICT (full_name) DO UPDATE SET installation_id = $3, enabled = true, updated_at = now()`,
                [r.id, fullName, installationId],
              );
              const [org, repo] = fullName.split("/");
              if (org && repo) {
                await pool.query(
                  `INSERT INTO allowed_workflows (id, org, repo, workflow_path, enabled, created_by, created_at, updated_at)
                   VALUES (gen_random_uuid(), $1, $2, '.github/workflows/skillscan.yml', true, 'system', now(), now())
                   ON CONFLICT (org, repo, workflow_path) DO UPDATE SET enabled = true, updated_at = now()`,
                  [org, repo],
                );
              }
            }
            for (const r of removed) {
              await pool.query(
                `UPDATE repos SET enabled = false, updated_at = now() WHERE repo_id = $1`,
                [r.id],
              );
            }
          }
        }
      }
    }
    return reply.status(200).send();
  });
}
