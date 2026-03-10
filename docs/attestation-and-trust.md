# Attestation and Trust Chain (Sigstore keyless)

This document defines how CI signs reports and how the service verifies them. **No long-lived keys in CI;** identity comes from GitHub Actions OIDC.

---

## 0. Default workflow path (MVP)

- **Default workflow path:** `.github/workflows/skillscan.yml`
- **Default policy:** Only this path is allowed to upload (unless the user explicitly registers another path on the allowlist).
- **Extension (later):** Users may register multiple workflow paths; server accepts only identities that match the allowlist (repo + workflow_path). Any other path → **401 identity not allowed**.

**Why fix a default name:** Reduces config hell for first users, reduces attack surface (no “any workflow in repo can sign”), and keeps docs to one sentence: “Add `.github/workflows/skillscan.yml` and run it.”

---

## 1. Identity binding (what we trust)

With Sigstore keyless, GitHub Actions obtains a short-lived certificate via OIDC. The service must enforce:

- **Issuer:** Must be `https://token.actions.githubusercontent.com`.
- **Identity:** Must match an **allowed workflow path** (see §4).  
  Identity string shape: `https://github.com/<owner>/<repo>/.github/workflows/<workflow>.yml@<ref>`  
  We do **not** bind to branch/tag; the `@...` (ref) part is allowed to vary. Use a regex that matches up to and including `@`, e.g.  
  `^https://github.com/<owner>/<repo>/.github/workflows/<workflow_file>@`

This prevents “someone adds a malicious workflow in the same repo and signs the same payload”; only workflows on the allowlist are accepted.

---

## 2. CI output (what CLI/Action must produce)

### A. report.json

Unchanged: findings, verdict, version info, etc. (see report v1 schema).

### B. Attestation (in-toto Statement, then signed)

The attestation **payload** (before DSSE/cosign) must be an **in-toto Statement** with at least:

| Field | Meaning |
|-------|--------|
| **subject** | `[{ "name": "report.json", "digest": { "sha256": "<sha256_of_report_file_bytes>" } }]` |
| **predicateType** | Custom URI, e.g. `https://skillscan.dev/attestation/v1` |
| **predicate** | |

**predicate** (minimal, auditable):

| Key | Source | Meaning |
|-----|--------|--------|
| `repo` | `GITHUB_REPOSITORY` | e.g. `owner/repo` |
| `workflow_ref` | `GITHUB_WORKFLOW_REF` | Contains workflow path (e.g. `owner/repo/.github/workflows/skillscan.yml@refs/heads/main`) |
| `run_id` | `GITHUB_RUN_ID` | Run identifier |
| `sha` | `GITHUB_SHA` | Commit SHA |
| `cli_version` | CLI | Scanner version |
| `ruleset_version` | Report | Ruleset version |

### C. Signing and bundle

- Use **cosign** in keyless mode to sign the attestation (DSSE envelope).
- Output a single artifact: **attestation.bundle** (or equivalent), containing everything needed to verify (certificate chain + signature). Do not expect clients or the server to reassemble cert/signature fragments.

**CI does not store any long-lived private keys.**

### D. Target CLI interface (minimal, for workflow compatibility)

- **`skillscan scan [path] --output-dir .`** — Run scan and write `report.json` to the target directory.
- **`skillscan version --json`** — CLI version (optional; 可先输出纯文本或从 report 的 `scanner.version` 取)。
- **`skillscan rules version --json`** — Ruleset version (optional; 可先返回内置规则版本或从 report 的 `scanner.ruleset_version` 取)。

当前仓库 workflow 已用 “Run scan” + 从 `report.json` 读出版本的方式兼容现有 CLI；后续可补齐上述子命令。

---

## 3. Server verification (POST /reports) — fixed order, non-negotiable

Request: **report.json** + **attestation.bundle**.

The server **must** perform these checks **in this exact order**; skipping or reordering any step invalidates the “trust” guarantee.

**MVP 版最小验证顺序（别加戏）：**

