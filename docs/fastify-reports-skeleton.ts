/**
 * POST /reports 实现骨架（Fastify + TS）
 * 重点：资源控制（大小限制、流式落盘、cosign 超时/并发、临时目录清理），不是业务逻辑。
 * 配套：Dockerfile 固定 cosign 版本；scripts/verify.sh 把 cosign 参数定死并覆盖测试；服务端只调该脚本。
 */

import Fastify from "fastify";
import multipart from "@fastify/multipart";
import { createHash } from "crypto";
import { mkdtemp, rm } from "fs/promises";
import { createWriteStream } from "fs";
import { pipeline } from "stream/promises";
import { tmpdir } from "os";
import path from "path";
import { spawn } from "child_process";
import pLimit from "p-limit";

const app = Fastify({ logger: true });

app.register(multipart, {
  limits: {
    files: 2,
    fileSize: 2 * 1024 * 1024, // 2MB 先保守，后面按真实 report 大小调；上传必须有大小限制，否则内存/磁盘爆
  },
});

const verifyLimit = pLimit(3); // 每个实例同时最多 3 个 cosign 验签；cosign 并发必须限

function sha256File(filepath: string): Promise<string> {
  // MVP：可先 readFile；更稳是流式 hash（避免大文件）
  // 实际写成流式：createReadStream -> pipe to Hash
  throw new Error("implement");
}

function runCosignVerify(args: string[], timeoutMs = 20_000): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const p = spawn("cosign", args, { stdio: ["ignore", "pipe", "pipe"] });

    let stdout = "";
    let stderr = "";
    p.stdout.on("data", (d) => (stdout += d.toString("utf8")));
    p.stderr.on("data", (d) => (stderr += d.toString("utf8")));

    const t = setTimeout(() => {
      p.kill("SIGKILL"); // cosign 子进程必须有超时 + kill，否则拖死 worker
      reject(Object.assign(new Error("cosign_timeout"), { stderr }));
    }, timeoutMs);

    p.on("error", (e) => {
      clearTimeout(t);
      reject(e);
    });
    p.on("close", (code) => {
      clearTimeout(t);
      if (code !== 0) {
        reject(Object.assign(new Error("cosign_failed"), { code, stderr, stdout }));
      } else {
        resolve({ stdout, stderr });
      }
    });
  });
}

app.post("/reports", async (req, reply) => {
  const dir = await mkdtemp(path.join(tmpdir(), "skillscan-"));
  const cleanup = async () => rm(dir, { recursive: true, force: true }); // 临时目录必须 finally 清理

  try {
    const parts = req.parts();
    let reportPath: string | null = null;
    let bundlePath: string | null = null;

    for await (const part of parts) {
      if (part.type !== "file") continue;
      // 必须流式落盘，不要把 report/bundle 全读进内存
      if (part.fieldname === "report") {
        reportPath = path.join(dir, "report.json");
        await pipeline(part.file, createWriteStream(reportPath));
      } else if (part.fieldname === "attestation_bundle") {
        bundlePath = path.join(dir, "attestation.bundle");
        await pipeline(part.file, createWriteStream(bundlePath));
      } else {
        return reply.code(422).send({ error: "unknown_field" });
      }
    }

    if (!reportPath || !bundlePath) {
      return reply.code(422).send({ error: "missing_files" });
    }

    const reportSha256 = await sha256File(reportPath);

    const { stdout } = await verifyLimit(async () => {
      // B 绑定：从 DB 查该 token/org 允许的 (org/repo/workflow_path)，拼 identity regex：
      // ^https://github\.com/<org>/<repo>/\.github/workflows/<workflow>\.yml@
      // cosign 参数随版本强绑定 → 固定 cosign 版本（Dockerfile）+ scripts/verify.sh 把参数定死并覆盖测试，服务端只调该脚本
      const args = [/* 示例：verify bundle + issuer + identity 约束，见 scripts/verify.sh */];
      return runCosignVerify(args, 20_000);
    });

    // 从 stdout 解析 in-toto statement，拿 subject.digest.sha256
    // const statement = JSON.parse(stdout); const attestedSha = statement.subject[0].digest.sha256;
    const attestedSha = "TODO";
    if (attestedSha !== reportSha256) {
      return reply.code(422).send({ error: "report_digest_mismatch" });
    }

    // allowlist 校验（repo + workflow_path）——必须命中，否则 401
    // schema 校验 report.json（ajv）
    // 入库 + 生成 console_url；report + bundle 至少要能存到 S3/R2（本地盘不可靠）
    return reply.send({
      report_id: "rpt_...",
      final_verdict: "needs_approval",
      approval_elevation_applied: false,
      console_url: "https://console.skillscan.example.com/reports/rpt_...",
    });
  } catch (e: any) {
    req.log.error({ err: e }, "ingest_failed");
    if (e?.message === "cosign_timeout") return reply.code(401).send({ error: "invalid_signature" });
    if (e?.message === "cosign_failed") return reply.code(401).send({ error: "invalid_signature" });
    return reply.code(500).send({ error: "internal_error" });
  } finally {
    await cleanup();
  }
});

app.listen({ host: "0.0.0.0", port: 3000 });
