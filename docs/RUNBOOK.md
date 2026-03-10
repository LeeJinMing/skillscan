# RUNBOOK：GitHub App、/reports、审批链排障

目标：出事时 3 分钟定位，不靠口述。契约以 **SPEC-github-app-binding.md** 与 **api/openapi.yaml** 为准。

先看 3 个地址：

- `/healthz`：服务是否活着
- `/readyz`：当前是 `demo` 还是 `database` 模式；DB 配置时会对 DB 执行 `SELECT 1`，不可达则返回 503
- `/metrics`：请求数、上传数、限流数、审计失败数（`skillscan_audit_failures_total`）

---

## 1. Webhook 验签失败

**现象**：POST /github/webhooks 返回 401 或日志报签名错误。

**排查**：

1. **验签必须用 raw body**：不能用 `JSON.stringify(req.body)`，否则签名对不上。确认中间件在 parse body 之前把原始字节存下来（如 `req.rawBody`），验签时用该字节 + WEBHOOK_SECRET。
2. 确认 **X-Hub-Signature-256** 与本地 HMAC-SHA256(secret, rawBody) 常量时间比较一致。
3. 确认 Webhook secret 与 GitHub App 配置里一致（无多余空格/换行）。

---

## 2. Webhook 幂等（重复投递）

**现象**：同一条 delivery 被处理多次，或报 unique 冲突。

**排查**：

1. 以 **X-GitHub-Delivery** 为幂等键；先 `INSERT INTO github_webhook_deliveries(delivery_id, event) VALUES ($1,$2)`。
2. 若 **唯一冲突** → 直接 200 返回，不再处理。
3. 只有插入成功才继续处理 installation / installation_repositories 逻辑。

---

## 3. Repo 不生效（未 enrolled）

**现象**：/reports 返回 401 repo_not_enrolled；用户说「已经装了 App 但不认」。

**排查**：

1. 查 **repos** 表：`SELECT * FROM repos WHERE full_name = 'org/repo'`；看 **enabled** 是否为 true。
2. 若 repo 不存在或 enabled=false：可能是用户安装时未勾选该 repo（Selected repositories），或 webhook installation_repositories 里该 repo 被 removed。让用户到 GitHub App 设置里确认该 repo 已选入，并触发一次「Save」或重装勾选。
3. Console 给人话提示：*"Repository is not enrolled. Go to GitHub App settings and add this repository (Selected repositories)."*

---

## 4. 403 tenant_owned_by_another_user

**现象**：用户点 Connect GitHub 并完成安装后，接口返回 403，code=tenant_owned_by_another_user。

**处理**：

1. 前端展示：标题 "This GitHub account is already linked"，说明该 org/user 已连到其他 Skillscan 账户，主按钮 Contact support。
2. **支持流程（人工）**：用户提交 (1) GitHub account（org/user login），(2) GitHub installation id（可选），(3) 证明为 owner/admin（截图或 org owner 登录 Console 再操作）。
3. **后台唯一动作（MVP）**：管理员**删除该 tenant + installation 绑定**（危险操作，必须人工确认），然后让用户**重新从 Console 发起安装绑定**。这是「强制解绑」，不是「转移」；MVP 不提供用户自助入口。
4. **审计**：记录 tenant_owner_conflict、install_conflict 等事件（current_user_id, github_account_id, installation_id, ip, user_agent）。

---

## 5. 410 分享链接已过期

**现象**：GET /r/:share_token 返回 410 Gone。

**解释**：链接已超过 **share_expires_at**（默认 7 天）。比 404 更明确：token 存在但已过期。

**处理**：页面展示「此链接已过期」；引导用户重新跑 CI 或从 Console 查看 Latest 报告。无需登录即可看到此提示。

---

## 6. 数据清理：reports 保留策略

**背景**：同一 commit 可能被同一 workflow 重跑多次，Append-only 会增长很快。

**MVP 做法**：cron job 定期执行保留策略，二选一或组合：

- **每个 repo 只保留最近 N 条**（如 200）；
- **或保留最近 30 天内的**（7 天分享期外，历史保留 30 天足够）。

**注意**：删除前确认不与 share_token 有效期内链接冲突（如只删 share_expires_at < now() 的旧报告）。

---

## 7. 审计日志（必做）

**必须记录的事件**：install_completed、tenant_owner_conflict、install_conflict（对应实现中 action：INSTALL_COMPLETED、TENANT_OWNER_CONFLICT、INSTALL_CONFLICT）。

**日志字段至少**：current_user_id、github_account_id、github_account_login、github_account_type、installation_id、ip、user_agent（存于 audit_log.metadata）。

**实现**：install/complete 成功写 INSTALL_COMPLETED；403 tenant 已被他人绑定写 TENANT_OWNER_CONFLICT；409 installation 已绑其他 tenant 写 INSTALL_CONFLICT。

---

## 8. /reports 验签或 schema 失败

**现象**：POST /reports 返回 401（invalid_signature、identity_not_allowed、repo_not_enrolled）或 422（report_digest_mismatch、schema_invalid）。

**排查**：

1. **401 invalid_signature**：cosign verify-blob 失败（issuer 非 GitHub Actions OIDC、或 identity 不匹配默认 workflow `.github/workflows/skillscan.yml`）。确认 scripts/verify-attestation.sh 参数与 GITHUB_WEBHOOK_SECRET 无关；验签用 attestation.bundle 内证书。Docker 镜像需固定 cosign 版本（见 server/Dockerfile）。
2. **401 identity_not_allowed**：证书 identity 未匹配 `COSIGN_IDENTITY_REGEXP`（默认 `^https://github\.com/…/\.github/workflows/skillscan\.yml@`）。确认 CI 使用默认 workflow 路径。
3. **401 repo_not_enrolled**：repo 没有在 `repos` 表里启用，或本地开发没传 `repo_full_name`。
4. **422 report_digest_mismatch**：report 文件 SHA256 与 attestation subject.digest.sha256 不一致。确认 CI 上传的 report 与签名时一致。
5. **422 schema_invalid**：report.json 不符合公开 schema（schema/report-v1.json）。服务端加载 schema 路径：REPORT_SCHEMA_PATH 或 server/schema/report-v1.json（Docker 内已 COPY）。未找到 schema 时跳过校验。

---

## 9. 审批后为什么还是没放行

**现象**：用户已经点了批准，但 Release 仍然失败。

**排查**：

1. 先查 `GET /verdict?repo=org/repo&commit_sha=<sha>`，确认服务端看到的最终 verdict。
2. 审批只提升 `needs_approval -> approved`。如果基础 verdict 是 `blocked`，永远不会提升。
3. 审批 scope 目前固定是 `repo@commit`。repo 或 commit_sha 任一不一致，都不会命中。
4. 查 `approvals` 表里是否有同一 `(org_id, scope_type='repo_commit', scope_key='repo=org/repo', commit_sha)` 的最新记录。
