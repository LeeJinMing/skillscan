# SkillScan Open Core Roadmap

这份文档只回答一个问题：

**如果 SkillScan 正式走 Open Core，应该先做哪些可验证动作。**

## 目标边界

最终建议分成三层：

### 1. Community Edition

公开、可验证、便于集成。

包含：

- `skillscan/` CLI
- 基础规则引擎
- 基础规则集
- policy / report schema
- JSON / SARIF / Markdown 输出
- GitHub Action / 基础 CI 集成
- fixtures / golden tests / 文档

### 2. Enterprise Edition

组织级治理能力。

包含：

- 扫描结果收集
- 最终 verdict 服务
- 审批流
- 例外管理
- 版本复审
- 审计留痕
- 组织策略中心
- RBAC / SSO / SCIM
- 企业连接器
- 高级规则包

### 3. Hosted / Managed

托管交付和持续运营。

包含：

- 托管控制面
- 托管规则更新
- 信誉 / 情报 feed
- 托管审计和备份
- License / billing / support

## 阶段 1：先把开源入口做强

这阶段的目标不是赚钱，是建立入口和信任。

### 需要确认保留在开源层的东西

- CLI 可独立运行
- 本地扫描不依赖服务端
- 输出格式稳定
- 规则命中可解释
- fixtures 能锁定行为

### 可验证标准

- `skillscan scan ...` 不依赖 `server/`
- 默认输出至少包含 `report.json`
- 命中结果包含规则、文件、证据
- tests 能覆盖基础规则和 verdict 映射

## 阶段 2：把商业层定义清楚

这阶段的目标是让“为什么付费”一眼说清。

### 商业层清单要单独写明

- 审批工作台
- 组织策略
- 例外和到期复审
- 审计导出
- 身份权限
- 企业连接器
- 高级规则包
- 信誉与情报

### 可验证标准

- README 有清楚的开源 / 商业能力表
- Pitch 里能一句话讲清：开源 scanner，收费 governance
- 企业功能不再混在“社区默认能力”里讲

## 阶段 3：正式做产品包装

这阶段才进入真正的版本分层。

### 建议动作

1. Community 文档只讲本地扫描、规则、报告、CI
2. Enterprise 文档单独讲审批、审计、策略、权限
3. Hosted 单独讲托管、SLA、情报和支持
4. 高级规则包从基础规则里拆出来

### 可验证标准

- 官网或 README 出现明确版本分层
- 演示路径分成 CLI demo 和 governance demo
- 高级规则、企业连接器、身份系统单独成页

## 现在仓库该怎么讲

当前更准确的说法是：

- 这个仓库已经包含 scanner 和治理控制面的原型代码
- 但推荐的正式商业边界，是“开源 scanner，商业化治理层”

这样讲有两个好处：

- 不会把未来边界说成当前事实
- 也不会错过现在就统一口径的机会

## 对外统一话术

可以固定成下面这句：

**SkillScan 开源可验证的扫描层，用它进入生态；把组织级审批、策略、审计和运营层做成商业产品。**

更短一句：

**让开发者免费用扫描器，让企业为治理层付费。**
