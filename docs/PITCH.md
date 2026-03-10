# SkillScan Pitch

这份文档用于统一对外说法。可直接拿去写官网、产品介绍、客户邮件、路演 deck。

延伸文案：

- 官网完整落地页：[`WEBSITE_COPY.md`](WEBSITE_COPY.md)
- 官网首页信息架构：[`HOMEPAGE_IA.md`](HOMEPAGE_IA.md)
- 融资 / 路演 deck：[`DECK.md`](DECK.md)
- 融资 PPT 正式排版稿：[`DECK_FINAL.md`](DECK_FINAL.md)

原则只有一条：

- **定位要大**：站在 agent 扩展治理层上
- **切口要窄**：当前先把 `skills` 做透

---

## 中文版

### 一句话

**SkillScan 是 AI agent 扩展内容的准入治理与审批控制层。**

### 副标题

**我们不阻止团队使用 agent 扩展；我们阻止未经批准的扩展进入组织仓库、安装目录和生产环境。**

### 30 秒介绍

SkillScan 不是单纯的扫描器。

它是给 `skills`、后续 `MCP`、`workflow packs` 这类 agent 扩展内容做准入治理的控制层。

它解决的不是“有没有风险”这一个问题。

它解决的是：

- 什么能进仓
- 什么能安装
- 什么必须审批
- 升级后要不要重新批
- 高风险内容能不能被隔离
- 事后能不能审计复盘

### 官网首屏文案

**Headline**  
给 AI agent 扩展内容加上准入治理。

**Subheadline**  
扫描只是开始。真正重要的是准入、审批、复审、隔离和审计。SkillScan 先从 `skills` 切入，后续扩展到 `MCP` 和更多 agent extensions。

### 客户版

企业真正担心的，不只是“扩展里有没有危险命令”。

他们更关心：

- 谁能引入扩展
- 哪些扩展能进入组织仓库
- 哪些高风险扩展必须人工审批
- 新版本上线时旧审批是否失效
- 红队类内容是否必须隔离
- 审计时能不能还原是谁在什么时候批准了什么

SkillScan 把这些问题收成一套控制层。

### 价值点

- **准入门禁**：不合规扩展进不了仓、过不了发布
- **审批闭环**：`needs_approval` 不是提示，而是可执行流程
- **版本复审**：绑定 `repo@commit`，版本一变就重新审
- **隔离策略**：高风险内容可限制在受控环境
- **审计可追溯**：谁上传、谁批准、为什么放行，都能查

### 投资人 / 合作方版

SkillScan 的核心不是“检测一个 skill”。

核心是成为 **AI agent 扩展生态的治理控制层**。

今天先切 `skills`，因为场景最清楚、最容易跑通。  
但底层要解决的是所有可安装 agent 扩展都会遇到的同一类问题：

- 准入
- 审批
- 复审
- 隔离
- 审计

这让 SkillScan 天然具备从单一对象扩展到多种扩展形态的空间。

### Open Core 讲法

最适合 SkillScan 的商业边界是：

- **开源 scanner**：CLI、基础规则、schema、报告输出、CI 集成
- **收费 governance**：审批流、组织策略、审计、权限、企业连接器、高级规则包

这套分法的好处很直接：

- 开源层负责 adoption、信任和生态入口
- 商业层负责组织治理、持续运营和企业付费

对外一句话可以这样讲：

**开源的是 scanner，收费的是 governance。**

### 短宣传语

- 让 AI agent 扩展先过治理，再进生产。
- 不只是扫描扩展，而是管住扩展。
- 给 agent extensions 加一道准入控制层。
- 先发现风险，再决定能不能进仓、能不能安装。

---

## English Version

### One-liner

**SkillScan is the governance and approval control layer for AI agent extensions.**

### Subheadline

**We do not stop teams from using agent extensions. We stop unapproved extensions from entering org repositories, install paths, and production environments.**

### 30-second pitch

SkillScan is not just a scanner.

It is a governance control layer for agent extensions such as `skills` today, and later `MCP servers`, `workflow packs`, and other installable artifacts.

It does more than answer “is this risky?”

It answers:

- What can enter the repo
- What can be installed
- What requires approval
- Whether upgrades must be re-approved
- Whether high-risk content must stay isolated
- Whether security and compliance teams can audit everything later

### Website hero copy

**Headline**  
Govern AI agent extensions before they reach production.

**Subheadline**  
Scanning is only the first step. The real problem is admission, approval, re-review, isolation, and audit. SkillScan starts with `skills` and expands to `MCP` and other agent extensions.

### Customer version

Enterprises are not only worried about risky commands inside an extension.

They care about governance:

- Who can introduce an extension
- What can enter the organization repository
- What must be manually approved
- Whether prior approval expires after an update
- Whether high-risk extensions must stay isolated
- Whether every approval can be reconstructed during audit

SkillScan turns those concerns into one control layer.

### Value points

- **Admission control**: non-compliant extensions do not enter repos or release flows
- **Approval workflow**: `needs_approval` becomes an enforceable process
- **Version-aware review**: approval is tied to `repo@commit`
- **Isolation policy**: high-risk content can be restricted to controlled environments
- **Audit trail**: every upload, approval, and release decision is traceable

### Investor / partner version

SkillScan is not just about scanning a single type of extension.

Its real value is becoming the **governance control layer for the AI agent extension ecosystem**.

We start with `skills` because the workflow is concrete and easy to operationalize.  
But the underlying problem is the same across installable agent artifacts:

- admission
- approval
- re-review
- isolation
- audit

That gives SkillScan room to expand from one object type into a broader platform layer.

### Open Core framing

The cleanest commercial split is:

- **Open scanner**: CLI, baseline rules, schema, report outputs, CI integrations
- **Paid governance**: approval workflows, org policy, audit, identity, enterprise connectors, premium rule packs

Why this works:

- The open layer drives adoption, trust, and ecosystem entry
- The paid layer captures enterprise governance and operating value

One sentence:

**Open the scanner. Sell the governance layer.**

### Short taglines

- Govern agent extensions before they ship.
- Not just extension scanning. Extension control.
- The admission control layer for agent extensions.
- Find the risk, then decide what gets installed.

---

## 使用建议

如果你对外讲这个项目，建议遵循这条顺序：

1. 先讲治理问题，不要先讲扫描器
2. 再讲当前切口是 `skills`
3. 最后再讲未来会扩到 `MCP` 和其他 agent 扩展

不要反过来。  
一上来先讲“我们支持很多对象”，会显得散。  
一上来只讲“我们扫 skill”，又会把自己讲小。
