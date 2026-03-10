# SkillScan 规范置顶（对外口径）

## 安全模型（接受一份上报的必要条件，缺一不可）

1. **cosign keyless 验签通过**，且 **issuer == `https://token.actions.githubusercontent.com`**
2. 证书 **identity 解析出的 org/repo** 存在于 **repos 表且 enabled=true**（repo enrollment）
3. identity 中 **workflow path 必须固定**：`.github/workflows/skillscan.yml`
4. **sha256(report.json)** 必须等于 **attestation subject.digest.sha256**

公网有人狂 POST 时，最多损失验签 CPU；**全局限流 + cosign 并发上限**兜住。详见 [../docs/github-app-binding.md](../docs/github-app-binding.md)。

---

## MVP：只开放默认 workflow（减少客服压力）

- **服务端只接受一个 identity**：固定 workflow path **`.github/workflows/skillscan.yml`**，固定 issuer **`https://token.actions.githubusercontent.com`**。
- **identity 正则**（按 token 绑定的 org/repo 动态生成，不写死 org/repo，一个服务端能服务多个 repo）：  
  `^https://github\.com/<org>/<repo>/\.github/workflows/skillscan\.yml@`
- **归属**：从 attestation identity 解析出的 **org/repo** 必须在 `repos` 表中且 `enabled=true`；本地开发可用 `repo_full_name` 兜底。
- **没命中默认 workflow** → 直接 **401 identity_not_allowed**；文档写清楚，减少“为什么我改了文件名就不行”的工单。

**产品上**：MVP 先不提供 POST /allowed-workflows、不做 allowlist UI；**工程上**保留表结构（或配置结构），onboarding 时自动插入默认行 `(org, repo, ".github/workflows/skillscan.yml", enabled=true)`，等开放“多 workflow 显式登记”时 /reports 主流程几乎不动，只把“默认 identity regex”改成“查 allowed_workflows 生成 regex / 精确匹配”。

---

## 两个必须写死的约束（否则信任链会变形）

1. **Workflow 文件路径**：MVP 阶段必须固定为 **`.github/workflows/skillscan.yml`**。  
2. **服务端验签**：验签时必须校验 issuer + **identity 匹配**（MVP 即上述正则）；只验签不校验 identity = 白干。

---

## PR / fork（MVP 先保守）

- **只支持**：`push`、`workflow_dispatch`。  
- **不建议**在 fork 发起的 PR 上跑本 workflow（避免外部贡献者滥用、也避免 OIDC/权限差异造成困惑）。第一版可在文档中写明“仅建议在默认分支或本仓库 push 使用”。

---

## POST /reports multipart 字段名（定死，不再改）

- **`report`** — report.json 文件。  
- **`attestation_bundle`** — attestation.bundle 文件。  

接口一旦在用户 CI 落地，不得再改；否则会收到大量“怎么突然坏了”的工单。OpenAPI 见 [../api/openapi.yaml](../api/openapi.yaml)。

---

详细：数据表、API、验签顺序、默认 workflow 策略见 [../docs/attestation-and-trust.md](../docs/attestation-and-trust.md) 与 [../docs/saas-api.md](../docs/saas-api.md)。  
可用的 workflow 模板见 [../.github/workflows/skillscan.yml](../.github/workflows/skillscan.yml)。