| Step | Check | Failure |
|------|--------|--------|
| 1. Repo 归属 | 从 attestation identity 或 `repo_full_name`（开发兜底）解析 **org/repo**，并确认 repo 已 enrolled。 | 401 |
| 2. Cosign 验签 | 调用 cosign（或 scripts/verify-attestation.sh）：校验 **issuer** 必须是 `https://token.actions.githubusercontent.com`；校验 **certificate identity** 必须匹配 `^https://github\.com/<org>/<repo>/\.github/workflows/skillscan\.yml@`。 | 401 invalid_signature |
| 3. Digest | 解析 attestation，取 **subject.digest.sha256**；计算 **sha256(report.json)**，必须匹配。 | 422 report_digest_mismatch |
| 4. Schema | `report.json` 符合公开 JSON Schema。 | 422 schema_invalid |
| 5. 业务 | 入库 / 审计 / 出 verdict；返回 report_id、final_verdict、approval_elevation_applied、console_url。 | — |

**没命中默认 workflow**（identity 不匹配上述正则）→ 直接 **401 identity_not_allowed**；文档写清楚，减少工单。

---

## 4. Allowed workflow：MVP 先“不开 allowlist”，但不堵死未来

- **产品上**：MVP 不提供 POST /allowed-workflows、不做 allowlist UI；服务端**只接受默认** `.github/workflows/skillscan.yml`，identity 正则按 enrolled repo 动态拼（§3）。
- **工程上**：**保留表结构**（或配置结构）；**onboarding 时自动插入默认行**：`(org, repo, ".github/workflows/skillscan.yml", enabled=true)`。这样等开放“多 workflow 显式登记”时：/reports 主流程几乎不动，只把“默认 identity regex”改成“查 allowed_workflows 生成一组 regex / 或精确匹配”。
- **接口形态**：POST /allowed-workflows、Console 登记入口等**保留在 OpenAPI/文档里**，实现可延后；表 `allowed_workflows` 先用于存默认行与未来扩展。

Table `allowed_workflows` (see `docs/postgres-schema.sql`):

| Column | Type | Meaning |
|--------|------|--------|
| `id` | uuid | Primary key |
| `org` | text | GitHub org/user |
| `repo` | text | Repo name |
| `workflow_path` | text | Must match `.github/workflows/*.yml` |
| `enabled` | bool | Soft switch |
| `created_by` | text | GitHub user login |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

Constraints: **UNIQUE(org, repo, workflow_path)**; **CHECK(workflow_path LIKE '.github/workflows/%.yml')**.

---

## 5. Register allowlist — 保留接口形态，MVP 不实现

**POST /allowed-workflows**（未来开放多 workflow 时实现）

- Body: `{ "org": "acme", "repo": "payments", "workflow_path": ".github/workflows/skillscan.yml" }`
- Server: 调 GitHub API 校验调用者对该 repo 至少 admin/maintain；CHECK(workflow_path)；upsert `allowed_workflows`。
- Response: `{ "ok": true, "allowed_workflow_id": "..." }`

**MVP**：产品上不提供此接口与 Console 登记；onboarding 时仅自动插入默认行（§4）。OpenAPI 与文档保留形态，避免以后大改。

---

## 6. POST /reports — input and response

- **Multipart 字段名定死，不再改**（接口一旦在用户 CI 落地，改一次就会收到一堆“怎么突然坏了”的工单）:
  - **`report`** — file (report.json bytes).
  - **`attestation_bundle`** — file (cosign bundle).
- **Response (success):**  
  `{ "report_id": "...", "final_verdict": "approved|blocked|needs_approval", "approval_elevation_applied": false, "console_url": "https://console...." }`

OpenAPI 定义见 [../api/openapi.yaml](../api/openapi.yaml)。

---

## 7. API error codes (explicit, no guesswork)

| HTTP | Body / code | Meaning |
|------|-------------|--------|
| **401** | `invalid_signature` | Cosign/Sigstore verify failed or issuer not GitHub Actions OIDC. |
| **401** | `identity_not_allowed` | Identity (repo + workflow_path) not in allowlist or disabled. |
| **422** | `report_digest_mismatch` | SHA256(report bytes) ≠ attestation subject digest. |
| **422** | `schema_invalid` | report.json does not conform to public schema. |
| **402** | `quota_exceeded` | Trial quota exhausted. |

