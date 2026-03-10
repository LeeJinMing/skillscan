# Open Source Boundary

这份文档不讲空话，只讲两件事：

1. 当前仓库里已经有哪些能力
2. SkillScan 如果走 Open Core，边界应该怎么切

## 结论

SkillScan 适合走这条线：

- **开源**：单机可验证的扫描能力
- **商业化**：组织级治理与运营能力

一句话：

**Open the scanner. Sell the governance layer.**

## 为什么这个边界更合适

SkillScan 有两层价值：

### 1. 扫描能力

这部分越透明，越容易被采用。

原因很直接：

- 安全团队需要看见规则、证据、输出逻辑
- 开发者更愿意先试一个开源 CLI
- 生态集成更依赖稳定 schema 和标准输出

所以，扫描器应该尽量做到：

- 可本地跑
- 可离线验证
- 可解释
- 可扩展

### 2. 治理能力

企业真正付钱的，通常不是“能扫出来”，而是：

- 谁能提交扩展
- 什么能进入组织仓库
- 哪些必须人工审批
- 谁批准了什么
- 例外什么时候失效
- 新版本是否必须重审
- 审计时如何导出证据

这部分天然更适合做商业层。

## 当前仓库状态

当前仓库已经同时包含两类东西：

### 已适合开源的部分

- `skillscan/` CLI
- 本地目录 / zip / GitHub repo 扫描
- 规则引擎和基础规则
- `report.json`、HTML、Markdown 输出
- schema、attestation、API 契约文档
- fixtures、golden tests
- GitHub Actions / CI 集成入口

### 当前仓库里也存在的治理侧代码

- `server/`
- `/reports`、`/approve`、`/reject`、`/audit`
- 扫描记录、审批、审计、健康检查
- 控制面相关接口和数据模型

这说明：

- **当前仓库更像产品孵化仓**
- **还不是已经完全切好的 Open Core 包装**

所以后续对外要讲清：

- 现在仓库里有什么
- 未来正式产品如何分层

不要把“目标边界”误写成“当前已经完全拆好”。

## 推荐开源边界

下面这些适合做 Community Edition：

### 1. Scanner / CLI

- `skillscan/` CLI
- skill 目录解析
- 命令和脚本片段发现
- verdict 计算
- 本地离线运行

### 2. 规则与 Schema

- 规则格式
- policy schema
- report schema
- verdict 定义
- rule extension 接口

### 3. 基础规则集

建议开基础版，不建议把规则全关掉。

适合公开的例子：

- `curl | bash`
- `wget | sh`
- `sudo`
- `chmod 777`
- systemd / crontab 写入
- shell profile 修改
- 外部二进制下载
- SSH key / sshd 配置改动

### 4. 报告与集成

- JSON 输出
- SARIF 输出
- Markdown summary
- PR comment format
- exit code 规范
- GitHub Action / GitLab CI / pre-commit / Docker 基础分发

### 5. 样本与文档

- fixtures
- 恶意样本片段
- 误报样本
- 回归测试数据
- 开发者文档
- 规则编写指南

## 推荐商业化边界

下面这些更适合 Enterprise / Hosted：

### 1. 组织级治理后端

- 报告接收与归档
- 最终 verdict 服务
- 组织策略绑定
- 审批流
- 例外管理
- 升级重审
- 审计记录

### 2. 管理台

- 风险看板
- 扫描历史
- skill 清单
- 审批工作台
- 审计导出
- 风险趋势

### 3. 身份与权限

- RBAC
- SSO
- SCIM
- LDAP / AD
- 多组织隔离
- 多租户

### 4. 高级规则和持续服务

- 私有高级规则包
- 低误报规则包
- 行业专项规则包
- 信誉库
- 威胁情报 feed
- 规则热更新服务

### 5. 企业连接器

- Jira / ServiceNow
- Slack / Teams / 飞书审批联动
- SIEM / SOC
- CMDB / 资产分类联动

### 6. 商业化基础设施

- HA
- license
- billing
- 托管服务
- 企业支持

## 三层产品结构

推荐直接按三层讲：

### Community Edition

让任何开发者先跑起来。

包含：

- CLI
- 基础规则
- 本地扫描
- JSON / SARIF / Markdown 输出
- GitHub Action
- 简单 policy 文件
- 文档和示例

### Enterprise Edition

卖给团队和组织。

包含：

- server 侧治理能力
- 组织策略
- 审批流
- 例外管理
- 审计报表
- SSO / RBAC
- 私有规则包
- 企业连接器

### Hosted / Managed

卖给不想自建的客户。

包含：

- 托管控制面
- 托管规则更新
- 信誉与情报 feed
- 托管审计
- 优先支持

## 三个不要踩的坑

### 1. 不要把扫描器做成黑盒

至少要让用户看见：

- 命中了哪条规则
- 哪个文件
- 哪一行
- 为什么是 `Needs Approval` 或 `Blocked`

### 2. 不要把全部规则都闭源

否则开源 CLI 会变成空壳。

更合适的做法是：

- 基础规则开源
- 高级规则收费

### 3. 不要过早承诺免费 self-host 全量版

如果商业价值主要在治理层，就别把完整治理后端当社区版默认能力。

## 可验证的下一步

如果正式按这个边界推进，建议先完成这些动作：

1. README 明确写出开源层和商业层的边界
2. 保持 CLI、schema、基础规则、fixtures、CI 集成为公共入口
3. 把企业能力单独定义成 Enterprise / Hosted 清单
4. 对外统一一句话：**开源的是 scanner，收费的是 governance**

详细拆分见：`docs/OPEN_CORE_ROADMAP.md`。
