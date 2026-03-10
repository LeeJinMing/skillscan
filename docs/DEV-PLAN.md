# SkillScan 后端开发计划（GitHub App 绑定 + Reports）

**目标**：按 `SPEC-github-app-binding.md` 与 `api/openapi.yaml` 交付可运行后端；先占位再逐步实现业务逻辑。  
**约束**：契约以 OpenAPI 为准；DB 以 `postgres-schema.sql` 为准；实现细节见 `IMPLEMENTATION-notes.md`。

---

## 阶段 0：环境与骨架（当前）

| 任务 | 产出 | 验收 |
|------|------|------|
| 0.1 补强 OpenAPI | ReportSummaryV1、OAuth 路径、Error 枚举 | 已就绪 |
| 0.2 制定开发计划 | 本文件 DEV-PLAN.md | 已就绪 |
| 0.3 搭建 server/ 骨架 | Node + Fastify + TS，所有 P0 路由占位 | `npm run build` 通过，各 path 返回约定 status |

---

## 阶段 1：P0 占位（路由 + 契约响应）

**目标**：每个 OpenAPI 路径有对应 handler，返回符合契约的 status/body（业务暂用 mock 或空实现）。

| 任务 | 路径/能力 | 产出 |
|------|-----------|------|
| 1.1 OAuth 占位 | GET /auth/github/start, /auth/github/callback | 302 跳转占位；callback 写死 session 或跳过 DB |
| 1.2 安装占位 | POST /github/install/start, complete | start 返回 install_url（state 可假）；complete 校验 state 占位，返回 200/403/409 |
| 1.3 Webhook 占位 | POST /github/webhooks | raw body 验签占位；幂等 key=delivery_id；200 |
| 1.4 上报占位 | POST /reports | multipart 接收；验签/归属 mock；返回 report_id, share_url, overall_pass, violations_count |
| 1.5 分享页占位 | GET /r/:share_token | 404/410/200 + ReportSummaryV1 或 HTML 占位 |

**验收**：对每个 path 的 happy path 与 1～2 个错误分支做请求级测试（curl 或 jest/supertest），状态码与 body 符合 OpenAPI。

---

## 阶段 2：P0 实现（DB + 真实逻辑）

**前提**：本地或 CI 可跑 Postgres（docker-compose 或托管）。

| 任务 | 内容 | 依赖 |
|------|------|------|
| 2.1 DB 迁移 | 执行 postgres-schema.sql；可选 migration 工具 | schema 已定 |
| 2.2 Session/用户 | OAuth 换 token → upsert users；写 session（cookie） | 2.1 |
| 2.3 State + install_sessions | HMAC state 生成/校验；install_sessions 读写、一次性 | 2.1 |
| 2.4 install/complete 事务 | tenant FOR UPDATE；github_installations 创建/冲突 409；used_at | 2.2, 2.3 |
| 2.5 Webhook 真实 | raw body 验签；delivery 幂等；installation(_repositories) 更新 repos | 2.1 |
| 2.6 /reports 验签+归属 | cosign 验签（或 scripts/verify.sh）；identity → repo → enrolled；reports + repo_latest_reports | 2.1, 2.5 |
| 2.7 GET /r/:share_token | 查 reports 表；404/410/200；summary JSON 或极简 HTML | 2.1 |

**验收**：E2E：登录 → start → complete（或 mock GitHub 安装）→ webhook 同步 repo → POST /reports → GET /r/:token；RUNBOOK 中列出的故障分支可复现并返回约定 code。

---

## 阶段 3：P0 防护与运维

| 任务 | 内容 |
|------|------|
| 3.1 限流 | /reports、/r/:token 按 IP 或 token 限流；可先内存/单机 |
| 3.2 cosign | 并发上限 + 超时；固定 cosign 版本（Dockerfile）+ scripts/verify.sh |
| 3.3 可观测 | 关键路径 log（不含敏感）；错误码打点；可选 metrics |
| 3.4 RUNBOOK 对齐 | 故障场景与处理步骤与 RUNBOOK.md 一致 |

---

## 阶段 4：P1（可选，按需排期）

- Console 侧：repo 列表与 enrolled 状态；安装页「如何勾选 repos」引导。
- 错误码 → 用户文案（前端/Setup 页）。
- 报告存储：S3/R2 持久化 report + bundle；artifact_url。

---

## 里程碑与优先级

| 里程碑 | 包含阶段 | 可交付物 |
|--------|----------|----------|
| M0 | 0 | 开发计划 + server 骨架 + 全路径占位 |
| M1 | 1 | 所有 P0 路由契约正确、可测 |
| M2 | 2 | 安装/上报/分享端到端走通 |
| M3 | 3 | 限流/验签/可观测就绪，可上预发 |

当前执行：**阶段 0.3 搭建 server/ 骨架**，随后进入阶段 1 细化占位响应。
