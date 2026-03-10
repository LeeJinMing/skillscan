# 何时开通 GitHub / 数据库 / 服务器并提供 Key

按你当前要做的**阶段**决定；越往后需要的越多。

## 最短判断

| 你现在想做什么 | 需要 DB | 需要 OAuth | 需要 GitHub App | 需要公网地址 |
|------|------|------|------|------|
| 只想本地扫 skill | 否 | 否 | 否 | 否 |
| 只想联调 `/reports` 契约 | 否 | 否 | 否 | 否 |
| 想看 `scans / approvals / audit` 真数据 | 是 | 是 | 否 | 否 |
| 想跑真实安装 + webhook + repo enrollment | 是 | 是 | 是 | 是 |
| 想给团队正式用 | 是 | 是 | 是 | 是 |

---

## 1. 只跑本地开发 / 单测（当前即可）

**不需要**你提供任何 Key 或外部服务。

- 无 `DATABASE_URL`：路由占位（install/start 500、share 404、reports 占位 200 或 401）。
- 无 GitHub：OAuth 用占位 URL；install/complete 可用 `GITHUB_MOCK_ACCOUNT_*` 模拟。
- `npm run build`、`npm test` 不依赖 DB/GitHub。
- `GET /healthz`、`GET /readyz`、`GET /metrics` 可直接看；`/scans`、`/approvals`、`/audit` 没有 DB 不会有真实结果。

---

## 2. 本地 E2E（登录 → 安装 → 上报 → 分享）

**需要**：

| 项目 | 何时需要 | 提供什么 |
|------|----------|----------|
| **数据库** | 要跑完整安装/上报/分享流程时 | 本地：`docker-compose up -d` + 执行 `docs/postgres-schema.sql`，设 `DATABASE_URL=postgres://skillscan:skillscan@localhost:5432/skillscan`。托管：创建 Postgres 实例，把连接串设成 `DATABASE_URL`。 |
| **GitHub OAuth（登录）** | 要「从 Console 登录后再点 Connect GitHub」时 | 在 GitHub 建 OAuth App：Settings → Developer settings → OAuth Apps → New。拿到 **Client ID**、**Client secret**；**Callback URL** 填你本地或内网地址，如 `http://localhost:3000/auth/github/callback`。设 `GITHUB_CLIENT_ID`、`GITHUB_CLIENT_SECRET`、`GITHUB_OAUTH_CALLBACK_URL`。 |
| **GitHub App（安装 + Webhook）** | 要「真实安装 App、选 repo、收 webhook、/reports 按 repo 归属」时 | 在 GitHub 建 GitHub App：Settings → Developer settings → GitHub Apps → New。记下 **App ID**、生成 **Private key**；**Webhook URL** 填可被 GitHub 访问的地址（本地可用 ngrok 等），设 **Webhook secret**。设 `GITHUB_APP_ID`、`GITHUB_PRIVATE_KEY`（PEM 内容）、`GITHUB_WEBHOOK_SECRET`、`GITHUB_APP_INSTALL_URL`（安装页 URL）。 |
| **服务器/公网地址** | Webhook 必须被 GitHub 访问时 | 本地开发可用 ngrok 暴露 `http://localhost:3000`，把 ngrok URL 填到 GitHub App 的 Webhook URL。 |

**可延后**：

- **Cosign 验签**：设 `SKIP_COSIGN_VERIFY=1`，/reports 用表单项 `repo_full_name` 兜底，不跑 cosign。
- **公网部署**：E2E 可在本机 + ngrok 完成，不必先买服务器。

---

## 3. 预发 / 生产（对外提供 Console + CI 上报）

**需要**：

| 项目 | 说明 |
|------|------|
| **数据库** | 托管 Postgres（如云厂商 RDS/Neon/Supabase），把连接串设成 `DATABASE_URL`。 |
| **服务器（或 Serverless）** | 能跑 Node、对外提供 HTTPS 的机器或 FaaS。设 `HOST`/`PORT`（或平台默认）、`PUBLIC_BASE_URL`（分享链接域名，如 `https://api.skillscan.example.com`）。 |
| **GitHub OAuth** | 同上；Callback URL 改为生产域名，如 `https://console.skillscan.example.com/auth/github/callback`。 |
| **GitHub App** | 同上；Webhook URL 改为生产 API 地址，如 `https://api.skillscan.example.com/github/webhooks`；Private key 与 Webhook secret 放环境变量或密钥管理。 |
| **Cosign** | 不设 `SKIP_COSIGN_VERIFY`，镜像内已带 cosign；CI 按 attestation-and-trust 签 report + attestation.bundle。 |
| **密钥** | `STATE_SECRET`、`SESSION_SECRET` 用随机串；生产务必换掉默认值。 |

---

## 4. 建议时间线（你何时去开通/提供）

- **现在**：不用。本地单测、看代码、改逻辑都不需要 Key。
- **要跑「登录 → 安装 → 上报 → 分享」一整条 E2E 时**：先开 **数据库**（本地 docker 或托管），再开 **GitHub OAuth**（否则无法登录），再开 **GitHub App**（否则无法真实安装 + webhook）。Webhook 要公网可达，此时再决定用 ngrok 还是先上一台服务器。
- **要对外给团队/用户用时**：再开通 **托管 DB + 服务器（或 Serverless）**，并把 OAuth / GitHub App 的 URL 和密钥切到生产环境。

一句话：**先用 CLI，本地联调 `/reports`，再开 DB；要跑真实安装和团队协作，再补 OAuth、GitHub App 和公网地址。**
