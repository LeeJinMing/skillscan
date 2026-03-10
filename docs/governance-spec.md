# SkillScan Governance — 可开工规格

三条企业默认策略（定死，能卖）：

| 策略 | 选择 |
|------|------|
| 默认禁止 OffSec 类 skill 进入通用仓库 | **是** |
| 是否允许任何 skill “自动执行命令”？ | **默认否**，只能建议；执行必须审批 |
| 是否允许“红队隔离仓库”？ | **是**，且独立审计 |

策略定义见：`policy/policy.yaml`。OffSec 分类关键词见：`policy/offsec_ruleset.yaml`。

---

## 产品定义（一句话，写在首页/README）

**“我们不阻止你写扩展；我们阻止未经批准的 agent 扩展内容进入组织的可安装目录。”**

补一句更完整：

**SkillScan 是 agent extensions 的准入治理与审批控制层，当前先支持 `skills`。**

- 开发阶段：PR 风险提示（needs_approval → neutral，可 merge）。
- 分发/安装阶段：只有 Allowed 或（控制台）Approved 的版本可进入 Catalog / 可被安装；门禁卡在“被消费”处。

---

## Verdict 映射到 GitHub Checks

| verdict | PR 流水线（风险提示） | 发布流水线（门禁） |
|---------|------------------------|--------------------|
| **blocked** | **failure**（阻止 merge） | **failure**（不可进入 catalog） |
| **needs_approval** | **neutral**（可 merge，醒目提示 + 控制台链接） | **failure**（未审批不可发布；审批后可通过） |
| **allowed** | **success** | **success**（可进入 catalog） |

PR comment 建议写清：**Needs approval 的 skill 不会进入可安装目录/不会被企业内部允许使用，除非在控制台批准该 commit SHA。**

---

## 两条流水线

| 流水线 | 触发 | 行为 |
|--------|------|------|
| **官方流水线** | `pull_request`、`push` main、`release: published`、`workflow_dispatch` | 扫描 → 上传 report + attestation_bundle → 按最终 verdict 决策；PR 场景 blocked 失败，Release 场景 verdict 非 allowed/approved 失败 |

工作流文件：`.github/workflows/skillscan.yml`。  
发布门禁以 **release: published** 为主：发版即分发，发布前必须批准。

---

## Catalog（可安装目录）门禁

- **General Catalog**：只出现 **APPROVED** 的 repo@commitSHA（或 verdict=allowed 的版本）。
- **needs_approval** 的版本只在“扫描记录”里可见，**不进入 catalog**，直到人工审批。
- **OffSec**：默认不进入 General Catalog，只能进入 **RedTeam Catalog**（RBAC 隔离）。
- 实现：控制台加“Catalog”页面，列出 Approved 条目；安装端（未来商店/registry）只允许从 Catalog 拉取。

**Catalog 最小数据（Approved 版本如何进入/退出）**：

| 表/概念 | 字段/说明 |
|---------|-----------|
| catalog_entry | repo, commit_sha, skill_id, verdict_at_scan, approval_state (APPROVED/REJECTED/EXPIRED), approved_at, approved_by, policy_version |
| 进入 | 扫描后 verdict=allowed 或人工 Approve → approval_state=APPROVED → 写入 catalog_entry |
| 退出 | 新 commit 导致旧审批 EXPIRED；或人工 Reject/下架 → 从 Catalog 列表移除 |

**审批粒度（定死）**：MVP = **repo@commit**（审批 key：org_id + scope_type=repo_commit + scope_key=repo=org/repo + commit_sha）；未来扩 **artifact_path@commit**。当前 report 含 **skills[]**（本次扫描到的 skill 列表），后续可扩成统一 artifact 列表。repo 级 verdict 聚合：任一层 blocked⇒blocked，否则任一层 needs_approval⇒needs_approval，否则 allowed。详见 `docs/saas-api.md`、`docs/postgres-schema.sql`。

