# 代码审查清单（抓“会让你背锅”的点）

---

## A. 契约一致性（Contract-first）

**目标**：Action / Console / API 三方口径永远一致。

| 检查点 | 要求 |
|--------|------|
| verdict.status | 只可能是 `allowed` \| `needs_approval` \| `approved` \| `blocked`；用常量 `VERDICT_*`，禁止裸字符串 |
| blocked 与 approval | **blocked 永远不能被 approval 提升**；任何路径都不允许在 blocked 分支里查 approvals 并改状态（重大事故） |
| explanations_mode | 必须和 repo_verdict 对应：blocked ⇒ OFFSEC_ONLY；needs_approval/approved ⇒ APPROVAL_SIGNALS_ONLY；allowed ⇒ NONE |
| reason_code | 必须来自注册表/枚举（`_verdict_to_reason_code`）；禁止散落字符串 |
| contract_version / policy_version | 必须回传且可追溯（写入 scan record） |

**审查动作**：

- 搜索全仓：`"blocked"`、`"needs_approval"` 等裸字符串（应走 `VERDICT_*` 常量）
- 搜索：blocked 分支里是否还有“查 approvals 并改状态”的逻辑（必须无）

---

## B. 归因（Attribution）只解释挡门原因

**目标**：blocked 分流（OffSec vs 硬阻断）；needs_approval 只给 requires_approval_signals 证据。

| 检查点 | 要求 |
|--------|------|
| blocked 的 Top3 候选 | **分流**：若有 `supports == "offsec_override"` ⇒ OFFSEC_ONLY（仅 offsec_override）；否则 BLOCK_REASONS_ONLY（仅 `blocked_other`，如 remote-pipe）。不混入 approval_signal。 |
| needs_approval 的候选 | 严格过滤 `supports == "approval_signal"` 且 signal ∈ policy.requires_approval_signals |

**常见翻车**：blocked 时只认 offsec_override，导致 remote-pipe 等硬阻断“blocked 但 Top3 空”；或为“凑 3 条”把 approval_signal 塞进 blocked 的 Top3。

---

## C. Top3 选择 deterministic（可复现）

**目标**：同一份 report 多跑几次，Top3 顺序完全一样。

| 检查点 | 要求 |
|--------|------|
| 排序 tie-breaker | 完整：severity → signal priority → file → line_start → code |
| 去重逻辑 | deterministic；用 **finding_id**（含 code/signal/file/line_start/supports/**rule_id**）去重，禁止用 dict 相等（同 file/line/code 多 pattern 会误合并） |
| 数组顺序 | explanations_top 数组顺序稳定 |

**finding 结构**：每条 finding 应有稳定 **rule_id**（或 detector_id/match_id），供 _finding_id 纳入 tuple，避免“同一行同一 code 多 rule 产出”被去重掉。

**快速验证**：同一份 report 跑 N 次 evaluation，hash(explanations_top) 必须一致；打乱 findings 顺序后 Top3 仍一致。

---

## D. Snippet 安全（别把 secret 打进 GitHub log）

| 检查点 | 要求 |
|--------|------|
| 截断 | ≤ 3 行、每行 ≤ N 字符（如 200） |
| mask | 覆盖 Bearer xxx、-----BEGIN PRIVATE KEY-----、AWS key 形态、长 token |
| 不安全时 | snippet 置空，但 file/line/pattern 仍要有 |

---

## E. 权限与审批（别让人绕过）

| 检查点 | 要求 |
|--------|------|
| approval 绑定 scope | 至少 repo@commit；校验 org/repo/commit 一致 |
| 鉴权 | 谁能 approve？（最少“仅 org 内特定角色/组”） |
| 审计字段 | approver、时间、理由、policy_version、evaluation_id/scan_id |
| 幂等 | 同一 commit 重复 approve 行为一致（不产生多条乱记录） |

---

## 相关文件

- Verdict 常量：`skillscan/engine.py`（VERDICT_ALLOWED / NEEDS_APPROVAL / APPROVED / BLOCKED）
- reason_code 映射：`skillscan/engine.py`（_verdict_to_reason_code）
- 归因与 Top3：`skillscan/explanations.py`（_attribution_candidates、_top3_select）
- 契约与 reason_code 注册表：`docs/evaluation-contract.md`
