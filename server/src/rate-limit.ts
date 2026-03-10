import type { FastifyReply, FastifyRequest } from "fastify";
import type { Pool } from "pg";
import { recordRateLimited } from "./metrics.js";

const WINDOW_MS = 60_000; // 1 min
const RATE_LIMIT_BACKEND = (process.env.RATE_LIMIT_BACKEND ?? "memory").toLowerCase();

interface Entry {
  count: number;
  resetAt: number;
}

const store = new Map<string, Entry>();

export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetAt: number;
  backend: "memory" | "database";
}

function getEntry(key: string): Entry {
  let e = store.get(key);
  const now = Date.now();
  if (!e || e.resetAt <= now) {
    e = { count: 0, resetAt: now + WINDOW_MS };
    store.set(key, e);
  }
  return e;
}

function checkRateLimitMemory(key: string, maxPerWindow: number): RateLimitResult {
  const e = getEntry(key);
  if (e.count >= maxPerWindow) {
    recordRateLimited();
    return {
      allowed: false,
      limit: maxPerWindow,
      remaining: 0,
      resetAt: e.resetAt,
      backend: "memory",
    };
  }
  e.count += 1;
  return {
    allowed: true,
    limit: maxPerWindow,
    remaining: Math.max(maxPerWindow - e.count, 0),
    resetAt: e.resetAt,
    backend: "memory",
  };
}

async function checkRateLimitDatabase(pool: Pool, key: string, maxPerWindow: number): Promise<RateLimitResult> {
  const now = Date.now();
  const bucketStart = Math.floor(now / WINDOW_MS) * WINDOW_MS;
  const resetAt = bucketStart + WINDOW_MS;
  const res = await pool.query<{ count: number }>(
    `INSERT INTO rate_limits (bucket_key, bucket_start, count, updated_at)
     VALUES ($1, to_timestamp($2 / 1000.0), 1, now())
     ON CONFLICT (bucket_key, bucket_start)
     DO UPDATE SET count = rate_limits.count + 1, updated_at = now()
     RETURNING count`,
    [key, bucketStart],
  );
  const count = Number(res.rows[0]?.count ?? 0);
  const allowed = count <= maxPerWindow;
  if (!allowed) recordRateLimited();
  return {
    allowed,
    limit: maxPerWindow,
    remaining: Math.max(maxPerWindow - Math.min(count, maxPerWindow), 0),
    resetAt,
    backend: "database",
  };
}

/** 检查是否允许通过；支持内存或数据库窗口限流。 */
export async function checkRateLimit(
  pool: Pool | null,
  key: string,
  maxPerWindow: number,
): Promise<RateLimitResult> {
  if (RATE_LIMIT_BACKEND === "database" && pool) {
    return checkRateLimitDatabase(pool, key, maxPerWindow);
  }
  return checkRateLimitMemory(key, maxPerWindow);
}

export function applyRateLimitHeaders(reply: FastifyReply, result: RateLimitResult): void {
  reply.header("X-RateLimit-Limit", String(result.limit));
  reply.header("X-RateLimit-Remaining", String(result.remaining));
  reply.header("X-RateLimit-Reset", String(Math.floor(result.resetAt / 1000)));
  reply.header("X-RateLimit-Backend", result.backend);
  if (!result.allowed) {
    const retryAfter = Math.max(1, Math.ceil((result.resetAt - Date.now()) / 1000));
    reply.header("Retry-After", String(retryAfter));
  }
}

/** 从请求取客户端 IP（考虑 X-Forwarded-For） */
export function getClientIp(req: FastifyRequest | { ip?: string; headers?: Record<string, string | string[] | undefined> }): string {
  const forwarded = req.headers?.["x-forwarded-for"];
  if (typeof forwarded === "string") {
    const first = forwarded.split(",")[0]?.trim();
    if (first) return first;
  }
  return req.ip ?? "127.0.0.1";
}
