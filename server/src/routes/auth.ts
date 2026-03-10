import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import crypto from "crypto";
import { setSession } from "../session.js";
import { buildState, verifyStateSignature } from "../state.js";

const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID ?? "";
const GITHUB_OAUTH_CALLBACK_URL = process.env.GITHUB_OAUTH_CALLBACK_URL ?? "";
const GITHUB_CLIENT_SECRET = process.env.GITHUB_CLIENT_SECRET ?? "";

/** GET /auth/github/start — 跳转 GitHub OAuth 授权页；state 签名防 CSRF */
export async function authRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  app.get("/auth/github/start", async (_req, reply) => {
    const returnTo = (reply.request.query as { return_to?: string }).return_to ?? "/";
    const safeReturnTo = returnTo.startsWith("/") ? returnTo : "/";
    const clientId = GITHUB_CLIENT_ID || "PLACEHOLDER";
    const redirectUri = GITHUB_OAUTH_CALLBACK_URL || "https://example.com/auth/github/callback";
    const nonce = crypto.randomBytes(16).toString("base64url");
    const state = buildState("oauth", undefined, nonce, safeReturnTo);
    const scope = "read:user user:email";
    const url = `https://github.com/login/oauth/authorize?client_id=${encodeURIComponent(clientId)}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${encodeURIComponent(scope)}&state=${encodeURIComponent(state)}`;
    return reply.redirect(url, 302);
  });

  app.get("/auth/github/callback", async (req, reply) => {
    const code = (req.query as { code?: string }).code;
    const stateRaw = (req.query as { state?: string }).state ?? "";
    const payload = verifyStateSignature(stateRaw);
    const returnTo = payload?.returnTo?.startsWith("/") ? payload.returnTo : "/";
    if (!code) {
      return reply.status(401).send({ code: "not_authenticated" as const });
    }
    if (!payload) {
      req.log.warn?.("oauth_state_invalid");
      return reply.redirect(returnTo + "?error=state", 302);
    }
    if (!GITHUB_CLIENT_SECRET) {
      return reply.redirect(returnTo + "?error=config", 302);
    }
    const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: GITHUB_CLIENT_ID,
        client_secret: GITHUB_CLIENT_SECRET,
        code,
        redirect_uri: GITHUB_OAUTH_CALLBACK_URL,
      }),
    });
    if (!tokenRes.ok) {
      req.log.warn?.({ status: tokenRes.status }, "oauth_token_failed");
      return reply.redirect(returnTo + "?error=token", 302);
    }
    const tokenData = (await tokenRes.json()) as { access_token?: string; error?: string };
    const accessToken = tokenData.access_token;
    if (!accessToken) {
      req.log.warn?.({ error: tokenData.error }, "oauth_no_token");
      return reply.redirect(returnTo + "?error=token", 302);
    }
    const userRes = await fetch("https://api.github.com/user", {
      headers: { Authorization: `Bearer ${accessToken}`, Accept: "application/vnd.github+json" },
    });
    if (!userRes.ok) {
      req.log.warn?.({ status: userRes.status }, "github_user_failed");
      return reply.redirect(returnTo + "?error=user", 302);
    }
    const userData = (await userRes.json()) as { id: number; login: string; email?: string | null };
    const githubUserId = userData.id;
    const login = userData.login ?? String(userData.id);
    const email = userData.email ?? null;
    const pool = app.db;
    if (!pool) {
      return reply.redirect(returnTo + "?error=db", 302);
    }
    const upsert = await pool.query<{ id: string }>(
      `INSERT INTO users (id, github_user_id, login, email) VALUES (gen_random_uuid(), $1, $2, $3)
       ON CONFLICT (github_user_id) DO UPDATE SET login = EXCLUDED.login, email = EXCLUDED.email
       RETURNING id`,
      [githubUserId, login, email],
    );
    const userId = upsert.rows[0]?.id;
    if (!userId) {
      return reply.redirect(returnTo + "?error=db", 302);
    }
    setSession(reply, userId);
    return reply.redirect(returnTo, 302);
  });
}
