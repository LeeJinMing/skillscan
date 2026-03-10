# SaaS 最小接口契约（Action 依赖）

服务端**必须**在落库后按策略重算 verdict（不信任客户端 report 自带的 verdict），否则伪造 report 会绕过门禁。

**信任链与错误码**：Sigstore keyless 校验、OIDC issuer、identity/workflow allowlist、report digest 校验及 401/422/402/429 约定见 [attestation-and-trust.md](attestation-and-trust.md)。

---

## 审批粒度（定死，避免后续重构）

| 阶段 | 审批 scope | Approval key |
|------|------------|--------------|
| **MVP** | **repo@commit** | scope_type=`repo_commit`，scope_key=`repo=org/repo`，(org_id, scope_type, scope_key, commit_sha) 唯一 |
| **未来** | skill_path@commit | scope_type=`skill_path_commit`，scope_key=`repo=org/repo;path=skills/xxx/SKILL.md`，skill_path 填值 |

- **scope_key 规范**：repo_commit 时 `repo=<org/repo>`；skill_path_commit 时 `repo=<org/repo>;path=<相对路径>`。
- GET /verdict、POST /approve、POST /reject 当前按 **repo + commit_sha** 查/写；未来增加参数 skill_path 或 scope_type 即可，旧数据不破坏。

---

## POST /reports

**请求**

- Content-Type: `multipart/form-data`
- File field: `report`
- File field: `attestation_bundle`
- Optional field: `repo_full_name`（开发环境跳过 cosign 时兜底）

**响应（固定结构）**

```json
{
  "scan_id": "uuid",
  "verdict": {
    "status": "blocked | needs_approval | allowed | approved",
    "reason": "..."
  },
  "approval_elevation_applied": false,
  "approval_scope_matched": null,
  "console_url": "https://console.yourapp/scans/uuid"
}
```

- **status**：服务端计算后的最终 verdict。
- **approval_elevation_applied**（契约要求）：本次 verdict 是否由“needs_approval + 审批通过”提升为 approved；blocked 永不提升，故为 false。
- **approval_scope_matched**（契约要求）：当 approval_elevation_applied 为 true 时，填 `{ "type": "repo_commit", "key": "repo=org/repo", "commit_sha": "abc..." }`；否则 null。便于前端/Action/审计看到“这次 approved 是怎么来的”。
  - **approved**：基础 verdict 为 needs_approval，且当前 org+repo+commit_sha 存在审批通过记录。
  - 其余同 report：blocked / needs_approval / allowed。

---

## GET /verdict

Release 流水线可再查一次当前 commit 是否已审批（可选，更稳）。

**请求**

- Query: `repo=org/repo`, `commit_sha=abc123...`

**响应**

```json
{
  "status": "approved | allowed | needs_approval | blocked",
  "scan_id": "uuid",
  "console_url": "https://console.yourapp/scans/uuid"
}
```

- 按 org + **repo + commit_sha** 查最新 scan 与 approvals（MVP：scope_type=repo_commit，scope_key=repo=org/repo）；若 needs_approval 且有 approved 记录则返回 **approved**。

---

## Verdict 计算逻辑（服务端）

1. 用 **ruleset**（或 report 内 skills[] 聚合）计算基础 verdict：**blocked** | **needs_approval** | **allowed**（不直接采信客户端 verdict）。
2. **Repo 级聚合规则**（多 skill 时）：任一层 blocked ⇒ repo blocked；否则任一层 needs_approval ⇒ repo needs_approval；否则 allowed。
3. 若基础 verdict 为 **needs_approval**：
   - 查表 **approvals**：MVP 查 `org_id, scope_type='repo_commit', scope_key='repo=<repo>', commit_sha` 且 `status = 'approved'`。
   - 有则最终 verdict 为 **approved**；无则保持 **needs_approval**。
4. 若基础 verdict 为 blocked 或 allowed，不再查审批，直接返回。

这样 Release workflow 只需根据返回的 `verdict.status` 判断：**allowed | approved → success**，**needs_approval | blocked → failure**。

**Release gate 返回约定（Action 依赖）**：

| 服务端返回 status | Action 行为 |
|-------------------|-------------|
| **blocked** | 直接 fail |
| **needs_approval** | fail + console_url 引导审批 |
| **approved** / **allowed** | pass |

- **approved**：同一 repo@commit 已审批，放行。**blocked** 永不因 approval 放行。

**显示策略**：失败时只展示 **Top 3** findings（来自 **explanations_top**）+ 固定尾句 “See console for full details: &lt;console_url&gt;”。服务端响应建议字段：`verdict`, **explanations_top**（已排序去重后的 1–3 条）, **console_url**。Action 只负责打印，不负责选 Top 3。

---

## SaaS 侧 approval 对抗性测试（必做）

本仓只测 `apply_approval_elevation(blocked, True) == blocked`；SaaS 必须补以下对抗性用例，否则本仓 tests 都过，线上照样能绕过：

| 用例 | 输入 | 期望 |
|------|------|------|
| **blocked + approval** | 基础 verdict=blocked，存在该 repo@commit 的 approved 记录 | 最终 verdict 仍为 **blocked**（永不因 approval 放行） |
| **needs_approval + approval(scope mismatch)** | 基础 verdict=needs_approval，存在 approval 但 **commit_sha 不同**（或 repo/org 不同） | 最终 verdict 仍为 **needs_approval** |
| **needs_approval + approval(expired/revoked)** | 基础 verdict=needs_approval，存在 approval 但状态为 expired 或 revoked（若你们支持撤销/过期） | 最终 verdict 仍为 **needs_approval** |

- 实现要点：查 approval 时必须校验 org_id + scope_type + scope_key + **commit_sha** 完全一致；若支持过期，需校验 approved_at / expires_at。

---

## 迁移策略（repo@commit → skill_path@commit）

- **policy 预留**：未来增加 `approval_granularity: repo_commit | skill_path_commit`。
- **新审批**：默认写 scope_type=skill_path_commit、scope_key 含 path。
- **老审批**：repo_commit 视为“全 repo 放行”；UI 可标“legacy approval”；更严格客户可配置“升级后 legacy 不再生效”。
