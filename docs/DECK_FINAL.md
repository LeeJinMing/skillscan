# SkillScan Deck Final

这份文档是更接近正式 PPT 排版稿的版本。  
每一页都包含：

- 页标题
- 页副标题
- 页面主文案
- 演讲要点
- 建议图示

---

## 中文版

### 第 1 页：封面

**标题**  
SkillScan：AI agent 扩展内容的准入治理控制层

**副标题**  
让 AI agent 扩展先过治理，再进生产

**主文案**  
我们帮助企业在扩展进入仓库、安装路径和生产环境之前，先完成准入、审批、复审和审计控制。

**演讲要点**

- 我们不是做“又一个 scanner”
- 我们做的是 agent 扩展进入企业系统前的控制层
- 先从 `skills` 切入，但底层问题不止 `skills`

**建议图示**

- 封面图可用一条简洁流程线：
  `Scan -> Verdict -> Approve -> Ship`

### 第 2 页：问题

**标题**  
AI agent 扩展开始增多，但企业没有治理层

**副标题**  
问题不是“能不能生成”，而是“能不能进入系统”

**主文案**

- 扩展一旦变多，问题不再只是“有没有风险”
- 企业真正卡在“谁能装、什么能进、哪些要批、升级后要不要重审”
- 今天很多团队只有扫描，没有完整治理闭环

**演讲要点**

- 扩展一多，组织就会遇到准入问题
- 这和单次代码扫描不是一个层级的问题
- 一旦进入共享仓库或生产环境，风险就从“发现”变成“控制”

**建议图示**

- 左侧放“扩展增长”
- 右侧放“治理缺位”
- 中间用箭头连出风险外溢

### 第 3 页：为什么旧方案不够

**标题**  
只有 scanner，不等于有治理

**副标题**  
发现风险，不等于阻止风险进入生产

**主文案**

- 发现风险，不等于能阻止风险进入生产
- 有提示，不等于有审批闭环
- 有本地扫描，不等于有组织级审计和复审
- 企业买单的不是“看见问题”，而是“控制问题怎么进入系统”

**演讲要点**

- Scanner 是必要条件，不是充分条件
- 企业真正需要的是流程和控制权
- 这正是 SkillScan 的产品边界

**建议图示**

- 对比表：
  - Scanner
  - SkillScan

### 第 4 页：我们的答案

**标题**  
不是再做一个 scanner，而是补一层治理控制面

**副标题**  
SkillScan = Scanner 输入层 + Governance 控制层

**主文案**

- Scanner 负责本地或 CI 取证
- Governance server 负责准入、审批、隔离、审计
- 只有 Allowed 或 Approved 的版本，才能进入共享和发布路径

**演讲要点**

- 我们不是替代 scanner，而是把 scanner 接进治理流程
- 这让检测结果变成可执行控制
- 产品价值主要体现在 server 这一层

**建议图示**

- 两层结构图：
  - Layer 1: Scanner
  - Layer 2: Governance

### 第 5 页：产品怎么工作

**标题**  
一条清楚的治理链路

**副标题**  
扫描、判定、审批、发布门禁、审计，收成一条流程

**主文案**

1. 本地或 CI 扫描扩展内容
2. 生成标准报告和证据
3. 服务端计算最终 verdict
4. 高风险内容进入审批
5. 只有 Allowed 或 Approved 的版本进入安装或发布路径

**演讲要点**

- 产品价值来自闭环，而不是单点能力
- 这套链路天然适合企业场景
- 它也是后续扩展对象类型的基础

**建议图示**

- 5 步流程图

### 第 6 页：为什么先从 skills 开始

**标题**  
先从 `skills` 切入，但不止于 `skills`

**副标题**  
切口先窄，平台空间更大

**主文案**

- `skills` 是最清楚、最容易跑通闭环的入口
- 但底层治理问题在 `MCP`、`workflow packs`、其他 installable artifacts 上是同一类
- 所以产品切口先窄，平台空间可以更大

**演讲要点**

- 先有一个场景做深，产品才站得住
- 但定位不能把自己锁死成单一对象工具
- 这是“窄切口，大定位”

