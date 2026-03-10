import Fastify from "fastify";
import cookie from "@fastify/cookie";
import { getPool } from "./db.js";
import { loadReportSchema } from "./report-schema.js";
import { authRoutes } from "./routes/auth.js";
import { governanceRoutes } from "./routes/governance.js";
import { githubInstallRoutes } from "./routes/github-install.js";
import { recordRequest } from "./metrics.js";
import { opsRoutes } from "./routes/ops.js";
import { webhooksRoutes } from "./routes/webhooks.js";
import { reportsRoutes } from "./routes/reports.js";
import { shareRoutes } from "./routes/share.js";
import { consoleRoutes } from "./routes/console.js";

/** 构建 Fastify 实例（不 listen），供测试与入口复用 */
export async function buildApp(opts?: { logger?: boolean }) {
  const app = Fastify({ logger: opts?.logger ?? true });
  await app.register(cookie, { secret: process.env.SESSION_SECRET ?? "dev" });
  app.decorate("db", getPool());
  await loadReportSchema();
  app.addHook("onRequest", (_request, _reply, done) => {
    recordRequest();
    done();
  });
  app.addHook("onResponse", (request, reply, done) => {
    if (reply.statusCode >= 400) {
      request.log.info?.(
        {
          statusCode: reply.statusCode,
          method: request.method,
          url: request.url,
        },
        "response_error"
      );
    }
    done();
  });
  app.get("/", (req, reply) => {
    const accept = (req.headers.accept ?? "").toLowerCase();
    const q = req.query as { format?: string };
    const wantsJson =
      accept.includes("application/json") || q.format === "json";
    if (wantsJson) {
      return reply.send({
        service: "SkillScan API",
        version: "1.0",
        docs: "api/openapi.yaml",
        paths: [
          "/healthz",
          "/readyz",
          "/metrics",
          "/auth/github/start",
          "/auth/github/callback",
          "/github/install/start",
          "/github/install/complete",
          "/github/webhooks",
          "/reports",
          "/r/:share_token",
          "/scans",
          "/scans/:scan_id",
          "/approvals",
          "/approve",
          "/reject",
          "/verdict",
          "/audit",
        ],
      });
    }
    if (accept.includes("text/html")) {
      const base = `${req.protocol}://${
        req.headers.host ?? req.hostname ?? "localhost:3001"
      }`;
      const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SkillScan API</title></head>
<body style="font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;">
  <h1>SkillScan API</h1>
  <p>这是后端 API 服务，不是完整 Web 界面。浏览器里看到本页说明服务已启动。</p>
  <h2>如何使用</h2>
  <ol style="line-height:1.6;">
    <li><strong>健康检查</strong>：打开 <a href="${base}/healthz">/healthz</a> 看服务是否存活，<a href="${base}/readyz">/readyz</a> 看当前是 demo 还是 DB 模式。</li>
    <li><strong>登录</strong>：打开 <a href="${base}/auth/github/start">/auth/github/start</a> 会跳转到 GitHub OAuth（需先配置 OAuth 与 DB）。</li>
    <li><strong>安装 GitHub App</strong>：登录后，前端调用 POST /github/install/start 拿到安装链接，用户在 GitHub 选仓库并安装，再 POST /github/install/complete 完成绑定。</li>
    <li><strong>CI 上报</strong>：在仓库里配置 <code>.github/workflows/skillscan.yml</code>，跑完后向本服务 POST /reports（report.json + attestation_bundle），返回 share_url。</li>
    <li><strong>查看结果</strong>：打开返回的 share_url（形如 /r/xxx），或登录后进入 <a href="${base}/console">Web 控制台</a>（扫描/审批/审计）。</li>
  </ol>
  <p>本地未配数据库时：install/start 会 500，share 会 404，reports 返回占位。配好 <code>DATABASE_URL</code> 并执行 <code>docs/postgres-schema.sql</code> 后可跑完整流程。详见仓库 <code>docs/WHEN-TO-PROVIDE-KEYS.md</code>。</p>
  <p><a href="${base}/?format=json">查看 JSON 接口列表</a></p>
</body></html>`;
      return reply.type("text/html").send(html);
    }
    return reply.send({
      service: "SkillScan API",
      version: "1.0",
      docs: "api/openapi.yaml",
      paths: [
          "/healthz",
          "/readyz",
          "/metrics",
        "/auth/github/start",
        "/auth/github/callback",
        "/github/install/start",
        "/github/install/complete",
        "/github/webhooks",
        "/reports",
        "/r/:share_token",
          "/scans",
          "/scans/:scan_id",
          "/approvals",
          "/approve",
          "/reject",
          "/verdict",
          "/audit",
      ],
    });
  });
  // 浏览器/PWA 常请求 /sw.js；API 不提供 SW，返回空 no-op 避免 404 刷日志
  app.get("/sw.js", (_req, reply) => {
    return reply
      .type("application/javascript")
      .send("self.addEventListener('fetch',()=>{});");
  });
  await app.register(opsRoutes);
  await app.register(authRoutes);
  await app.register(githubInstallRoutes);
  await app.register(webhooksRoutes);
  await app.register(reportsRoutes);
  await app.register(shareRoutes);
  await app.register(governanceRoutes);
  await app.register(consoleRoutes);
  return app;
}
