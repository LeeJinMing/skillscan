import type { FastifyRequest, FastifyReply } from "fastify";
import crypto from "crypto";

const COOKIE_NAME = "session";
const SESSION_SECRET =
  process.env.SESSION_SECRET ?? "dev_session_secret_change_in_production";
const TTL_SEC = 7 * 24 * 3600; // 7 days

function sign(value: string): string {
  const sig = crypto.createHmac("sha256", SESSION_SECRET).update(value).digest("base64url");
  return `${value}.${sig}`;
}

function verify(signed: string): string | null {
  const dot = signed.lastIndexOf(".");
  if (dot <= 0) return null;
  const value = signed.slice(0, dot);
  const sig = signed.slice(dot + 1);
  const expected = crypto.createHmac("sha256", SESSION_SECRET).update(value).digest("base64url");
  if (expected.length !== sig.length || !crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(sig))) return null;
  return value;
}

/** 从 cookie 解析出 user_id（uuid），未登录或无效返回 null */
export function getSessionUserId(req: FastifyRequest): string | null {
  const raw = req.cookies[COOKIE_NAME];
  if (!raw || typeof raw !== "string") return null;
  const value = verify(raw);
  if (!value) return null;
  const parts = value.split(":");
  if (parts.length !== 3) return null;
  const [, userId, exp] = parts;
  if (Number(exp) <= Math.floor(Date.now() / 1000)) return null;
  return userId;
}

/** 写入 session cookie（userId = uuid） */
export function setSession(reply: FastifyReply, userId: string): void {
  const exp = Math.floor(Date.now() / 1000) + TTL_SEC;
  const value = `v1:${userId}:${exp}`;
  reply.setCookie(COOKIE_NAME, sign(value), {
    path: "/",
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: TTL_SEC,
  });
}
