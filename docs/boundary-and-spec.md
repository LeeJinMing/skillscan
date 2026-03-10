# SkillScan：agent 扩展治理边界与规范

## 1. 边界（我们做什么 / 不做什么）

| 不做 | 做 |
|------|-----|
| 通用代码安全平台（Trivy/Scorecard 等已有优势） | **agent 扩展内容** 的“可治理结论”：Allowed / Needs Approval / Blocked，并给证据 |
| 依赖“玄学分数” | 策略落到**能力**上（Capability Schema） |
| 要求企业上传私有 zip/源码 | 扫描在客户本地/CI 跑；SaaS 只收 **report + 审计信息** |

**原则**：证据可定位（文件名 + 行号/片段 + 命中规则），否则“背书”是空话。

**当前切口**：先把 `skills` 做透。  
**产品边界**：从第一天起按“agent 扩展治理层”设计，后续可扩到 `MCP`、`workflow packs`、其他可安装扩展。

---

## 2. Capability Schema（核心数据结构）

- 存库与交换均用同一 JSON 结构。
- `level: suggest | execute`：区分“给命令”与“真的执行”，企业策略不同。
- 每个能力块均带 `evidence[]`：文件名、行号/片段、命中规则。

见：`schema/capability.json`。

**安全攻防类能力维度**（当命中 OffSec 规则时至少提取）：

- `offensive_security` = true  
- `targets_identity_systems` = true（AD/域控）  
- `credential_access`、`lateral_movement`、`privilege_escalation`、`exploitation_guidance`  
- `tooling_required` = [impacket, mimikatz, bloodhound, rubeus, crackmapexec, responder, …]

企业策略可基于“能力”禁止，而不是“看到命令就慌”。

---

## 3. 解析对象（MVP）

### 3.1 当前已实现对象

1. **SKILL.md** 的 YAML frontmatter：作者、用途、输入/输出、警告。
2. **Skill 目录内**：引用的命令/脚本（如 `references/*.md`、`*.sh`、`*.ps1`、`*.py`）。
3. **文档中的明确命令块**：Markdown 代码围栏里的 shell。

### 3.2 术语约定

- **Artifact**：被治理的扩展内容总称。
- **Skill**：当前第一个落地的 artifact 类型。
- **Scanner**：本地/CI 取证并产出报告。
- **Governance**：准入、审批、隔离、审计、复审。

不依赖 LLM 做“理解风险”；先把“命令和脚本”抓出来。

---

## 4. 10 条 MVP 审核规则

### Block（直接封禁）

| 规则 ID | 描述 | 命中模式 | 结果 |
|---------|------|----------|------|
| `block-remote-pipe` | Remote pipe execution | `curl .* \| (bash\|sh)`、`wget .* \| (bash\|sh)` | Blocked |
| `block-destructive-fs` | Destructive filesystem | `rm -rf /`、`mkfs.*`、`dd if=`、`wipefs`、`chmod -R 777 /`、`chown -R .* /` | Blocked |
| `block-priv-ssh` | User/privilege escalation / SSH tampering | 修改 `sshd_config`、`PermitRootLogin`、`authorized_keys` 写入、`sudoers` 修改 | Blocked |

### Needs Approval（强制审批）

| 规则 ID | 描述 | 命中 | 结果 |
|---------|------|------|------|
| `approval-sudo` | Any sudo requirement | `sudo` 或明确“需要 root” | NeedsApproval |
| `approval-service` | Service restart/stop/enable/disable | `systemctl restart/stop/enable/disable`、`pm2 restart/delete` | NeedsApproval |
| `approval-write-config` | Write under system config paths | 写 `/etc/*`、`/lib/systemd/*`、`/usr/lib/systemd/*`、`/etc/nginx/*` | NeedsApproval |
| `approval-permission` | Permission change | `chmod`/`chown`（尤其 `-R` 或变量路径）；路径不明确则升级 Blocked | NeedsApproval |
| `approval-network` | Network egress / download binary | `curl`/`wget` 下载文件、`apt`/`yum`/`brew` 安装、`npm`/`pip` 安装 | NeedsApproval |

### Allow（默认可放行，给风险提示）

| 规则 ID | 描述 | 命中 | 结果 |
|---------|------|------|------|
| `allow-readonly-diagnostics` | Read-only diagnostics | `systemctl status`、`journalctl`、`ss -lntp`、`nginx -t`、`dig`/`nslookup`、`curl -I` | Allowed |
| `allow-evidence-first` | Evidence-first：先收集日志/状态再建议修复 → 加分；“上来就重启/改配置” → 降级 NeedsApproval | 文案/流程判断 | 影响评级 |