---

## 8. Server ingest — MVP 版（token 绑定 org/repo + 默认 workflow）

“B 绑定”在 MVP 即：**identity 必须匹配** `^https://github\.com/<org>/<repo>/\.github/workflows/skillscan\.yml@`，**org/repo 从 token 配置来**。

```
function ingest(report_bytes, attestation_bundle, token):
  # 1) 鉴权：token → org/repo（1 token = 1 repo）
  (org, repo) = lookup_token(token)
  if not org or not repo: return 401

  # 2) 验签（调用 scripts/verify-attestation.sh 或等价）
  #    --expected-issuer https://token.actions.githubusercontent.com
  #    --expected-identity-regexp "^https://github\.com/<org>/<repo>/\.github/workflows/skillscan\.yml@"
  claims = run_verify_script(report_path, bundle_path, org, repo)
  if claims.error: return 401 invalid_signature | identity_not_allowed

  # 3) report digest 必须匹配 attestation subject
  digest = sha256(report_bytes)
  if digest != claims.subject_digest_sha256: return 422 report_digest_mismatch

  # 4) schema 校验 report.json
  if not jsonschema_validate(report): return 422 schema_invalid

  # 5) 业务：入库 / 审计 / verdict
  store_audit(repo, workflow_path, run_id, sha, ruleset_version, identity_verified=true)
  return 200 final
```

---

## 8b. Cosign 验签合约：封装成脚本（别在 TS 里拼参数）

- **Dockerfile**：固定 cosign 版本（严禁 latest），校验下载哈希。
- **scripts/verify-attestation.sh**：参数只传 `--report <path>`、`--bundle <path>`、`--expected-issuer ...`、`--expected-identity-regexp ...`；脚本内部调用 cosign，**stdout 永远输出一个固定 JSON**（如 `{ "ok": true, "subject_digest_sha256": "..." }` 或 `{ "ok": false, "error": "identity_not_allowed" }`），由你们自己定义字段。
- **TS 里**：只 **spawn 该脚本**，**parse 脚本 stdout 的 JSON**；不拼 cosign 参数。以后 cosign 参数变了，只改脚本和镜像，不改业务代码。

---

## 9. Default workflow 强制策略（MVP）

- **用户什么都不配置时**：引导他只用 **`.github/workflows/skillscan.yml`**；服务端只接受该 identity（按 token 绑定的 org/repo 动态拼正则）。
- **Onboarding**：自动插入默认行 `(org, repo, ".github/workflows/skillscan.yml", enabled=true)` 到 allowed_workflows（或等价配置）；产品上不暴露 allowlist 登记 UI/API。
- **要加第二个 workflow**：后续版本开放 allowlist 后，再提供 “Add allowed workflow”；/reports 主流程几乎不动，只改“从 allowed_workflows 查 regex”。

---

## 10. Fork / PR behavior (practical note)

GitHub Actions OIDC and permissions for **fork PRs** can be tricky. **First version:** do **not** accept runs triggered by fork PRs (or only allow runs from internal branches). Revisit after identity constraints, abuse controls, and quota are stable.

---

## 11. Pitfalls (why default workflow name matters)

- **Avoid config hell:** Without a fixed default, first users get stuck on path/permissions/env vars; support load explodes.
- **Reduce attack surface:** The more configurable the “allowed workflow” is, the more room for “add one malicious workflow and it can sign too.” One default path + explicit allowlist keeps the model clear.
- **Docs in one line:** “Add `.github/workflows/skillscan.yml` to your repo and run it” is enough to get started.

---

## 12. 致命缺陷（不现在解决，后面一定翻车）

- **自研验签**：自己解析证书、自己校验 DSSE/in-toto、自己校 Rekor → 迟早出安全事故或兼容事故。必须用 **cosign 二进制** 或官方 SDK。
- **identity / allowlist 非 hard requirement**：若验签通过就放行、不强制命中 allowlist，则“绑定 repo+workflow”只是一句宣传话术。服务端必须：验签通过 **且** identity 命中 allowlist 才进入业务。
- **字段名 / 返回结构频繁变动**：用户会直接骂不专业然后卸载。multipart 字段 **report**、**attestation_bundle** 及 200 响应体字段 **report_id / final_verdict / approval_elevation_applied / console_url** 定死，不向后不兼容地改。

