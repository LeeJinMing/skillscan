# Evaluation 响应契约（API / Action 口径）

**目标**：前端与 Action 只负责渲染，不重算 Top 3、不重排 findings、不自己拼 repo 文案。契约版本化，breaking change 必须 bump contract_version。

---

## 1. Verdict 四态（全局枚举）

| status | 语义 |
|--------|------|
| **allowed** | 按当前 policy 可直接发布/执行 |
| **needs_approval** | 可通过审批放行；release gate 必须拦 |
| **approved** | 存在匹配 scope 的有效审批记录，视为放行；release gate 放行 |
| **blocked** | policy 永久禁止；**审批不能放行** |

**允许迁移**：needs_approval → approved（找到有效审批）；其它不变。  
**禁止**：blocked → approved/allowed。

---

## 2. reason_code 注册表（稳定，勿随手改）

| reason_code | 含义 |
|-------------|------|
| OK_ALLOWED | 允许 |
| OK_APPROVED | 已审批放行 |
| REQUIRES_APPROVAL_HIGH_RISK_SIGNALS | 需审批（高风险信号） |
| POLICY_OFFSEC_BLOCKED_IN_GENERAL | OffSec 在 General 被策略禁止 |
| **POLICY_BLOCK_REMOTE_PIPE** | remote-pipe 硬阻断（curl\|wget ... \| bash/sh） |
| **POLICY_BLOCK_DESTRUCTIVE_FS** | 破坏性文件系统操作硬阻断（rm -rf /、mkfs、wipefs 等） |
| **POLICY_BLOCK_PRIV_SSH** | 私钥/SSH 篡改硬阻断（sshd_config、authorized_keys、sudoers 等） |
| **POLICY_BLOCKED_OTHER** | 其它硬阻断（未映射的 block-* 规则） |
| INVALID_REPORT | report 缺字段/解析失败 |
| POLICY_PROFILE_NOT_FOUND | 策略配置错误 |

blocked 时 reason_code 由 `_block_reason_code(skills_data, repo_findings)` 产出，必须来自上述常量。新增 reason_code 须走 code review，禁止随意写字符串。

**reason_code 命名约定（契约，勿破）**：`validate_verdict_reason()` 依赖此前缀判断，违反会导致校验误判。

| verdict.status | reason_code 约定 |
|----------------|-------------------|
| **allowed** | 固定 `OK_ALLOWED` |
| **approved** | 固定 `OK_APPROVED` |
| **needs_approval** | 必须以 `REQUIRES_APPROVAL_` 开头 |
| **blocked** | 必须以 `POLICY_` 开头 |

例如：blocked 下不可使用不带前缀的 `BLOCK_REMOTE_PIPE`，须为 `POLICY_BLOCK_REMOTE_PIPE`。新增 reason_code 须遵守上表，否则单测与校验会失败。

---

## 3. explanations_mode（Top 3 选择逻辑，基于 reason_code 注册表）

分流条件**只查 reason_code 注册表**（不靠 startswith/猜字符串）：`reason_code in REASON_CODE_OFFSEC ⇒ OFFSEC_ONLY`，`reason_code in REASON_CODE_BLOCK_REASONS ⇒ BLOCK_REASONS_ONLY`。**mode 唯一收口**：`explanations_mode_from(verdict_status, reason_code)`（单测覆盖），防止 CLI/服务端/库里各写一份导致口径漂移。

| mode | 含义 |
|------|------|
| **OFFSEC_ONLY** | blocked 且 reason_code=POLICY_OFFSEC_BLOCKED_IN_GENERAL：Top 3 仅 supports=offsec_override；不足 3 条用合成 OffSec finding 补齐 |
| **BLOCK_REASONS_ONLY** | blocked 且 reason_code∈{POLICY_BLOCK_REMOTE_PIPE, POLICY_BLOCK_DESTRUCTIVE_FS, POLICY_BLOCK_PRIV_SSH, POLICY_BLOCKED_OTHER}：Top 3 仅 supports=blocked_other。**规则**：reason_code 为 BLOCK_REASONS 时永远走 BLOCK_REASONS_ONLY，不被 offsec effective_category 抢解释权。 |
| **APPROVAL_SIGNALS_ONLY** | needs_approval 时：Top 3 仅来自 supports=approval_signal |
| **NONE** | allowed：不输出 Top 3 |

---

## 4. Blocked 场景（OffSec-only）锁死规则

- **candidate** = 仅 supports == "offsec_override"（禁止混入 approval_signal / info）。
- **不足 3 条**：按“每个触发 offsec 的 skill”生成 OFFSEC_OVERRIDE_SYNTH（file=skill.path），直到 3 或 skill 用完；仍不足则输出 N&lt;3 条，**不**为凑数塞非 OffSec。
- **排序**：severity + signal priority + file/line/code；Top 3 去重优先不同 file（不强制不同 signal）。
- **repo_explanation**（blocked 固定）：title = "Release blocked by policy (OffSec content in General)"；text = "This repository contains skills classified as OffSec. OffSec distribution is blocked in the General profile by policy."；checklist = 3 条（RedTeam 迁移 / 移除或重构 OffSec / 重扫重试）。

---

## 5. 客户端渲染顺序（Action / UI）

1. repo_verdict.status + repo_explanation.title  
2. repo_explanation.text  
3. repo_explanation.checklist（最多 3 条）  
4. explanations_top（最多 3 条）  
5. 固定尾句：**See console for full details: {console_url}**

客户端不得自行：重算 Top 3、重排 findings、自拼 repo 文案。

---

## 6. GitHub Action / CI 退出码

| 场景 | exit code |
|------|-----------|
| Release gate：allowed / approved | 0 |
| Release gate：needs_approval / blocked | 1 |
| PR 阶段：blocked | 1 |
| PR 阶段：needs_approval | 0（输出 warnings + console_url） |

---

## 7. 响应必须字段（MVP）

- **contract_version**：响应契约版本（e.g. 2026-02-01）  
- **verdict.status** + **verdict.reason_code**  
- **explanations_mode**  
- **repo_explanation**（title, text, checklist）  
- **explanations_top**（0–3 条）  
- **console_url**  

人话一律放在 repo_explanation 和 explanations_top，不塞进 verdict。
