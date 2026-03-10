# IMPLEMENTATION NOTES：GitHub App 绑定（可选附录）

**说明**：本文档是**参考实现**，不是产品契约。契约以 **SPEC-github-app-binding.md** 与 **api/openapi.yaml** 为准。  
写给开发者：伪代码、schema 摘要、竞态、任务与测试清单。代码变更时以 SPEC/OpenAPI 为准，本文档可滞后更新。

---

## 1. Postgres schema 摘要

完整 DDL 见 **docs/postgres-schema.sql**。绑定相关表摘要：

| 表 | 用途 |
|------|------|
| users | OAuth 登录；id, github_user_id unique, login, email |
| tenants | workspace=GitHub account；github_account_id unique, owner_user_id |
| install_sessions | state 一次性；user_id, nonce unique, expires_at, used_at |
| github_installations | installation_id pk, tenant_id, account_id/login/type |
| repos | repo_id pk, full_name unique, installation_id, enabled |
| github_webhook_deliveries | 幂等；delivery_id pk, event |
| reports | Append-only；share_token unique, share_expires_at not null |
| repo_latest_reports | repo_id pk → report_id（取最新 O(1)） |

---

## 2. State 结构（HMAC）

- **payload**：v=1, sid, uid(可选), iat, exp, nonce（32 bytes base64url）。
- **序列化**：payload_b64 = base64url(JSON.stringify(payload))；sig = base64url(HMAC_SHA256(STATE_SECRET, payload_b64))；state = payload_b64 + "." + sig。
- **校验**：split 两段 → 常量时间 HMAC 比较 → exp > now → DB 查 install_sessions.id=sid 且 used_at IS NULL 且 expires_at > now；使用后在事务内写 used_at=now()。
- **为何要 install_sessions**：HMAC 防篡改不防重放；一次性必须靠 DB。

---

## 3. Handler 伪代码骨架（Node/Fastify）

- **POST /github/install/start**：生成 sid、nonce、exp(10min)，插入 install_sessions，构造 state，返回 install_url。
- **POST /github/install/complete**：校验 state（split、HMAC、exp）→ 事务内：查 install_sessions FOR UPDATE、used_at/expires_at → 查/插 tenant FOR UPDATE、owner 冲突 403 → 查/插 github_installations、已绑其他 tenant 则 409 → 写 used_at；事务外可选 syncReposFromInstallation。
- **POST /github/webhooks**：raw body 验签 → 幂等插入 delivery_id（冲突则 200）→ installation deleted 时 repos.enabled=false；installation_repositories 时 added/removed 更新 repos。

详见原 **github-app-binding.md** 中「实现规格：Postgres schema + handler 骨架」一节（已拆出到本附录，原文件将替换为导航）。

---

## 4. 竞态与实现细节

- **Webhook 与 complete 竞态**：行由 complete 创建并写 tenant_id；webhook 只更新已有行或同步 repos。若 webhook 先到且无行则跳过（complete 会建行）。
- **install_complete 并发**：tenant owner 冲突（403）必须在事务内对 tenant 行 **FOR UPDATE**，否则两账号可同时抢绑同一 org/user。
- **webhook 验签**：必须用 **raw body**，不能用 JSON.stringify(req.body)。

---

## 5. 工程清单（按优先级）

**P0**：POST /github/install/start、complete；POST /github/webhooks（验签+幂等）；POST /reports（验签+归属+入库+share_url）；GET /r/:share_token（404/410/200）。  
**P0 防护**：/reports 限流、cosign 并发上限与超时；/r/:token 限流与 token 格式校验。  
**P1**：Console repo 列表与状态；「如何在 GitHub 安装页勾选 repos」引导；错误码→人话文案。

---

## 6. 最小测试清单

- Webhook 签名正确/错误 → 200/401。
- Webhook 同 delivery 重放 → 幂等，200。
- installation_repositories added/removed → repos enabled 正确。
- /reports 合法 bundle+report → 200；digest mismatch → 422；identity 非默认 workflow → 401；repo 未 enrolled → 401。
- /r/:share_token 存在且未过期 → 200；不存在 → 404；已过期 → 410。
- install/complete：state 无效/过期/已用 → 403；tenant 已被他人绑定 → 403；installation 已绑其他 tenant → 409。
