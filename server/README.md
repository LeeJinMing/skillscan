# SkillScan Server（Fastify）

这是团队侧治理后端。它负责：

1. 收 `report.json` + `attestation.bundle`
2. 返回最终 verdict
3. 保存扫描记录、审批结果、审计日志
4. 提供 `healthz / readyz / metrics / scans / approvals / audit`

接口真相源在 [`../api/openapi.yaml`](../api/openapi.yaml)。

## 推荐顺序

不要一上来就起服务端。

先走这条路：

1. 在仓库根目录用 CLI 跑出 `report.json`
2. 用 `.github/workflows/skillscan.yml` 接进 CI
3. 再启动这个服务，接团队共享、审批和审计

这里的定位不是“一个上传报告的 API”。

更准确地说，它是：

**agent 扩展治理层的控制面。**

当前先接 `skills`。后续如果扩到 `MCP`、`workflow packs`，主要复用的也是这一层。

## 本地启动

### Demo 模式

```bash
cd server
npm install
copy .env.example .env
npm run dev
```

默认地址：`http://localhost:3000`

这时是 **demo 模式**：

- `GET /healthz` 正常
- `GET /readyz` 会显示 `mode=demo`
- `POST /reports` 可以联调
- `GET /scans`、`/approvals`、`/audit` 需要数据库才有真实数据

### 完整模式

```bash
cd server
npm install
copy .env.example .env

# 准备好 Postgres 后执行一次
psql $DATABASE_URL -f ../docs/postgres-schema.sql

npm run dev
```

什么时候需要配 DB、OAuth、GitHub App，看 [`../docs/WHEN-TO-PROVIDE-KEYS.md`](../docs/WHEN-TO-PROVIDE-KEYS.md)。

## 常用命令

```bash
npm run dev
npm run build
npm start
npm test
```

## 核心接口

### 健康检查

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`

### 登录和安装

- `GET /auth/github/start`
- `GET /auth/github/callback`
- `POST /github/install/start`
- `POST /github/install/complete`
- `POST /github/webhooks`

### 报告和分享

- `POST /reports`
- `GET /r/:share_token`

### 审批和审计

- `GET /scans`
- `GET /scans/:scan_id`
- `GET /approvals`
- `POST /approve`
- `POST /reject`
- `GET /verdict?repo=org/repo&commit_sha=...`
- `GET /audit`

## `/reports` 现在会做什么

服务端现在会把这条链路打通：

1. 收 multipart：`report` + `attestation_bundle`
2. 校验 schema
3. 可选跑 cosign 验签
4. 解析 repo / commit / verdict
5. 写 `reports`
6. 写 `scans`
7. 查有没有匹配审批
8. 返回最终 verdict、`share_url`、`console_url`

返回里关键字段有：

- `scan_id`
- `report_id`
- `share_url`
- `console_url`
- `verdict.status`
- `final_verdict`
- `approval_elevation_applied`

## 环境变量

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | Postgres 连接串；不设时进入 demo 模式 |
| `HOST` / `PORT` | 监听地址 |
| `STATE_SECRET` | install state 签名密钥 |
| `SESSION_SECRET` | session cookie 签名密钥 |
| `PUBLIC_BASE_URL` | 对外地址，用于 share_url / console_url |
| `GITHUB_WEBHOOK_SECRET` | Webhook 验签 |
| `GITHUB_APP_ID` / `GITHUB_PRIVATE_KEY` | GitHub App 安装绑定 |
| `GITHUB_MOCK_ACCOUNT_*` | 本地无 App 时模拟安装账户 |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` / `GITHUB_OAUTH_CALLBACK_URL` | GitHub OAuth 登录 |
| `REPORTS_RATE_LIMIT_PER_MIN` / `SHARE_RATE_LIMIT_PER_MIN` | 限流阈值 |
| `RATE_LIMIT_BACKEND` | `memory` 或 `database`；多实例建议 `database` |
| `REPORT_VERIFY_CONCURRENCY` / `REPORT_VERIFY_TIMEOUT_MS` | 验签并发和超时 |
| `SKIP_COSIGN_VERIFY=1` | 开发时跳过 cosign，用 `repo_full_name` 兜底 |
| `REPORT_SCHEMA_PATH` | 指定 report schema 文件 |

## 数据库

表结构在 [`../docs/postgres-schema.sql`](../docs/postgres-schema.sql)。

这次主链主要用到：

- `reports`
- `repo_latest_reports`
- `scans`
- `approvals`
- `audit_log`
- `rate_limits`

`rate_limits` 用于多实例共享固定窗口限流。

## Cosign 验签

- `scripts/verify-attestation.sh`：调用 `cosign verify-blob`
- `src/verify-attestation.ts`：调脚本并解析 bundle
- 开发联调可以设 `SKIP_COSIGN_VERIFY=1`

## 测试

```bash
npm test
```

现在的测试覆盖：

- OAuth / install / webhook 基本契约
- `/reports` 的 multipart smoke test
- `healthz / readyz / metrics`
- 未登录访问 `scans / approvals` 的行为

## Docker

在仓库根目录执行：

```bash
docker build -f server/Dockerfile .
```

镜像内会带固定版本 cosign。生产仍要传入 DB、OAuth、GitHub App 和 secret。
