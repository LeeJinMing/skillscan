import "dotenv/config";
import { assertProductionSecrets } from "./env-check.js";
import { buildApp } from "./app.js";

assertProductionSecrets();
const app = await buildApp({ logger: true });
const host = process.env.HOST ?? "0.0.0.0";
const port = Number(process.env.PORT ?? 3000);
await app.listen({ host, port });
app.log.info({ host, port }, "SkillScan server listening");
