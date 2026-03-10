# SPEC：GitHub App 绑定（唯一权威）

产品/后端/前端都按此执行。**目标：10 分钟读完。只写契约，不写伪代码。**  
接口细节以 `api/openapi.yaml` 为准；实现细节见 `IMPLEMENTATION-notes.md`。

---

## 1. Scope（MVP 做什么 / 不做什么）

**做**

- 从 Console 发起安装（带 state）→ Setup 页完成绑定 → webhook 同步 repos → workflow 跑完 POST /reports → 报告 Append-only 入库，分享链接 7 天有效。
- 只允许 **Selected repositories**；workflow 固定 `.github/workflows/skillscan.yml`。
- **tenant = GitHub installation 的 account**（Org 或 User）；**单 owner**（谁绑定谁用）。

**不做**

- 从 GitHub 直接安装后自动绑定（无 state 不绑定，只引导回 Console）。
- workspace 转移 owner、共享/邀请、多 org 合并到一个 workspace。
- 手动认领 installation_id、All repositories、多 workflow allowlist UI。

---

## 2. Definitions（tenant / Org+User / 单 owner / Selected repos）

| 概念 | 定义 |
|------|------|
| **tenant** | = GitHub installation 的 **account**（Org 或 User）。安装在 org → tenant=该 org；安装在 user → tenant=该 user。 |
| **单 owner** | 一个 workspace(tenant) 只能有一个 Console 用户拥有者（`owner_user_id`）。绑定后永久归属该 owner，MVP 不提供转移。 |
| **Repo 归属** | 跟着 installation 走；只对被选择的 repos 生效（未选则 /reports 401 repo_not_enrolled）。 |
| **计费** | 按 tenant：一个 org 一份账单，一个 user 一份账单。MVP 不做多 org 合并结算。 |

---

## 3. User Journey（端到端流程）

| 步骤 | 动作 |
|------|------|
| 1 | Console（已 OAuth 登录）点 **Connect GitHub** |
| 2 | 跳 GitHub 安装页 → 用户选 **Selected repositories** → 勾选 repo |
| 3 | 安装完成回到 **/github/setup**，自动完成绑定（有 state + installation_id） |
| 4 | 用户在 repo 放 `.github/workflows/skillscan.yml`，跑起来后 **/reports** 自动入库 |
| 5 | 响应返回 **share_url**；用户打开 **/r/:share_token** 查看结果（无需登录，7 天有效） |

**Setup 页无 state**：不绑定，只引导「请从 Console 发起连接」；按钮 Sign in to Skillscan。

**从 GitHub 直接安装（绕过 Console）**：Setup 页显示 "Installation not linked"，引导回 Console 登录后点 Connect GitHub 重新发起（带 state）。

---

## 4. State machine（安装绑定状态 + 失败分支）

**成功路径**：登录 → POST /github/install/start（拿到 install_url 带 state）→ 用户在 GitHub 完成安装 → GET /github/setup?installation_id=…&state=… → 前端 POST /github/install/complete → 200 { ok: true }。

**失败分支（仅列契约，具体 HTTP/code 以 OpenAPI 为准）**

| 条件 | 结果 |
|------|------|
| 未登录（start/complete） | 401 not_authenticated |
| state 无效/过期/已用 | 403 state_invalid_or_expired |
| 该 GitHub account 已被其他 Console 用户绑定 | 403 tenant_owned_by_another_user |
| installation 已绑定其他 tenant | 409 installation_already_linked |

**错误码 → 用户文案**（前端/Setup 页按此展示，不暴露内部 code）

| 场景 | 标题 | 主操作 |
|------|------|--------|
| 403 tenant_owned_by_another_user | This GitHub account is already linked | Contact support |
| 409 installation_already_linked | 该安装已连接到其他 Skillscan 账户 | 联系支持 |
| 无 state / state 无效 | Installation not linked | Sign in to Skillscan |
| /reports 401 repo_not_enrolled | — | Console 提示：Repository is not enrolled. Go to GitHub App settings and add this repository (Selected repositories). |

---

## 5. Security model（边界，不写实现）

| 边界 | 要求 |
|------|------|
| **state** | 一次性、可验证、不可篡改；10 分钟过期；使用后作废（防重放靠 DB）。 |
| **webhook** | 验签（X-Hub-Signature-256）；幂等（X-GitHub-Delivery）。 |
| **/reports** | 公网匿名；必须限流、cosign 并发上限、超时、文件大小限制；验签后 identity → repo → enrolled 再归属 tenant。 |
| **分享链接** | share_token ≥256-bit 随机；默认 7 天过期；/r/:token 不登录可访问，但需限流与 token 格式校验防扫描。 |

---

## 6. API contract summary（以 OpenAPI 为准）

| Endpoint | 鉴权 | 幂等 | 说明 |
|----------|------|------|------|
| GET /auth/github/start | 无 | — | 跳转 OAuth |
| GET /auth/github/callback | 无 | — | 换 token，upsert users，建 session |
| POST /github/install/start | 登录 | 否 | 返回 install_url（带 state） |
| POST /github/install/complete | 登录 | 否（state 一次性） | 绑定 installation → tenant |
| POST /github/webhooks | Webhook secret | 是（delivery_id） | installation / installation_repositories |
| POST /reports | 无（验签） | 否 | multipart report + attestation_bundle；返回 report_id, share_url, overall_pass, violations_count |
| GET /r/:share_token | 无 | 是 | 404 不存在；410 已过期；200 极简展示 Pass/Fail、violations、top_rules、commit_sha、run_url |

详细 request/response/错误码见 **api/openapi.yaml**。

---

## 7. Data ownership & billing assumptions

- 归属：**tenant = installation 的 account**；**owner_user_id** 唯一拥有者。
- 计费：按 tenant；不支持转移、合并、共享。
- 报告：Append-only；每 repo 有 **repo_latest_reports** 指针取最新；分享链接 7 天；不暴露 tenant_id/installation_id 给分享页。

---

## 8. Support policy（遇到冲突就 A：拒绝 + 联系支持）

- **tenant 已被其他用户绑定**：403，前端展示 "This GitHub account is already linked"，主按钮 Contact support。
- **installation 已绑其他 tenant**：409，提示联系支持。
- **支持侧**：不提供用户自助转移；仅管理员可做「强制解绑」（删 tenant+installation 绑定）后让用户重新从 Console 发起安装。流程与审计见 **RUNBOOK.md**。