**建议图示**

- 漏斗图：
  - 入口 `skills`
  - 扩展到 `MCP`
  - 扩展到其他 artifacts

### 第 7 页：客户价值

**标题**  
企业买单的不是检测，而是控制权

**副标题**  
SkillScan 解决的是准入和放行，而不只是提示

**主文案**

- 准入门禁：不合规扩展进不了仓
- 审批闭环：高风险内容必须人工批准
- 版本复审：审批绑定 `repo@commit`
- 隔离策略：高风险内容不进入通用目录
- 审计追溯：每个上传、批准、放行都能回查

**演讲要点**

- 这里是企业付费意愿最高的部分
- 这些能力更接近制度和流程
- 不容易被一个单纯 scanner 替代

**建议图示**

- 5 张能力卡片

### 第 8 页：为什么现在值得做

**标题**  
扩展生态会越来越多，治理需求只会更早出现

**副标题**  
扩展越多，越需要一层统一治理

**主文案**

- AI agent 正在从模型调用走向“可安装扩展”
- 企业一旦允许这类扩展进入内部流程，就一定会碰到治理问题
- 越早补治理层，越能成为基础设施而不是附属工具

**演讲要点**

- 趋势不是“会不会扩展化”，而是“扩展化来得多快”
- 谁先占住治理层，谁就更有机会变成基础设施

**建议图示**

- 时间线或市场趋势箭头图

### 第 9 页：扩展路径

**标题**  
从单一对象切口，走向更大的治理层

**副标题**  
治理动作不变，对象类型可扩

**主文案**

- 今天先支持 `skills`
- 后续扩到 `MCP`
- 再扩到 `workflow packs` 和其他 agent extension artifacts
- 治理动作不变：准入、审批、复审、隔离、审计

**演讲要点**

- 平台空间来自“治理动作稳定”
- 新对象进来，不用重写产品核心逻辑

**建议图示**

- 中心圆：Governance
- 外层圆：skills / MCP / workflow packs / more

### 第 10 页：收尾

**标题**  
让 AI agent 扩展先过治理，再进生产

**副标题**  
从 `skills` 开始，走向更广的 agent extension 治理层

**主文案**

SkillScan 先从 `skills` 做透，再扩展到更多 agent extension 形态，成为企业侧的准入治理控制层。

**演讲要点**

- 先解决一个真实痛点
- 再扩大对象范围
- 最终成为企业扩展治理基础设施

**建议图示**

- 收束页，保留一句 slogan 和 CTA

---

## English Version

### Slide 1: Cover

**Title**  
SkillScan: the governance control layer for AI agent extensions

**Subtitle**  
Govern agent extensions before they ship

**Main copy**  
We help enterprises enforce admission, approval, re-review, and audit controls before extensions enter repositories, install paths, and production environments.

**Speaker notes**

- We are not building just another scanner
- We are building the control layer before extensions enter enterprise systems
- We start with `skills`, but the underlying problem is broader

**Suggested visual**

- A simple line:
  `Scan -> Verdict -> Approve -> Ship`

### Slide 2: The problem

**Title**  
AI agent extensions are growing, but governance is missing

**Subtitle**  
The issue is no longer generation. It is admission.

**Main copy**

- Once extensions grow in number, the problem is no longer just “is this risky”
- Enterprises care about who can install, what can enter repos, what needs approval, and whether updates must be re-reviewed
- Many teams have scanning, but not a complete governance workflow

**Speaker notes**

- As extension volume grows, admission becomes the real bottleneck
- This is a governance problem, not just a detection problem
- Once extensions enter shared repos or production, control matters more than visibility

**Suggested visual**

- Growth on one side, governance gap on the other, connected by risk

### Slide 3: Why current tooling is not enough

**Title**  
Scanning alone is not governance

**Subtitle**  
Finding risk does not stop it from reaching production

**Main copy**

- Finding risk does not stop it from reaching production
- Warnings do not create an approval workflow
- Local scanning does not create organization-wide auditability or re-review
- Enterprises pay for control, not just visibility

