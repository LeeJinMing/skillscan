/**
 * P0 路由契约测试：状态码与 body 符合 OpenAPI。
 * 运行：npm test
 */
import { describe, it } from "node:test";
import assert from "node:assert";
import crypto from "crypto";

process.env.SKIP_COSIGN_VERIFY = "1";
const { buildApp } = await import("../src/app.js");
const app = await buildApp({ logger: false });

function multipartBody(fields: Record<string, string>, files: Array<{ name: string; filename: string; contentType: string; content: string }>) {
  const boundary = "----skillscan-test-boundary";
  const parts: string[] = [];
  for (const [key, value] of Object.entries(fields)) {
    parts.push(`--${boundary}\r\nContent-Disposition: form-data; name="${key}"\r\n\r\n${value}\r\n`);
  }
  for (const file of files) {
    parts.push(
      `--${boundary}\r\nContent-Disposition: form-data; name="${file.name}"; filename="${file.filename}"\r\nContent-Type: ${file.contentType}\r\n\r\n${file.content}\r\n`,
    );
  }
  parts.push(`--${boundary}--\r\n`);
  return { boundary, payload: parts.join("") };
}

describe("P0 routes", () => {

  describe("GET /auth/github/start", () => {
    it("returns 302 redirect to GitHub OAuth", async () => {
      const res = await app.inject({ method: "GET", url: "/auth/github/start" });
      assert.strictEqual(res.statusCode, 302);
      assert.ok(res.headers.location?.startsWith("https://github.com/login/oauth/authorize"));
    });
  });

  describe("GET /auth/github/callback", () => {
    it("returns 401 when code missing", async () => {
      const res = await app.inject({ method: "GET", url: "/auth/github/callback" });
      assert.strictEqual(res.statusCode, 401);
      const body = res.json() as { code?: string };
      assert.strictEqual(body.code, "not_authenticated");
    });
  });

  describe("POST /github/install/start", () => {
    it("returns 401 when not authenticated (no session)", async () => {
      const res = await app.inject({ method: "POST", url: "/github/install/start" });
      assert.strictEqual(res.statusCode, 401);
      const body = res.json() as { code?: string };
      assert.strictEqual(body.code, "not_authenticated");
    });
  });

  describe("POST /github/install/complete", () => {
    it("returns 401 when not authenticated", async () => {
      const res = await app.inject({
        method: "POST",
        url: "/github/install/complete",
        payload: { installation_id: 123, state: "x" },
      });
      assert.strictEqual(res.statusCode, 401);
    });
    it("returns 400 when installation_id or state missing", async () => {
      const res = await app.inject({
        method: "POST",
        url: "/github/install/complete",
        payload: {},
      });
      assert.strictEqual(res.statusCode, 400);
      const body = res.json() as { code?: string };
      assert.strictEqual(body.code, "invalid_request");
    });
  });

  describe("POST /github/webhooks", () => {
    it("returns 401 when signature headers missing", async () => {
      const res = await app.inject({
        method: "POST",
        url: "/github/webhooks",
        payload: {},
      });
      assert.strictEqual(res.statusCode, 401);
    });
    it("returns 200 when valid signature (configured secret)", async () => {
      const secret = "test_webhook_secret_min_32_chars_for_ci";
      process.env.GITHUB_WEBHOOK_SECRET = secret;
      const body = JSON.stringify({ action: "created" });
      const sig = "sha256=" + crypto.createHmac("sha256", secret).update(body).digest("hex");
      const res = await app.inject({
        method: "POST",
        url: "/github/webhooks",
        headers: {
          "content-type": "application/json",
          "x-github-delivery": "test-delivery-id",
          "x-github-event": "installation",
          "x-hub-signature-256": sig,
        },
        payload: body,
      });
      assert.strictEqual(res.statusCode, 200);
    });
  });

  describe("POST /reports", () => {
    it("returns 4xx when content-type is not multipart (406 or 422)", async () => {
      const res = await app.inject({
        method: "POST",
        url: "/reports",
        headers: { "content-type": "application/json" },
        payload: {},
      });
      assert.ok(res.statusCode >= 400 && res.statusCode < 500, "expect 4xx for wrong content-type or missing files");
    });
    it("returns 200 with scan_id, verdict, and URLs when multipart payload is valid", async () => {
      const report = {
        schema_version: "1.0",
        scanner: { name: "skillscan", version: "0.1.0", ruleset_version: "2026-02-01", execution_mode: "suggest_only" },
        source: { provider: "github", repo: "demo/repo", ref: "refs/heads/main", commit_sha: "abc123", default_branch: "main" },
        input_fingerprint: { type: "content-hash", sha256: "abc" },
        skill: { ecosystem: "clawdbot", path: "", id: "demo", author: "", declared_version: "1.0", title: "Demo", category: "" },
        verdict: { status: "needs_approval", reason: "demo reason", reason_code: "REQUIRES_APPROVAL_HIGH_RISK_SIGNALS", policy_version: "policy@2026-02-01" },
        capabilities: {},
        findings: [{ id: "APPROVAL_NETWORK" }],
        skills: [{ path: "skills/demo/SKILL.md", id: "demo", category: "devops", verdict: { status: "needs_approval" } }],
        timing: { started_at: "2026-02-01T00:00:00Z", finished_at: "2026-02-01T00:00:01Z", duration_ms: 1000 },
      };
      const { boundary, payload } = multipartBody(
        { repo_full_name: "demo/repo" },
        [
          {
            name: "report",
            filename: "report.json",
            contentType: "application/json",
            content: JSON.stringify(report),
          },
          {
            name: "attestation_bundle",
            filename: "attestation.bundle",
            contentType: "application/json",
            content: JSON.stringify({}),
          },
        ],
      );
      const res = await app.inject({
        method: "POST",
        url: "/reports",
        headers: { "content-type": `multipart/form-data; boundary=${boundary}` },
        payload,
      });
      assert.strictEqual(res.statusCode, 200);
      const body = res.json() as {
        scan_id?: string;
        report_id?: string;
        share_url?: string;
        console_url?: string;
        final_verdict?: string;
        verdict?: { status?: string; base_status?: string };
      };
      assert.ok(body.scan_id);
      assert.ok(body.report_id);
      assert.ok(body.share_url?.includes("/r/"));
      assert.ok(body.console_url);
      assert.strictEqual(body.final_verdict, "needs_approval");
      assert.strictEqual(body.verdict?.status, "needs_approval");
    });
  });

  describe("GET /r/:share_token", () => {
    it("returns 404 when token does not exist", async () => {
      const res = await app.inject({ method: "GET", url: "/r/nonexistent_token_123" });
      assert.strictEqual(res.statusCode, 404);
    });
    it("returns 404 for unknown token with Accept: application/json", async () => {
      const res = await app.inject({
        method: "GET",
        url: "/r/any",
        headers: { accept: "application/json" },
      });
      assert.strictEqual(res.statusCode, 404);
    });
  });

  describe("Ops and governance routes", () => {
    it("returns 200 on /healthz", async () => {
      const res = await app.inject({ method: "GET", url: "/healthz" });
      assert.strictEqual(res.statusCode, 200);
      assert.strictEqual((res.json() as { ok?: boolean }).ok, true);
    });

    it("returns 200 on /readyz", async () => {
      const res = await app.inject({ method: "GET", url: "/readyz" });
      assert.strictEqual(res.statusCode, 200);
    });

    it("returns metrics text on /metrics", async () => {
      const res = await app.inject({ method: "GET", url: "/metrics" });
      assert.strictEqual(res.statusCode, 200);
      assert.ok(res.body.includes("skillscan_requests_total"));
    });

    it("returns 401 for /scans when not authenticated", async () => {
      const res = await app.inject({ method: "GET", url: "/scans" });
      assert.strictEqual(res.statusCode, 401);
    });

    it("returns 401 for /approvals when not authenticated", async () => {
      const res = await app.inject({ method: "GET", url: "/approvals" });
      assert.strictEqual(res.statusCode, 401);
    });
  });
});