---

## General 默认策略（非 OffSec 10 条高收益规则）

| 类型 | 规则 | verdict | PR 表现 | 发布表现 |
|------|------|--------|---------|----------|
| OffSec | OffSec 分类器（AD/渗透/工具链） | **blocked** | failure | failure |
| 运维高权限 | sudo、service_control、write_system_paths、chmod_chown、network_download | **needs_approval** | neutral | failure（除非已审批） |
| 只读诊断 | systemctl status、journalctl、dig、curl -I 等 | **allowed** | success | success |

规则数据见：`rules/mvp-rules.json`。运维高权限“先放行但标 Needs Approval”，在发布关口强制审批。

---

## 1. 状态机（Skill Version 级别）

绑定粒度：`repo@commitSHA` 或 skill zip hash。

| 状态 | 说明 |
|------|------|
| SCANNED | 扫描完成，报告已产生 |
| BLOCKED | 自动判定封禁（如 OffSec 进 General） |
| NEEDS_APPROVAL | 自动判定需审批 |
| APPROVED | 人工审批通过 |
| REJECTED | 人工拒绝 |
| EXPIRED | 上游变化（新 commit/hash），旧审批不继承 |

**规则**：Approved 只对该版本有效；新 commit 一律回到 NEEDS_APPROVAL 或 BLOCKED。

---

## 2. 审计事件（表结构）

企业买的是“出了事能追责”。以下事件必须记录。

| 事件类型 | 说明 |
|----------|------|
| SCAN_CREATED | 扫描创建（报告上传） |
| VERDICT_COMPUTED | 判定结果（Blocked/NeedsApproval/Allowed） |
| APPROVED_BY_USER | 用户审批通过（who, when, scan_id） |
| REJECTED_BY_USER | 用户拒绝（who, when, scan_id） |
| VIEWED_SKILL | 查看 skill/报告 |
| DOWNLOADED_SKILL | 下载 skill（若支持） |
| POLICY_CHANGED | 策略变更（policy_version, who） |

**最小字段**：`event_type`, `timestamp`, `actor_id`, `resource_type` (scan/skill/project), `resource_id`, `details` (JSON)。

---

## 3. 红队隔离仓库（RedTeam Repo）落地要点

- RedTeam 不是“开放商店的一个分类”，而是**权限隔离域**。
- **MVP 最低要求**：
  - **RBAC**：只有 `redteam` 组用户能看到 RedTeam 仓库内容。
  - **审计**：查看/下载/批准都记录（VIEWED_SKILL、DOWNLOADED_SKILL、APPROVED_BY_USER）。
  - **版本锁定**：绑定 `repo@commitSHA`，任何更新都需重新审批（EXPIRED → 重新走流程）。

**对外话术**：“我们允许红队内容存在，但它与通用技能库完全隔离，默认不可见，不可安装，不可执行。”

---

## 4. “默认不自动执行”硬约束

- **报告字段**（强制）：`execution.mode = suggest_only`, `execution.enforced_by = policy`, `execution.requested = false`。
- **UI/交互**：所有“命令块”只提供 **Copy**，不提供 **Run**。
- **未来接 agent 执行器**：流程必须是“生成命令候选 → 审批 → 人工在终端执行 / 或受控执行器执行”。MVP 不接受控执行器，先把治理闭环卖出去。

---

## 5. MVP 页面（最少 4 个）

| 页面 | 功能 |
|------|------|
| **Projects** | 项目列表；每个项目绑定一个 repo 或技能集合 |
| **Scans** | 扫描记录列表；筛选：Blocked / Needs Approval / Approved |
| **Scan Detail** | 报告详情：命中规则、证据、capabilities、依赖摘要、对象列表 |
| **Approvals** | 待审批队列 + 操作（Approve/Reject）+ 审计 trail |

---

