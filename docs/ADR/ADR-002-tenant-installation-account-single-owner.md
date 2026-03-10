# ADR-002：tenant = installation account，Org+User，单 owner（B）

**状态**：已接受  
**日期**：2026-02

## 背景

租户(tenant) 的归属有两种常见模型：  
A) tenant = GitHub 组织/用户账号（按 installation 的 account 归属）  
B) tenant = 自有「公司空间」（一个 tenant 可绑多个 GitHub org）

## 决定

- **选 A**：**tenant = GitHub installation 的 account**（Org 或 User）。
- **安装在 org → tenant = 该 org**；**安装在 user → tenant = 该 user**。
- **单 owner**：一个 workspace(tenant) 只能有一个 Console 用户拥有者（`owner_user_id`）；谁绑定谁用，MVP 不提供转移/共享。

## 理由

- 计费主体清晰、权限模型简单；一个 org 一份账单，一个 user 一份账单。
- 不做「一个公司多个 org 合并结算」可避免 MVP 复杂度爆炸。
- 单 owner 避免协作/邀请/角色体系，留到有付费客户再做。

## 后果

- 数据模型：tenants 表含 `github_account_id`、`owner_user_id`；无 tenant_members。
- 要扫 org 的 repos，必须在该 org 安装 App；不能靠个人安装「代扫」org。
