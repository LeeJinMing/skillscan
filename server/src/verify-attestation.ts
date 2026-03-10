/**
 * 验签脚本调用 + bundle 解析（取 subject digest、predicate.repo）。
 * 脚本 stdout 固定 JSON：{ ok: true } | { ok: false, error: string }
 */
import { spawn } from "child_process";
import { createHash } from "crypto";
import { readFile } from "fs/promises";
import path from "path";

const DEFAULT_SCRIPT = path.join(process.cwd(), "scripts", "verify-attestation.sh");

export interface VerifyResult {
  ok: true;
  subjectDigestSha256: string;
  predicateRepo: string;
  workflowRef?: string;
}

export interface VerifyFailure {
  ok: false;
  error: string;
}

/** 运行验签脚本；超时或非 0 退出返回 VerifyFailure */
export function runVerifyScript(
  reportPath: string,
  bundlePath: string,
  timeoutMs: number,
  scriptPath: string = process.env.COSIGN_VERIFY_SCRIPT ?? DEFAULT_SCRIPT,
): Promise<VerifyResult | VerifyFailure> {
  return new Promise((resolve) => {
    const issuer = process.env.COSIGN_OIDC_ISSUER ?? "https://token.actions.githubusercontent.com";
    const identityRegexp =
      process.env.COSIGN_IDENTITY_REGEXP ?? "^https://github\\.com/[^/]+/[^/]+/\\.github/workflows/skillscan\\.yml@";
    const args = [
      "--report", reportPath,
      "--bundle", bundlePath,
      "--expected-issuer", issuer,
      "--expected-identity-regexp", identityRegexp,
    ];
    const proc = spawn(scriptPath, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    proc.stdout?.on("data", (d) => (stdout += d.toString("utf8")));
    proc.stderr?.on("data", (d) => (stderr += d.toString("utf8")));
    const t = setTimeout(() => {
      proc.kill("SIGKILL");
      resolve({ ok: false, error: "invalid_signature" });
    }, timeoutMs);
    proc.on("error", () => {
      clearTimeout(t);
      resolve({ ok: false, error: "cosign_error" });
    });
    proc.on("close", (code) => {
      clearTimeout(t);
      if (code !== 0) {
        try {
          const out = JSON.parse(stdout.trim()) as { ok?: boolean; error?: string };
          resolve({ ok: false, error: out.error ?? "invalid_signature" });
        } catch {
          resolve({ ok: false, error: "invalid_signature" });
        }
        return;
      }
      parseBundle(bundlePath)
        .then((parsed) => {
          if (parsed) resolve({ ok: true, ...parsed });
          else resolve({ ok: false, error: "invalid_signature" });
        })
        .catch(() => resolve({ ok: false, error: "invalid_signature" } as VerifyFailure));
    });
  });
}

/** 从 bundle JSON 解析 subject[0].digest.sha256、predicate.repo、predicate.workflow_ref */
export async function parseBundle(bundlePath: string): Promise<{
  subjectDigestSha256: string;
  predicateRepo: string;
  workflowRef?: string;
} | null> {
  const raw = await readFile(bundlePath, "utf8");
  let bundle: unknown;
  try {
    bundle = JSON.parse(raw);
  } catch {
    return null;
  }
  const b = bundle as Record<string, unknown>;
  const msgList = (b.messageSignatures ?? b.message_signature) as Record<string, unknown>[] | undefined;
  const msg = msgList?.[0] as Record<string, unknown> | undefined;
  const message = (msg?.message ?? b.base64Payload) as string | undefined;
  if (!message || typeof message !== "string") return null;
  let envelope: { payload?: string };
  try {
    envelope = JSON.parse(Buffer.from(message, "base64").toString("utf8"));
  } catch {
    return null;
  }
  const payloadB64 = envelope.payload;
  if (!payloadB64) return null;
  let statement: {
    subject?: { digest?: { sha256?: string } }[];
    predicate?: { repo?: string; workflow_ref?: string };
  };
  try {
    statement = JSON.parse(Buffer.from(payloadB64, "base64").toString("utf8"));
  } catch {
    return null;
  }
  const subjectDigestSha256 = statement.subject?.[0]?.digest?.sha256;
  const predicateRepo = statement.predicate?.repo;
  const workflowRef = statement.predicate?.workflow_ref;
  if (!subjectDigestSha256 || typeof predicateRepo !== "string") return null;
  return {
    subjectDigestSha256,
    predicateRepo,
    workflowRef: typeof workflowRef === "string" ? workflowRef : undefined,
  };
}

export function sha256Buffer(buf: Buffer): string {
  return createHash("sha256").update(buf).digest("hex");
}