---

## 13. 推荐技术栈（MVP 最少代码、最稳）

**方案 A（保守稳健，推荐）：Server 里“调用 cosign 二进制”完成验签**

- **后端**：FastAPI + PostgreSQL 或 **Node/TS (Fastify)** + PostgreSQL。
- **验签**：容器内**固定版本** cosign，服务端用 **exec/spawn** 调用。不自己解析证书/DSSE/Rekor。

**Node/TS 务实版：**

| 组件 | 选型 | 说明 |
|------|------|------|
| HTTP | Fastify + @fastify/multipart | |
| DB | PostgreSQL + **pg**（先别上 Prisma） | MVP 要可控和少坑 |
| 校验 | Fastify 自带 **ajv**（JSON schema） | report schema 放 skillscan-spec |
| 并发/限流 | **p-limit**（限制 cosign 并发）+ Fastify rate limit（按 token/org） | |
| 验签 | **调用固定版本的 cosign CLI**（别用库嵌进去，坑多且不稳定） | Dockerfile 固定 COSIGN_VERSION；scripts/verify.sh 把参数定死并覆盖测试，服务端只调该脚本 |

**cosign 参数与版本：** cosign CLI 参数细节跟版本强绑定。正确做法：Dockerfile 固定 cosign 版本（写死 COSIGN_VERSION，校验下载哈希，别用 latest）；仓库里写 **scripts/verify.sh** 把参数定死并覆盖测试；服务端只调用该脚本，减少线上版本漂移。

---

## 13b. Node 端最容易翻车的点（必须硬做）

| 点 | 做法 |
|----|------|
| **上传大小** | multipart **fileSize limit**（如 2MB），否则内存/磁盘直接爆。 |
| **流式落盘** | **必须**流式写文件，不要把 report/bundle 全读进内存。 |
| **cosign 超时** | 子进程**超时 + kill**（如 20s 后 SIGKILL），否则被卡住会拖死 worker。 |
| **cosign 并发** | 每 pod 同时最多 2～4 个验签（p-limit）。 |
| **临时目录** | **finally** 里清理 mkdtemp 目录，否则磁盘慢性死亡。 |

实现骨架（Fastify + TS）见 [fastify-reports-skeleton.ts](fastify-reports-skeleton.ts)。

---

## 14. MVP 核心功能（别加戏）

| 功能 | 说明 |
|------|------|
| **默认 workflow 一键登记** | Console 里点一下即登记 `.github/workflows/skillscan.yml`（org/repo 由登录用户选）。 |
| **POST /reports** | 验签（cosign）→ allowlist 校验 → report digest 校验 → schema 校验 → 入库 → 返回 report_id / final_verdict / approval_elevation_applied / console_url。 |
| **审计事件** | 至少记录：repo、workflow_path、run_id、sha、ruleset_version、**identity_verified=true**。 |
| **试用额度扣减 + 402** | 试用配额扣减；超限返回 **402 quota_exceeded**。 |

---

## 15. 上线前必须补的 3 个工程护栏（不做就别上线）

| 护栏 | 说明 |
|------|------|
| **Docker 固定 cosign** | 镜像里**固定 cosign 版本**（写死 COSIGN_VERSION），**校验下载哈希**，别用 latest。 |
| **速率限制 + 配额** | /reports 做 **token/org 级别**的速率限制 + 配额扣减，防被打爆；超限 402 quota_exceeded。 |
| **对象存储落地** | report + bundle **至少要能存到 S3/R2**（或等价物）；本地盘不可靠，容器重启就没了。 |

---

## 16. Iteration (later; don’t overdo now)

- **Allowlist pattern:** Support workflow_path pattern later; skip for MVP.
- **Branch/Tag (C):** Restrict by ref as an enterprise add-on.
- **Self-host:** Enterprise delivery (image + license); server remains closed source.
