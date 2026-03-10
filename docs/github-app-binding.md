# GitHub App 绑定（文档导航）

**本仓库已按「契约 / 实现 / 运维」拆成多份文件，本页仅作导航。以以下文件为准，勿以本页为权威。**

---

## 权威文档（按用途）

| 文档 | 用途 | 读者 |
|------|------|------|
| **[SPEC-github-app-binding.md](SPEC-github-app-binding.md)** | **唯一权威**：产品/后端/前端都按它。8 节固定（Scope、Definitions、User Journey、State machine、Security model、API contract summary、Data ownership、Support policy）。约 10 分钟读完，只写契约不写伪代码。 | 产品、前端、后端 |
| **[api/openapi.yaml](../api/openapi.yaml)** | **接口真相源**：代码生成、测试、前端对接都靠它。含 /github/install/start、complete，/github/webhooks，/reports，/r/{share_token}，以及 /scans、/approvals、/audit。 | 后端、前端、测试 |
| **[docs/ADR/](ADR/)** | **关键决定存档**：以后有人推翻决定，先读 ADR 再讨论。至少 4 个：ADR-001 Public+Selected repos，ADR-002 tenant=installation account 单 owner，ADR-003 冲突策略 A（拒绝不转移），ADR-004 append-only+latest+share 7 天。 | 架构、产品 |
| **[RUNBOOK.md](RUNBOOK.md)** | **运维/排障**：出事时 3 分钟定位。含 webhook 验签失败、delivery 幂等、repo 未 enrolled、403 tenant_owned、410 分享过期、reports 保留策略、审计日志。 | 运维、支持 |
| **[IMPLEMENTATION-notes.md](IMPLEMENTATION-notes.md)** | **可选附录**：伪代码、schema 摘要、竞态、工程清单、测试清单。写给开发者，是「参考实现」不是产品契约。 | 开发者 |

---

## 数据与实现

- **Postgres DDL**：**docs/postgres-schema.sql**（含 users、tenants、install_sessions、github_installations、repos、github_webhook_deliveries、reports、repo_latest_reports）。
- **验签/报告 schema**：见 **docs/attestation-and-trust.md**、**schema/report-v1.json**、**api/openapi.yaml**（multipart 字段名 report、attestation_bundle 定死）。

---

## 为何拆分

原单文件 72 个二三级标题，同一内容多套命名（原则/产品约束/最终规则、端到端/用户主路径/关键流程、数据模型/至少要有的表/Postgres schema、致命缺陷/必须面对/踩坑），规格与实现混在一起，导致「改代码就要改 spec、最后失真」。  
现拆成：**SPEC（契约）** + **OpenAPI（接口真相）** + **ADR（决定）** + **RUNBOOK（排障）** + **IMPLEMENTATION-notes（参考实现）**，各归其位。
