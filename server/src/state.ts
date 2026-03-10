import crypto from "crypto";

const STATE_SECRET =
  process.env.STATE_SECRET ?? "dev_state_secret_change_in_production";
const STATE_TTL_SEC = 600; // 10 min

export interface StatePayload {
  v: number;
  sid: string;
  uid?: string;
  iat: number;
  exp: number;
  nonce: string;
  returnTo?: string;
}

function base64urlEncode(buf: Buffer): string {
  return buf.toString("base64url");
}

function base64urlDecode(str: string): Buffer | null {
  try {
    return Buffer.from(str, "base64url");
  } catch {
    return null;
  }
}

/** 生成 state：payload_b64 + "." + HMAC(payload_b64)；防 CSRF */
export function buildState(sid: string, uid: string | undefined, nonce: string, returnTo?: string): string {
  const now = Math.floor(Date.now() / 1000);
  const payload: StatePayload = {
    v: 1,
    sid,
    uid,
    iat: now,
    exp: now + STATE_TTL_SEC,
    nonce,
    returnTo: returnTo ?? "/",
  };
  const payloadB64 = base64urlEncode(Buffer.from(JSON.stringify(payload)));
  const sig = crypto.createHmac("sha256", STATE_SECRET).update(payloadB64).digest();
  return `${payloadB64}.${base64urlEncode(sig)}`;
}

/** 校验 state，返回 payload 或 null（篡改/过期） */
export function verifyStateSignature(state: string): StatePayload | null {
  const dot = state.indexOf(".");
  if (dot <= 0) return null;
  const payloadB64 = state.slice(0, dot);
  const sigB64 = state.slice(dot + 1);
  const sigBuf = base64urlDecode(sigB64);
  if (!sigBuf) return null;
  const expected = crypto.createHmac("sha256", STATE_SECRET).update(payloadB64).digest();
  if (expected.length !== sigBuf.length || !crypto.timingSafeEqual(expected, sigBuf)) return null;
  const payloadBuf = base64urlDecode(payloadB64);
  if (!payloadBuf) return null;
  try {
    const payload = JSON.parse(payloadBuf.toString("utf8")) as StatePayload;
    if (payload.v !== 1 || !payload.sid || !payload.exp) return null;
    if (payload.exp <= Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}
