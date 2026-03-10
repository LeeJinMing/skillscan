/** 获取 GitHub App Installation 的 account 信息（用于 install/complete 建 tenant） */
export interface InstallationAccount {
  account_id: number;
  account_login: string;
  account_type: "Organization" | "User";
}

const GITHUB_APP_ID = process.env.GITHUB_APP_ID;
const GITHUB_PRIVATE_KEY = process.env.GITHUB_PRIVATE_KEY;

/** 若未配置 App 凭证则返回 null（本地可 mock 或从 env 读） */
export async function getInstallationAccount(installationId: number): Promise<InstallationAccount | null> {
  const mockId = process.env.GITHUB_MOCK_ACCOUNT_ID;
  const mockLogin = process.env.GITHUB_MOCK_ACCOUNT_LOGIN;
  const mockType = process.env.GITHUB_MOCK_ACCOUNT_TYPE;
  if (mockId != null && mockLogin != null && mockType != null) {
    return {
      account_id: Number(mockId),
      account_login: mockLogin,
      account_type: mockType === "Organization" ? "Organization" : "User",
    };
  }
  if (!GITHUB_APP_ID || !GITHUB_PRIVATE_KEY) return null;

  const jwt = await createAppJwt();
  const res = await fetch(`https://api.github.com/app/installations/${installationId}`, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${jwt}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!res.ok) return null;
  const data = (await res.json()) as { account?: { id: number; login: string; type: string } };
  const account = data?.account;
  if (!account) return null;
  const accountType = account.type === "Organization" ? "Organization" : "User";
  return {
    account_id: account.id,
    account_login: account.login,
    account_type: accountType,
  };
}

async function createAppJwt(): Promise<string> {
  const { createSign } = await import("crypto");
  const header = { alg: "RS256", typ: "JWT" };
  const now = Math.floor(Date.now() / 1000);
  const payload = { iss: GITHUB_APP_ID, iat: now, exp: now + 600 };
  const b64 = (buf: Buffer) => buf.toString("base64url");
  const part1 = b64(Buffer.from(JSON.stringify(header)));
  const part2 = b64(Buffer.from(JSON.stringify(payload)));
  const toSign = `${part1}.${part2}`;
  const key = (GITHUB_PRIVATE_KEY ?? "").replace(/\\n/g, "\n");
  const sig = createSign("RSA-SHA256").update(toSign).sign(key, "base64url");
  return `${toSign}.${sig}`;
}
