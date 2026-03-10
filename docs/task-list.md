# Skill Governance — 可排期开发任务清单

选 **A) GitHub Action 优先**：最快拿到真实样本和迭代规则；CLI 为企业后续必需品。

---

## report.json 合同（v1）

- **Schema**：`schema/report-v1.json`
- **必含**：`schema_version`, `scanner`, `source`, `input_fingerprint`, `skill`, `verdict`, `findings`, `timing`
- **evidence 强约束**：`file` + `line_start` / `line_end` + `match`（否则背书无法解释）
- **ruleset_version**：规则一变结论可能变，审计必须可追溯
- **input_fingerprint**：`type: content-hash | git-tree`，`sha256` 保证报告对应这份内容

---

## 第 1 周：能跑通 PR 扫描

| 任务 | 说明 | 验收 |
|------|------|------|
| skillscan 输出 v1 report | 只做 SKILL.md 发现 + 行号证据（file, line_start, line_end, match）+ OffSec 关键词规则 | `skillscan scan . --format v1 --output-dir .` 产出符合 report-v1.json 的 report.json |
| GitHub Action 骨架 | on: pull_request (+ push main)；checkout → 安装 skillscan → 运行 scan → 产出 report.json | PR 触发后 job 成功并生成 report.json |
| 失败阻止合并 | blocked 时 Check 失败（读取 report.json 的 verdict.status） | verdict=blocked 时 job 失败 |
| SaaS：POST /reports | 接收 report.json，存储（Postgres） | 上传后可查 scan_id / console_url |

**交付**：PR 触发扫描、本地/CI 产出 v1 report、blocked 阻止合并、报告可上报 SaaS。

---

## 第 2 周：治理闭环（能卖）

| 任务 | 说明 | 验收 |
|------|------|------|
| 控制台：Scan 列表 | 筛选 Blocked / Needs Approval / Approved | 列表展示 verdict、时间、skill_id |
| 控制台：Scan 详情 | findings/evidence/capabilities，行号可点 | 证据可定位到 file:line_start-line_end |
| 审批接口 + 按钮 | `POST /approve`、`POST /reject`；写入审计日志 | 审批后状态变更，审计可查 |
| 状态机 | SCANNED → BLOCKED / NEEDS_APPROVAL → APPROVED / REJECTED / EXPIRED | 版本漂移后旧审批 EXPIRED |

**交付**：Scan 列表/详情、审批流、状态机、审计记录。

---

## 第 3～4 周：变成企业产品

| 任务 | 说明 | 验收 |
|------|------|------|
| RBAC | admin / approver / viewer | 仅 approver 可点审批 |
| 组织/项目隔离 | multi-tenant，按 org/project 隔离 scan | 只能看本 org 的 scan |
| PR comment（可选） | 把 verdict + console link 回写到 PR | PR 下方出现评论 |
| 策略版本化 | policy@date，可导出审计 | 报告带 policy_version，可追溯 |

**交付**：RBAC、多租户、可选 PR 评论、策略版本与审计。

---

## SaaS 接口（最少）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /reports | 上传 report.json；返回 `{ scan_id, verdict: { status, reason }, console_url }` |
| GET | /scans/:id | 获取扫描详情（报告 JSON） |
| POST | /approve | 审批通过（repo@commit） |
| POST | /reject | 拒绝 |
| GET | /audit?project=... | 审计日志 |

---

## 强约束（必须实现）

1. **suggest-only 强制**：报告里 `execution_mode=suggest_only`，控制台 UI 不提供 Run。
2. **OffSec 默认 Blocked（General 仓库）**：AD 攻击类 skill 必须自动挡住。
3. **版本漂移必复审**：commit SHA 一变，原 Approved 不继承（EXPIRED）。

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `schema/report-v1.json` | v1 合同 Schema |
| `.github/workflows/skillscan.yml` | GitHub Action：官方扫描 + 上传 + 门禁 |
| `skillscan/cli.py` | `--format v1`、`--repo/--ref/--commit-sha`、GITHUB_* 环境变量 |
| `skillscan/engine.py` | `build_report_v1`、`risk_summary_to_findings`（line_start/line_end/match） |
