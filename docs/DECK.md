# SkillScan Deck Copy

这份文档是融资 deck / 路演 / 对外介绍版话术。  
目标是压成能讲清楚的 10 页结构，不是写成长文。

---

## 中文版

## 10 页结构

### 第 1 页：封面

**标题**  
SkillScan：AI agent 扩展内容的准入治理控制层

**副标题**  
让 AI agent 扩展先过治理，再进生产

**一句话介绍**  
我们帮助企业在扩展进入仓库、安装路径和生产环境之前，先完成准入、审批、复审和审计控制。

### 第 2 页：问题

**标题**  
AI agent 扩展开始增多，但企业没有治理层

**要点**

- 扩展一旦变多，问题不再只是“有没有风险”
- 企业真正卡在“谁能装、什么能进、哪些要批、升级后要不要重审”
- 今天很多团队只有扫描，没有完整治理闭环

### 第 3 页：为什么旧方案不够

**标题**  
只有 scanner，不等于有治理

**要点**

- 发现风险，不等于能阻止风险进入生产
- 有提示，不等于有审批闭环
- 有本地扫描，不等于有组织级审计和复审
- 企业买单的不是“看见问题”，而是“控制问题怎么进入系统”

### 第 4 页：我们的答案

**标题**  
不是再做一个 scanner，而是补一层治理控制面

**要点**

- Scanner 负责本地或 CI 取证
- Governance server 负责准入、审批、隔离、审计
- 只有 Allowed 或 Approved 的版本，才能进入共享和发布路径

### 第 5 页：产品怎么工作

**标题**  
一条清楚的治理链路

**要点**

1. 本地或 CI 扫描扩展内容
2. 生成标准报告和证据
3. 服务端计算最终 verdict
4. 高风险内容进入审批
5. 只有 Allowed 或 Approved 的版本进入安装或发布路径

### 第 6 页：为什么先从 skills 开始

**标题**  
先从 `skills` 切入，但不止于 `skills`

**要点**

- `skills` 是最清楚、最容易跑通闭环的入口
- 但底层治理问题在 `MCP`、`workflow packs`、其他 installable artifacts 上是同一类
- 所以产品切口先窄，平台空间可以更大

### 第 7 页：客户价值

**标题**  
企业买单的不是检测，而是控制权

**要点**

- 准入门禁：不合规扩展进不了仓
- 审批闭环：高风险内容必须人工批准
- 版本复审：审批绑定 `repo@commit`
- 隔离策略：高风险内容不进入通用目录
- 审计追溯：每个上传、批准、放行都能回查

### 第 8 页：为什么现在值得做

**标题**  
扩展生态会越来越多，治理需求只会更早出现

**要点**

- AI agent 正在从模型调用走向“可安装扩展”
- 企业一旦允许这类扩展进入内部流程，就一定会碰到治理问题
- 越早补治理层，越能成为基础设施而不是附属工具

### 第 9 页：扩展路径

**标题**  
从单一对象切口，走向更大的治理层

**要点**

- 今天先支持 `skills`
- 后续扩到 `MCP`
- 再扩到 `workflow packs` 和其他 agent extension artifacts
- 治理动作不变：准入、审批、复审、隔离、审计

### 第 10 页：收尾

**标题**  
让 AI agent 扩展先过治理，再进生产

**结束语**  
SkillScan 先从 `skills` 做透，再扩展到更多 agent extension 形态，成为企业侧的准入治理控制层。

## 一页版讲法

如果你只有 1 分钟，可以直接讲这 6 句：

1. AI agent 扩展越来越多，但企业缺的不是 scanner，而是治理层。
2. 企业真正关心的是谁能进仓、谁能安装、哪些要审批、升级后要不要重审。
3. SkillScan 不是单纯检测工具，而是准入治理与审批控制层。
4. 它把扫描、verdict、审批、发布门禁和审计收成一条流程。
5. 我们先从 `skills` 切入，因为最容易跑通闭环。
6. 但长期会扩到 `MCP`、`workflow packs` 和更多 installable artifacts。