**Speaker notes**

- Scanners are necessary, but not sufficient
- Enterprises need processes and control
- That is the boundary of SkillScan

**Suggested visual**

- Comparison table:
  - Scanner
  - SkillScan

### Slide 4: Our answer

**Title**  
Not another scanner. A governance control plane.

**Subtitle**  
SkillScan = scanner input layer + governance control layer

**Main copy**

- The scanner collects evidence locally or in CI
- The governance server handles admission, approval, isolation, and audit
- Only Allowed or Approved versions can move into shared distribution and release paths

**Speaker notes**

- We do not replace scanners; we connect them to governance
- This turns findings into enforceable control
- Most of the enterprise value lives in the server layer

**Suggested visual**

- Two-layer architecture

### Slide 5: How the product works

**Title**  
A clear governance workflow

**Subtitle**  
Scanning, verdict, approval, release gating, and audit in one loop

**Main copy**

1. Scan extension content locally or in CI
2. Generate a standard report with evidence
3. Let the server compute the final verdict
4. Route risky versions into approval
5. Allow only Allowed or Approved versions into install and release paths

**Speaker notes**

- The value comes from the closed loop
- This is what makes the product enterprise-ready
- It also becomes the foundation for future object expansion

**Suggested visual**

- 5-step workflow diagram

### Slide 6: Why start with skills

**Title**  
Start with `skills`, but not limited to `skills`

**Subtitle**  
Narrow wedge, broader platform

**Main copy**

- `skills` are the clearest entry point to operationalize governance fast
- The underlying governance problem is the same for `MCP`, `workflow packs`, and other installable artifacts
- The wedge is narrow, but the platform scope is broader

**Speaker notes**

- We need one category to solve deeply first
- But the positioning cannot lock us into a single object type
- This is a narrow wedge with wider platform potential

**Suggested visual**

- Funnel or expansion wedge

### Slide 7: Customer value

**Title**  
Enterprises pay for control, not just detection

**Subtitle**  
SkillScan governs what gets in, what gets approved, and what gets shipped

**Main copy**

- Admission control: non-compliant extensions do not enter repos
- Approval workflow: risky content requires human approval
- Version-aware review: approval is tied to `repo@commit`
- Isolation policy: high-risk content stays out of general distribution
- Audit trail: every upload, approval, and release decision is traceable

**Speaker notes**

- This is where enterprise willingness to pay sits
- These are process and control problems
- They are harder to replace with a single scanning utility

**Suggested visual**

- Five feature cards

### Slide 8: Why now

**Title**  
As extension ecosystems grow, governance becomes inevitable

**Subtitle**  
The more installable artifacts exist, the more a control layer matters

**Main copy**

- AI agents are moving from simple model calls to installable extensions
- The moment enterprises allow those extensions into internal workflows, governance becomes necessary
- The earlier a governance layer exists, the more likely it becomes infrastructure instead of a plugin

**Speaker notes**

- The trend is not whether extensions will emerge, but how quickly
- Whoever owns governance early has a better chance of becoming infrastructure

**Suggested visual**

- Market timing or trend arrow

### Slide 9: Expansion path

**Title**  
From a single wedge to a broader control layer

**Subtitle**  
Governance actions stay stable even as object types expand

**Main copy**

- Start with `skills`
- Expand into `MCP`
- Expand into `workflow packs` and other agent extension artifacts
- Keep the same core actions: admission, approval, re-review, isolation, and audit

**Speaker notes**

- The broader platform comes from stable governance primitives
- New object types do not require a new product core

**Suggested visual**

- Core circle with outer object categories

### Slide 10: Closing

**Title**  
Govern agent extensions before they ship

**Subtitle**  
Start with `skills`, expand into the broader agent extension governance layer

**Main copy**  
SkillScan starts by solving `skills` well, then expands into broader agent extension categories as the governance layer enterprises already need.

**Speaker notes**

- Solve one urgent pain first
- Expand object coverage over time
- Become enterprise infrastructure for extension governance

**Suggested visual**

- Closing slogan with CTA
