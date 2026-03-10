# 分类与策略计算规范（权威来源）

**原则（定死）**：声明分类仅用于默认归类；若内容命中 OffSec 规则，系统会强制升级为 **offsec** 并按 OffSec 策略处理。

---

## 1. 分类权威：声明为准 + OffSec override

| 来源 | 含义 |
|------|------|
| **declared_category** | 从 skill.yaml / SKILL.md 读到的原始声明（客户端上报） |
| **effective_category** | 服务端计算后写回：`declared_category`，若 **offsec_hit** 则强制为 `"offsec"` |
| **offsec_hit** | 规则扫描命中 OffSec 关键词/工具链（可解释证据，非 ML） |

---

## 2. 服务端计算顺序（唯一权威）

客户端 report 可带“自评 verdict”，**服务端一律重算**，否则伪造 allowed 可绕过门禁。

### evaluate_scan(org_id, repo, commit_sha, report)

```
policy = load_policy(org_id, repo)   # general-default | redteam-default

skills_out = []
for skill in report.skills:
  declared = skill.declared_category   # 来自 skill.yaml，无则 'unknown'

  # Step 1: 规则扫描得到 signals（不直接给 verdict）
  signals = detect_signals(skill)     # offsec_hit, uses_sudo, service_control, ...

  # Step 2: effective_category（声明为准 + offsec override）
  effective_category = declared
  if signals.offsec_hit:
    effective_category = "offsec"

  # Step 3: 按 effective_category + signals 套 policy 得 skill_verdict
  skill_verdict = policy.default_verdict
  if effective_category == "offsec" and policy.repo_zone == "general":
    skill_verdict = policy.category_rules.offsec.verdict   # blocked
  else if any(s in policy.requires_approval_signals for s in signals):
    skill_verdict = "needs_approval"
  # else allowed

  skills_out.append(skill with effective_category, signals, skill_verdict)

# Step 4: 聚合 repo verdict
repo_verdict = aggregate(skills_out)
# any blocked => blocked
# else any needs_approval => needs_approval
# else allowed

# Step 5: 审批升级（repo@commit）
approval = find_approval(org_id, scope_type="repo_commit", repo, commit_sha)
if approval.status == "approved" and repo_verdict == "needs_approval":
  repo_verdict = "approved"
# repo blocked 永不因 approval 放行

return { skills_out, repo_verdict }
```

---

## 3. report.json 必含字段（支持 override）

| 层级 | 字段 | 说明 |
|------|------|------|
| skill | **declared_category** | 客户端从 skill.yaml 上报 |
| skill | **effective_category** | 服务端计算后写回（存库） |
| skill | **signals** | 扫描命中信号列表（可解释、可审计） |
| skill | findings | 证据 file/line/match |

客户端上报至少要有 **declared_category** + evidence；**signals** / **effective_category** 由服务端生成并存。

---

## 4. Signals 列表（scanner 输出 / 服务端从 evidence 推导）

每个 signal 须能给出证据（文件/行号）。MVP 规则 ID → signal 映射：

| rule_id（示例） | signal |
|-----------------|--------|
| block-offsec-ad-playbook | offsec_hit（且 credential_access 等子信号） |
| approval-sudo | uses_sudo |
| approval-service | service_control |
| approval-write-config | writes_system_paths |
| approval-permission | chmod_chown |
| approval-network | network_download_exec |
| （预留） | shell_exec, process_injection, persistence |

---

## 5. Release gate 返回（Action 依赖）

| 服务端返回 status | Action 行为 |
|-------------------|-------------|
| **blocked** | 直接 fail |
| **needs_approval** | fail + console_url 引导审批 |
| **approved** / **allowed** | pass |

- **approved**：同一 repo@commit 已审批，放行。
- **blocked**：永不因 approval 放行。

---

## 6. 默认 Policy（可版本化）

- **general-default**：`policy/general-default.json`（offsec ⇒ blocked；requires_approval_signals 含 uses_sudo, service_control, writes_system_paths, chmod_chown, credential_access, network_download_exec, shell_exec, process_injection, persistence）
- **redteam-default**：`policy/redteam-default.json`（offsec ⇒ needs_approval；同一批 requires_approval_signals）

Policy 版本号建议 `policy_version=2026-02-01`，存库与 API 返回均带 `policy_version`。

---

## 7. UI 最小能力（先别大而全）

- **Scan Detail**：列出 skills（effective_category、signals、findings）
- **Approve repo@commit**：一个按钮 + 审批理由
- **Policy Profile**：只支持切换 general-default / redteam-default（先不开放自定义编辑器）

---

## 8. 解释模板（English-first，MVP 交付）

**研发负责人 + 安全联合审批**：每条模板必须一句话风险 + 一句话影响 + 三条可执行检查清单；不写安全黑话（CWE 等），关心会不会炸生产、能不能回滚、能不能审计。

- **Finding 模板**：`policy/finding-templates.json`（key: **finding_templates**）
  - 字段：code, severity, signal, **title**, **risk_summary**（一句话风险）, **impact_summary**（一句话影响）, detail_tpl, remediation_tpl, **approval_checklist**（3 条）。
  - 证据：file, line_start, line_end, match；**snippet 最多 3 行**。
- **Signal 模板**：`policy/signal-templates.json`（key: **signal_templates**）
  - 字段：name, title, **why**（一句话为什么需要审批/为什么 blocked）, **approval_checklist**（3 条）。
- **explanations 输出**：report 内 `explanations[]`（英文）：level: repo | finding, title, text, checklist?, code?, snippet?；UI 与 Action **共用同一套**，避免两套口径。
- **显示策略（定死）**：Release gate 失败时只展示 **Top 3** findings + “See console for full details: &lt;url&gt;”。GitHub log 不是审计台，刷屏会让人直接忽略。
- **explanations_top**：仅从**导致 repo verdict 的 findings**（归因）中取 Top 3；稳定排序（severity 权重 + signal 优先级 + file/line/code）；优先不同 signal，其次不同 file，再补齐。
- **归因**：blocked → candidate = supports in (offsec_override, blocked_other)；needs_approval → approval_signal；allowed → 不输出 Top 3。
- **Snippet 安全**：最多 3 行、每行 200 字；对 Bearer token、AWS key、私钥头等做简单 mask；无法安全截取时 snippet 置空，只留 file:line。
- **合成 finding**：当 blocked 且没有任何 supports=offsec_override 的证据时，补一条 OFFSEC_OVERRIDE_SYNTH（file=skill.path，text 含 ruleset_version）。
- **Action 使用**：打印 repo explanation + **explanations_top**（1–3 条）+ 固定尾句 “See console for full details: &lt;console_url&gt;”。Console 展示全量 findings，按相同排序规则，保证 Action 看到的 Top 3 在 Console 里可找到。
- **未来 i18n**：在每个 template 上加 i18n_key，保留英文文案为默认 fallback；MVP 不建多语言体系。

---

## 9. 相关文件

| 文件 | 说明 |
|------|------|
| `policy/general-default.json` | General 默认策略（可版本化） |
| `policy/redteam-default.json` | RedTeam 默认策略 |
| `policy/finding-templates.json` | Finding 解释模板（可版本化） |
| `policy/signal-templates.json` | Signal 解释模板（审批理由/checklist） |
| `docs/saas-api.md` | POST /reports、GET /verdict 契约 |
| `docs/postgres-schema.sql` | scans、approvals 表结构 |
