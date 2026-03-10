# 端到端验收与工程保障

## 1. 端到端验收（如何验证）

**需要你本地/真实 GitHub 做一次“假发布”**（当前无 SaaS 时，可只验 CLI + report 一致性）。

| 验证点 | 操作 | 期望 |
|--------|------|------|
| **PR/Release workflow log** | 在 PR 或 release 的 Action 日志里看输出 | 有 repo_explanation + Top3 + “See console…” |
| **Console** | （未来）在 Console 看该 scan | 全量 findings，且 Action 的 Top3 在 Console 里**按同样排序**能找到 |
| **审批流** | needs_approval 的 release 先不批 → 再点 approve → 同 commit 再触发 release | 审批前失败；审批后同 commit 再跑 → approved 并放行 |
| **blocked** | blocked 的 release，点 approve（若有入口） | 永远失败，审批不改变 verdict |

**验收通过标准（写死）**：

- 同一 commit 重跑 N 次，**结论与 Top3 不变**。
- 任意 **blocked 不能通过任何审批路径放行**。
- Action 日志**不出现敏感 token**（可在 report 里故意注入假 token 验证 mask）。

---

## 2. 最少要补的工程化保障

| 保障 | 现状 / 建议 |
|------|-------------|
| **单元测试** | `tests/test_fixtures.py` 覆盖：allowed / needs_approval / **approved** / blocked / **blocked+approval 不提升** / **blocked 无证据→synth** / **Top3 去重与确定性** / reason_code 映射；CI 必跑 |
| **集成测试** | API + DB（approval）+ fixture report → 需 SaaS 后补 |
| **回归锁定** | fixtures 作 golden；同一 report 多跑 hash(explanations_top) 一致 |
| **日志与追踪** | 每次 evaluation 输出 **evaluation_id**，Console 按 id 查全链路 → 需 SaaS 后补（scan_id / evaluation_id） |

**最小验收标准（可上线前必达）**：

- `tests/test_fixtures.py` 一键跑完（9 个用例），CI 必跑。
- 覆盖：allowed / needs_approval / approved / blocked / **blocked+approval 不能提升**（对抗性测试）/ **blocked 无证据→OFFSEC_OVERRIDE_SYNTH** / **Top3 去重与确定性** / reason_code 注册表。
- 任意 **blocked 不可被 approval 放行**（`apply_approval_elevation("blocked", True) == "blocked"` 锁死）。
- Top3 输出稳定、可预测；排序规则见 `skillscan/explanations.py`（severity → signal priority → file → line_start → code）。

---

## 3. MVP 三件（脱敏示例）

### 3.1 POST /evaluate 的 response JSON（needs_approval 例子）

当前无 SaaS，等价于 **CLI 产出的 report.json 中与“上报后服务端应返回”一致的部分**。未来 `POST /reports` 或 `POST /v1/evaluations` 建议返回形如：

```json
{
  "contract_version": "2026-02-01",
  "repo_verdict": {
    "status": "needs_approval",
    "reason_code": "REQUIRES_APPROVAL_HIGH_RISK_SIGNALS"
  },
  "explanations_mode": "APPROVAL_SIGNALS_ONLY",
  "repo_explanation": {
    "title": "Release requires approval",
    "text": "High-risk operational behaviors were detected. Approval is required before publishing.",
    "checklist": [
      "Is it restricted to maintenance windows or non-prod?",
      "Is there a health-check and automatic rollback on failure?",
      "Is the affected service list explicit and minimal?"
    ]
  },
  "explanations_top": [
    {
      "level": "finding",
      "code": "APPROVAL_SUDO",
      "title": "Requires elevated privileges (sudo/admin)",
      "text": "Running as admin increases blast radius... Evidence: SKILL.md:22-22.",
      "snippet": "sudo systemctl restart nginx",
      "checklist": ["Is the target scope (hosts/env) explicitly limited?", "..."]
    }
  ],
  "console_url": "https://console.example.com/scans/<scan_id>"
}
```

（上为 needs_approval 时；blocked 时 `status`=blocked；`explanations_mode` 分流：OffSec ⇒ OFFSEC_ONLY，remote-pipe 等硬阻断 ⇒ BLOCK_REASONS_ONLY。）

### 3.2 Top3 选择函数（核心代码片段）

见 `skillscan/explanations.py`：

- **归因**：`_attribution_candidates(repo_verdict, finding_entries)` — blocked 分流：若有 `supports == "offsec_override"` 则 OFFSEC_ONLY（仅 offsec_override）；否则 BLOCK_REASONS_ONLY（仅 `blocked_other`，如 remote-pipe）。needs_approval 只取 `supports == "approval_signal"`。
- **排序**：`_sort_key(entry)` → `(-severity_weight, -signal_priority, file, line_start, code)`。
- **选 3**：`_top3_select(candidates)` — 先不同 signal，再不同 file，再按序补齐至 3。

### 3.3 approval 表结构/字段

见 `docs/postgres-schema.sql` 中 approvals 表：

- **approvals**：id, org_id, scope_type, scope_key, repo, commit_sha, skill_path, status (approved/rejected), decided_by, decided_at, comment；唯一 (org_id, scope_type, scope_key, commit_sha)。
