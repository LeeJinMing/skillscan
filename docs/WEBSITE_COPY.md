# SkillScan Website Copy

这份文档是官网完整落地页文案草稿。  
目标不是写“很完整的公司介绍”，而是写“用户一落地就明白你卖什么”。

---

## 中文版

### 1. Hero 区

**Headline**  
给 AI agent 扩展内容加上准入治理。

**Subheadline**  
SkillScan 是 agent 扩展内容的准入治理与审批控制层。扫描只是开始。真正重要的是准入、审批、复审、隔离和审计。

**Supporting line**  
当前先支持 `skills`，后续扩展到 `MCP`、`workflow packs` 和其他可安装扩展。

**Primary CTA**  
预约演示

**Secondary CTA**  
查看 GitHub

### 2. 问题区

**Section title**  
企业担心的，不只是“扩展里有没有危险命令”

**Body**  
当团队开始引入 AI agent 扩展，真正的问题很快会变成治理问题，而不是单点检测问题。

他们会问：

- 谁能把扩展带进组织
- 什么能进入共享仓库
- 什么能被安装到正式环境
- 哪些高风险内容必须人工审批
- 升级后旧审批是否自动失效
- 红队类内容是否必须隔离
- 审计时能不能还原是谁批准了什么

SkillScan 解决的，就是这层控制问题。

### 3. 产品定义区

**Section title**  
不是一个扫描器增强版，而是一层治理控制面

**Body**  
SkillScan 可以拆成两层：

- **Scanner 输入层**：在本地或 CI 收集证据，生成标准报告
- **Governance 控制层**：对扩展做准入、审批、复审、隔离和审计

这样团队拿到的，不只是“有风险提示”。  
而是一套真正能卡住上线、卡住安装、卡住发布的流程。

### 4. 核心能力区

**Section title**  
你真正需要管住的 5 件事

**Cards**

**准入门禁**  
不合规扩展进不了仓、过不了发布。

**审批闭环**  
`needs_approval` 不只是提示，而是可执行的审批流程。

**版本复审**  
审批绑定 `repo@commit`。版本一变，旧批准自动失效。

**隔离策略**  
高风险内容可以限制在受控环境，不进入通用目录。

**审计追溯**  
谁上传、谁批准、为什么放行，都能回查。

### 5. 为什么现在切 skills

**Section title**  
为什么先从 `skills` 开始

**Body**  
因为 `skills` 是最容易落地、最容易触发治理需求、也最容易跑出闭环的入口。

但 SkillScan 的目标不是停在 `skills`。  
底层要解决的是所有 agent 扩展内容都会遇到的同一类问题：

- 准入
- 审批
- 复审
- 隔离
- 审计

这也是它后续能扩到 `MCP`、`workflow packs` 和更多 installable artifacts 的原因。

### 6. 工作流区

**Section title**  
先扫描，再决定能不能进生产

**Flow**

1. 本地或 CI 扫描扩展内容
2. 生成标准报告和证据
3. 服务端计算 verdict
4. 命中高风险则进入审批
5. 只有 Allowed 或 Approved 的版本才能进入安装或发布路径

### 7. 适合谁

**Section title**  
适合这些团队

- 在内部维护共享 agent 扩展仓库的平台团队
- 需要控制扩展准入和发布的安全团队
- 要做审批、审计、复审的合规团队
- 想把 AI agent 能力带进企业环境的产品团队

### 8. 对比区

**Section title**  
为什么不是“再做一个 scanner”

**Body**  
扫描器解决的是“发现风险”。  
SkillScan 要解决的是“发现之后，能不能进、能不能装、要不要批、出了事怎么查”。

所以它更接近治理层，而不是单个工具。

### 9. 结尾 CTA

**Headline**  
让 agent 扩展先过治理，再进生产。

**Body**  
从 `skills` 开始，把准入、审批、复审和审计变成一条清晰流程。

**CTA**  
预约演示  
查看文档

---

## English Version

### 1. Hero

**Headline**  
Govern AI agent extensions before they reach production.

**Subheadline**  
SkillScan is the governance and approval control layer for AI agent extensions. Scanning is only the first step. The real problem is admission, approval, re-review, isolation, and audit.

**Supporting line**  
It starts with `skills` today, and expands to `MCP`, `workflow packs`, and other installable artifacts over time.

**Primary CTA**  
Book a demo

**Secondary CTA**  
View on GitHub

### 2. Problem Section

**Section title**  
Enterprises worry about more than risky commands

**Body**  
Once teams start adopting AI agent extensions, the real problem quickly becomes governance, not just detection.

They need to answer:

- Who can introduce an extension
- What can enter the shared repository
- What can be installed in production
- What requires manual approval
- Whether prior approval expires after an update
- Whether high-risk content must stay isolated
- Whether every decision can be reconstructed during audit

SkillScan is the control layer for exactly that.

### 3. Product Definition

**Section title**  
Not just a better scanner. A governance control plane.

**Body**  
SkillScan has two layers:

- **Scanner input layer**: collects evidence locally or in CI and produces a standard report
- **Governance control layer**: handles admission, approval, re-review, isolation, and audit

That means teams get more than risk visibility.  
They get a real process that can block installs, releases, and distribution.

### 4. Core Capabilities

**Section title**  
The five things you actually need to control

**Cards**

**Admission control**  
Non-compliant extensions do not enter repos or release paths.

**Approval workflow**  
`needs_approval` becomes an enforceable workflow, not just a warning.

**Version-aware review**  
Approval is tied to `repo@commit`. New version, new review.

**Isolation policy**  
High-risk content can be restricted to controlled environments.

**Audit trail**  
Every upload, approval, and release decision is traceable.

### 5. Why start with skills

**Section title**  
Why start with `skills`

**Body**  
Because `skills` are the clearest entry point to operationalize governance fast.

But SkillScan is not limited to `skills`.  
The underlying problems are the same across agent extension artifacts:

- admission
- approval
- re-review
- isolation
- audit

That is why the product can expand into `MCP`, `workflow packs`, and other installable artifacts.

### 6. Workflow Section

**Section title**  
Scan first. Then decide what reaches production.

**Flow**

1. Scan extension content locally or in CI
2. Generate a standard report with evidence
3. Let the server compute the final verdict
4. Route risky versions into approval
5. Allow only Allowed or Approved versions into install and release paths

### 7. Who it is for

**Section title**  
Built for teams like these

- Platform teams managing shared agent extension repositories
- Security teams that need admission control and release gates
- Compliance teams that need approval and audit workflows
- Product teams bringing AI agent capabilities into enterprise environments

### 8. Positioning Section

**Section title**  
Why this is not just another scanner

**Body**  
A scanner answers “what risk exists.”  
SkillScan answers “what happens next.”

Can it enter the repo?  
Can it be installed?  
Does it require approval?  
Can it stay isolated?  
Can we reconstruct every decision later?

That is why SkillScan is a governance layer, not just a tool.

### 9. Closing CTA

**Headline**  
Govern agent extensions before they ship.

**Body**  
Start with `skills`, and turn admission, approval, re-review, and audit into one clear workflow.

**CTA**  
Book a demo  
Read the docs