规则数据见：`rules/mvp-rules.json`。

### Offensive Security 分类器（当前对 Skill 生效，后续可复用到其他 artifact）

| 规则 ID | 描述 | 命中（任一） | 结果 |
|---------|------|--------------|------|
| `block-offsec-ad-playbook` | AD 渗透/进攻性安全 playbook | 标题/描述/关键词：Active Directory 攻击、域渗透、Kerberoasting、DCSync、Golden/Silver Ticket、Pass-the-Hash、NTLM relay、BloodHound、Mimikatz、Impacket、CrackMapExec、Responder、Rubeus 等；或“交付成果”：提取凭据/哈希/票据/域管理员/持久化；或攻击工具名命令段 | **Blocked**，`verdict_reason` = Offensive security / AD exploitation guidance |

**要点**：这类内容在企业治理里默认封禁；就算作者写“红队/渗透测试用”，也不进入通用 skill 仓库，最多进入“隔离的红队私有库”。平台展示时必须明确：我们验证来源与版本完整性（attestation），**不为其用途与后果做安全承诺**。

---

## 5. Verdict 计算

- 命中任意 **Blocked** 规则 ⇒ **Blocked**
- 否则命中任意 **NeedsApproval** 规则 ⇒ **Needs Approval**
- 否则 ⇒ **Allowed**

输出附带 `risk_summary`：命中的规则 ID + 证据列表（文件:行/片段）。  
当 Verdict = **Blocked** 时，输出 `verdict_reason`（如 "Offensive security / AD exploitation guidance"）。  
输出 `endorsement_level`：**Full**（生产可用）、**Restricted**（仅红队/高权限仓库）、**None**（不背书，如 Blocked）。

---

## 5.1 背书体系（Endorsement）

| 背书等级 | 含义 | 典型场景 |
|----------|------|----------|
| Full | 来源与版本完整性可验证；可用于通用仓库 | Allowed、低风险 |
| Restricted | 仅允许进入“红队/安全团队专用仓库”；私有分发、明确授权、禁止自动执行、强制审批与审计 | NeedsApproval、或 OffSec 内容在隔离库 |
| None | 不背书；我们验证 attestation，**不为其用途与后果做安全承诺** | Blocked（含 OffSec playbook） |

---

## 6. 审批流状态机（版本级）

绑定粒度：`repo@commitSHA` 或 skill zip hash。

| 状态 | 说明 |
|------|------|
| UNSCANNED | 未扫描 |
| SCANNED | 自动产生 |
| NEEDS_APPROVAL | 自动产生 |
| APPROVED | 人工审批 |
| REJECTED | 人工拒绝 |
| EXPIRED | skill 更新到新 commit/hash，旧审批不继承 |

**规则**：任何版本漂移必须重新审批（审计底线）。

---

## 6.1 三类仓库/渠道（产品形态建议）

| 渠道 | 用途 | 默认策略 |
|------|------|----------|
| **General Extensions** | 生产可用、低风险 | Allowed / Needs Approval；Full 或 Restricted 背书 |
| **Privileged Ops Extensions** | 运维高权限（sudo/改配置） | 强审批；Restricted 背书 |
| **OffSec / RedTeam Extensions** | 红队/渗透测试 | **默认 Blocked**；仅“受限策略”下可见/可用（私有、授权、禁止自动执行、强制审计） |

这样安全负责人一眼能懂治理边界，便于企业侧销售。

---

## 7. MVP 架构

### 客户侧（必须）

- **skillscan CLI**：输入本地目录 / zip / GitHub repo（当前先以 `skills` 为主）；输出 `report.json` + 可选 `report.html` + `attestation.json`。

### SaaS 控制台

- **API**：治理控制层。
- **功能**：上传 report（非源码）、策略配置（后续）、审批、复审、审计、看板。
- **多租户**：按 org 隔离（MVP 最基础）。

---

## 8. 变现设计

推荐按 Open Core 来切：

| 开源层（Community） | 商业层（Enterprise / Hosted） |
|------|----------|
| CLI + 规则引擎 + 基础规则 | 组织级准入门禁、审批流、审计导出 |
| report schema + policy schema + 标准输出 | Org / Team 管理、RBAC、SSO、SCIM |
| 本地 HTML / JSON / SARIF 报告 | 组织策略中心、例外管理、到期复审 |
| GitHub Action / 基础 CI 集成 | 企业连接器、报表、趋势分析 |
| fixtures、golden tests、规则编写指南 | 高级规则包、信誉库、威胁情报、托管服务 |

原则只有一句：

**开源可验证的扫描层，商业化组织治理层。**
