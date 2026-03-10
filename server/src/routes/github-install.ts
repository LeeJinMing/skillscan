import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import crypto from "crypto";
import { insertAudit } from "../audit.js";
import { getClientIp } from "../rate-limit.js";
import { getSessionUserId } from "../session.js";
import { buildState, verifyStateSignature } from "../state.js";
import { getInstallationAccount } from "../github.js";
import type { ErrorBody } from "../types.js";

const APP_INSTALL_URL = process.env.GITHUB_APP_INSTALL_URL ?? "https://github.com/apps/skillscan/installations/new";

/** POST /github/install/start — 发起安装（返回带 state 的 install_url） */
/** POST /github/install/complete — 完成安装绑定 */
export async function githubInstallRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  app.post("/github/install/start", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    const pool = app.db;
    if (!pool) {
      return reply.status(500).send({ code: "internal_error" } satisfies ErrorBody);
    }
    const sid = crypto.randomUUID();
    const nonce = crypto.randomBytes(32).toString("base64url");
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000);
    try {
      await pool.query(
        `INSERT INTO install_sessions (id, user_id, nonce, expires_at) VALUES ($1::uuid, $2::uuid, $3, $4)`,
        [sid, userId, nonce, expiresAt],
      );
    } catch (e) {
      req.log.error?.(e);
      return reply.status(500).send({ code: "internal_error" } satisfies ErrorBody);
    }
    const state = buildState(sid, userId, nonce);
    const installUrl = `${APP_INSTALL_URL}?state=${encodeURIComponent(state)}`;
    return reply.send({ install_url: installUrl });
  });

  app.post("/github/install/complete", async (req, reply) => {
    const body = req.body as { installation_id?: number; setup_action?: string; state?: string };
    if (body?.installation_id == null || !body?.state) {
      return reply.status(400).send({ code: "invalid_request" } satisfies ErrorBody);
    }
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.status(401).send({ code: "not_authenticated" } satisfies ErrorBody);
    }
    const payload = verifyStateSignature(body.state);
    if (!payload) {
      return reply.status(403).send({ code: "state_invalid_or_expired" } satisfies ErrorBody);
    }
    const account = await getInstallationAccount(body.installation_id);
    if (!account) {
      return reply.status(403).send({ code: "state_invalid_or_expired" } satisfies ErrorBody);
    }
    const pool = app.db;
    if (!pool) {
      return reply.status(500).send({ code: "internal_error" } satisfies ErrorBody);
    }
    const client = await pool.connect();
    try {
      await client.query("BEGIN");
      const sessionRow = await client.query(
        `SELECT id, used_at, expires_at FROM install_sessions WHERE id = $1::uuid FOR UPDATE`,
        [payload.sid],
      );
      const row = sessionRow.rows[0];
      if (!row || row.used_at != null || new Date(row.expires_at) <= new Date()) {
        await client.query("ROLLBACK");
        return reply.status(403).send({ code: "state_invalid_or_expired" } satisfies ErrorBody);
      }
      const tenantSel = await client.query(
        `SELECT id, owner_user_id FROM tenants WHERE github_account_id = $1 FOR UPDATE`,
        [String(account.account_id)],
      );
      const existingTenant = tenantSel.rows[0];
      const ip = getClientIp(req);
      const userAgent = (req.headers["user-agent"] as string) ?? "";
      const meta = (tid: string) => ({
        current_user_id: userId,
        github_account_id: account.account_id,
        github_account_login: account.account_login,
        github_account_type: account.account_type,
        installation_id: body.installation_id,
        ip,
        user_agent: userAgent,
      });
      let tenantId: string;
      if (existingTenant) {
        await client.query(
          `INSERT INTO tenant_members (id, tenant_id, user_id, role) VALUES ($1::uuid, $2::uuid, $3::uuid, 'admin')
           ON CONFLICT (tenant_id, user_id) DO NOTHING`,
          [crypto.randomUUID(), existingTenant.id, existingTenant.owner_user_id],
        );
        if (existingTenant.owner_user_id !== userId) {
          await client.query("ROLLBACK");
          await insertAudit(pool, {
            org_id: existingTenant.id,
            actor: userId,
            action: "TENANT_OWNER_CONFLICT",
            target_type: "installation",
            target_id: String(body.installation_id),
            metadata: meta(existingTenant.id),
          });
          return reply.status(403).send({ code: "tenant_owned_by_another_user" } satisfies ErrorBody);
        }
        tenantId = existingTenant.id;
      } else {
        tenantId = crypto.randomUUID();
        await client.query(
          `INSERT INTO tenants (id, github_account_id, github_account_login, github_account_type, owner_user_id)
           VALUES ($1::uuid, $2, $3, $4, $5::uuid)`,
          [tenantId, account.account_id, account.account_login, account.account_type, userId],
        );
        await client.query(
          `INSERT INTO tenant_members (id, tenant_id, user_id, role) VALUES ($1::uuid, $2::uuid, $3::uuid, 'admin')
           ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = 'admin'`,
          [crypto.randomUUID(), tenantId, userId],
        );
      }
      const instSel = await client.query(
        `SELECT tenant_id FROM github_installations WHERE installation_id = $1`,
        [body.installation_id],
      );
      const instRow = instSel.rows[0];
      if (instRow && instRow.tenant_id !== tenantId) {
        await client.query("ROLLBACK");
        await insertAudit(pool, {
          org_id: instRow.tenant_id,
          actor: userId,
          action: "INSTALL_CONFLICT",
          target_type: "installation",
          target_id: String(body.installation_id),
          metadata: meta(instRow.tenant_id),
        });
        return reply.status(409).send({ code: "installation_already_linked" } satisfies ErrorBody);
      }
      if (!instRow) {
        await client.query(
          `INSERT INTO github_installations (installation_id, tenant_id, account_id, account_login, account_type)
           VALUES ($1, $2::uuid, $3, $4, $5)`,
          [
            body.installation_id,
            tenantId,
            account.account_id,
            account.account_login,
            account.account_type,
          ],
        );
      }
      await client.query(`UPDATE install_sessions SET used_at = now() WHERE id = $1::uuid`, [payload.sid]);
      await client.query("COMMIT");
      await insertAudit(pool, {
        org_id: tenantId,
        actor: userId,
        action: "INSTALL_COMPLETED",
        target_type: "installation",
        target_id: String(body.installation_id),
        metadata: meta(tenantId),
      });
    } catch (e) {
      await client.query("ROLLBACK").catch(() => {});
      req.log.error?.(e);
      return reply.status(500).send({ code: "internal_error" } satisfies ErrorBody);
    } finally {
      client.release();
    }
    return reply.send({ ok: true });
  });
}