## 6. MVP API（最少）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/reports` | 上传扫描报告（只收 JSON，不收源码） |
| GET | `/scans/:id` | 获取扫描详情（报告 JSON） |
| POST | `/approve` | 审批通过（repo@commit） |
| POST | `/reject` | 拒绝（repo@commit） |
| GET | `/audit?project=...` | 审计日志（按项目/时间筛选） |
| GET | `/verdict?repo=...&commit_sha=...` | Release 门禁用：返回当前 verdict（含 approved） |

**SaaS 契约**：见 `docs/saas-api.md`（POST /reports 响应、GET /verdict、verdict 计算逻辑）。  
**Postgres 最小表结构**：见 `docs/postgres-schema.sql`（scans、approvals、audit_log）。

---

## 7. Blocked / Restricted 的 UI/审批流设计要点

- **Blocked**：在 Scans 列表和 Scan Detail 中醒目展示 `verdict_reason` 与 `endorsement_level: None`；不提供“申请放行”入口（企业策略即禁止）。
- **Needs Approval**：在 Approvals 队列中展示；操作只有 Approve / Reject；Approved 后状态变为 APPROVED，并写入审计（APPROVED_BY_USER）。
- **Restricted（红队）**：仅 redteam 组可见对应仓库；进入后仍为 suggest_only，查看/下载/批准均记审计。
- **列表筛选**：Scans 页支持按 verdict（Blocked / Needs Approval / Approved）、按项目、按时间筛选。

---

## 8. 相关文件

| 文件 | 说明 |
|------|------|
| `policy/policy.yaml` | 企业默认策略（三条定死 + repositories + rules） |
| `policy/offsec_ruleset.yaml` | OffSec 分类关键词表（可维护）；证据输出：关键词 + 位置 + category=offsec, verdict=blocked |
| `schema/report.json` | 报告 Schema，含 `execution` 块 |
| `docs/boundary-and-spec.md` | 产品边界、能力 Schema、规则、三类仓库 |
| `docs/saas-api.md` | SaaS 契约：POST /reports、GET /verdict 响应与 verdict 计算逻辑 |
| `docs/evaluation-contract.md` | Evaluation 响应契约：verdict 四态、reason_code、explanations_mode、Blocked OffSec-only、Action 退出码 |
| `docs/code-review-checklist.md` | 代码审查清单：契约一致、归因、Top3 确定性、snippet 安全、审批权限 |
| `fixtures/` + `tests/test_fixtures.py` | 固定测试向量（golden tests）锁死行为 |
| `docs/postgres-schema.sql` | Postgres 最小表结构：scans、approvals、audit_log |
| `docs/skill-discovery-rules.md` | Skill 发现规则：锚点（skill.yaml/SKILL.md）、file set、嵌套/过大 findings、skills[] 输出、repo 聚合 |
| `docs/category-and-policy-spec.md` | 分类权威：声明为准 + OffSec override；evaluate_scan 伪代码；signals；Release gate 返回 |
| `policy/general-default.json` | General 默认策略（可版本化）；offsec⇒blocked，requires_approval_signals |
| `policy/redteam-default.json` | RedTeam 默认策略；offsec⇒needs_approval |
| `policy/finding-templates.json` | Finding 解释模板（人话 summary/detail/remediation）；版本与 ruleset 绑定 |
| `policy/signal-templates.json` | Signal 解释模板（why_tpl、approve_checklist_tpl）；供审批理由 |
| `policy/skill.yaml.example` | skill.yaml 最小规范（id/title/category/version/entrypoint） |

## 9. 术语口径

- **Scanner**：负责取证和产出报告。
- **Governance**：负责准入、审批、复审、隔离、审计。
- **Artifact**：统一指被治理的扩展对象。
- **Skill**：当前第一个落地的 artifact 类型。

对外不要把项目讲成“单一 skill 扫描器”。  
更好的口径是：“先从 `skills` 切入的 agent 扩展治理层”。
