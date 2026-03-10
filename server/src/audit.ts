import type { Pool } from "pg";
import crypto from "crypto";
import { recordAuditFailure } from "./metrics.js";

export interface AuditEntry {
  org_id: string;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
}

/** 写入审计日志；失败仅打 log，不抛错 */
export async function insertAudit(pool: Pool | null, entry: AuditEntry): Promise<void> {
  if (!pool) return;
  const id = crypto.randomUUID();
  try {
    await pool.query(
      `INSERT INTO audit_log (id, org_id, actor, action, target_type, target_id, metadata)
       VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb)`,
      [
        id,
        entry.org_id,
        entry.actor,
        entry.action,
        entry.target_type,
        entry.target_id,
        JSON.stringify(entry.metadata),
      ],
    );
  } catch (e) {
    // 审计失败不阻断主流程，但必须记录以便告警/补偿
    recordAuditFailure();
    console.error("[audit] insert failed", { action: entry.action, target_id: entry.target_id, error: e });
  }
}
