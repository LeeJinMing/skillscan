import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import { metricsSnapshot, metricsText } from "../metrics.js";
import { reportSchemaStatus } from "../report-schema.js";

export async function opsRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  app.get("/healthz", async (_req, reply) => {
    return reply.send({ ok: true, service: "skillscan-server" });
  });

  app.get("/readyz", async (_req, reply) => {
    const schema = reportSchemaStatus();
    const hasDb = !!app.db;
    let dbOk = false;
    if (hasDb && app.db) {
      try {
        await app.db.query("SELECT 1");
        dbOk = true;
      } catch {
        dbOk = false;
      }
    }
    const ok = !hasDb || dbOk;
    const payload = {
      ok,
      mode: hasDb ? "database" : "demo",
      database: hasDb ? (dbOk ? "connected" : "unreachable") : "disabled",
      report_schema: schema,
    };
    return reply.status(ok ? 200 : 503).send(payload);
  });

  app.get("/metrics", async (_req, reply) => {
    const snapshot = metricsSnapshot();
    reply.header("Content-Type", "text/plain; version=0.0.4; charset=utf-8");
    return reply.send(metricsText() + `# db_configured ${app.db ? 1 : 0}\n`);
  });
}
