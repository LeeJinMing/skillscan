/**
 * report.json 公开 JSON Schema 校验（schema/report-v1.json）；未找到 schema 时跳过校验。
 */
import type { ValidateFunction } from "ajv";
import { createRequire } from "module";
import { readFile } from "fs/promises";
import path from "path";

const require = createRequire(import.meta.url);

let validateReport: ValidateFunction | null = null;
let loadAttempted = false;
let schemaLoaded = false;

const DEFAULT_SCHEMA_PATH = path.join(process.cwd(), "schema", "report-v1.json");

/** 加载 schema 并编译；schema 不存在时 validateReport 保持 null（跳过校验） */
export async function loadReportSchema(schemaPath: string = process.env.REPORT_SCHEMA_PATH ?? DEFAULT_SCHEMA_PATH): Promise<void> {
  if (loadAttempted) return;
  loadAttempted = true;
  try {
    const raw = await readFile(schemaPath, "utf8");
    const schema = JSON.parse(raw);
    const Ajv = require("ajv") as new (opts?: { strict?: boolean }) => { compile: (s: unknown) => ValidateFunction };
    const addFormats = require("ajv-formats") as (ajv: unknown) => void;
    const ajv = new Ajv({ strict: false });
    addFormats(ajv);
    validateReport = ajv.compile(schema);
    schemaLoaded = true;
  } catch {
    validateReport = null;
    schemaLoaded = false;
  }
}

/** 校验 data 是否符合 report-v1；无 schema 时返回 true（不校验） */
export function validateReportData(data: unknown): boolean {
  if (!validateReport) return true;
  return validateReport(data) === true;
}

export function reportSchemaStatus() {
  return {
    attempted: loadAttempted,
    loaded: schemaLoaded,
    path: process.env.REPORT_SCHEMA_PATH ?? DEFAULT_SCHEMA_PATH,
  };
}

/** 从完整 report-v1 构建 ReportSummaryV1；非 v1 形状时返回 null，由调用方用现有逻辑 */
export function summaryFromReportV1(report: Record<string, unknown>): {
  overall_pass: boolean;
  violations_count: number;
  top_rules: string[];
  commit_sha: string;
  run_url: string | null;
  repo: string;
  verdict_status: string;
  reason_code: string;
} | null {
  const verdict = report.verdict as { status?: string } | undefined;
  const findings = report.findings as { id?: string }[] | undefined;
  const source = report.source as { commit_sha?: string; repo?: string } | undefined;
  if (!verdict || typeof verdict.status !== "string") return null;
  const status = verdict.status;
  const overall_pass = status !== "blocked";
  const violations_count = Array.isArray(findings) ? findings.length : 0;
  const top_rules = Array.isArray(findings)
    ? findings.slice(0, 5).map((f) => (f.id != null ? String(f.id) : "")).filter(Boolean)
    : [];
  const commit_sha = source && typeof source.commit_sha === "string" ? source.commit_sha : "";
  const repo = source && typeof source.repo === "string" ? source.repo : "";
  const reasonCode = typeof (verdict as { reason_code?: unknown }).reason_code === "string"
    ? String((verdict as { reason_code?: string }).reason_code)
    : "";
  return { overall_pass, violations_count, top_rules, commit_sha, run_url: null, repo, verdict_status: status, reason_code: reasonCode };
}