---

## English Version

## 10-slide structure

### Slide 1: Cover

**Title**  
SkillScan: the governance control layer for AI agent extensions

**Subtitle**  
Govern agent extensions before they ship

**One-liner**  
We help enterprises enforce admission, approval, re-review, and audit controls before extensions enter repositories, install paths, and production environments.

### Slide 2: The problem

**Title**  
AI agent extensions are growing, but governance is missing

**Points**

- Once extensions grow in number, the problem is no longer just “is this risky”
- Enterprises care about who can install, what can enter repos, what needs approval, and whether updates must be re-reviewed
- Many teams have scanning, but not a complete governance workflow

### Slide 3: Why existing tooling is not enough

**Title**  
Scanning alone is not governance

**Points**

- Finding risk does not stop it from reaching production
- Warnings do not create an approval workflow
- Local scanning does not create organization-wide auditability
- Enterprises pay for control, not just visibility

### Slide 4: Our answer

**Title**  
Not another scanner. A governance control plane.

**Points**

- The scanner collects evidence locally or in CI
- The governance server handles admission, approval, isolation, and audit
- Only Allowed or Approved versions can move into shared distribution and release paths

### Slide 5: How it works

**Title**  
A clear governance workflow

**Points**

1. Scan extension content locally or in CI
2. Generate a standard report with evidence
3. Let the server compute the final verdict
4. Route risky versions into approval
5. Allow only Allowed or Approved versions into install and release paths

### Slide 6: Why start with skills

**Title**  
Start with `skills`, but not limited to `skills`

**Points**

- `skills` are the clearest entry point to operationalize governance fast
- The underlying governance problem is the same for `MCP`, `workflow packs`, and other installable artifacts
- The wedge is narrow, but the platform scope is broader

### Slide 7: Customer value

**Title**  
Enterprises pay for control, not just detection

**Points**

- Admission control: non-compliant extensions do not enter repos
- Approval workflow: risky content requires human approval
- Version-aware review: approval is tied to `repo@commit`
- Isolation policy: high-risk content stays out of general distribution
- Audit trail: every upload, approval, and release decision is traceable

### Slide 8: Why now

**Title**  
As extension ecosystems grow, governance becomes inevitable

**Points**

- AI agents are moving from simple model calls to installable extensions
- The moment enterprises allow those extensions into internal workflows, governance becomes necessary
- The earlier a governance layer exists, the more likely it becomes infrastructure instead of a plugin

### Slide 9: Expansion path

**Title**  
From one wedge to a broader control layer

**Points**

- Start with `skills`
- Expand into `MCP`
- Expand into `workflow packs` and other agent extension artifacts
- Keep the same core governance actions: admission, approval, re-review, isolation, and audit

### Slide 10: Closing

**Title**  
Govern agent extensions before they ship

**Closing**  
SkillScan starts by solving `skills` well, then expands into broader agent extension categories as the governance layer enterprises already need.

## One-minute version

If you only have one minute, say this:

1. AI agent extensions are growing, but enterprises are missing a governance layer.
2. The real problem is not just risk detection, but who can install, what can enter repos, and what must be re-approved after updates.
3. SkillScan is not just a scanner; it is the governance and approval control layer.
4. It connects scanning, verdicts, approval, release gating, and audit into one workflow.
5. We start with `skills` because that is the fastest way to operationalize the loop.
6. Over time, the same layer expands into `MCP`, `workflow packs`, and other installable artifacts.

---

## 使用建议

### 路演时怎么讲

建议按这个顺序：

1. 先讲企业治理问题
2. 再讲为什么旧方案不够
3. 再讲 SkillScan 的治理闭环
4. 再讲为什么先从 `skills` 切入
5. 最后讲平台扩展空间

### 不要这样讲

- 一上来先讲“我们支持很多对象”
- 一上来先讲规则引擎、schema、attestation
- 一上来先把自己讲成“某个生态的附属小工具”

### 要这样讲

- 先讲控制权
- 再讲流程闭环
- 最后讲产品形态和技术实现
