# ADR-003：冲突策略 A（拒绝，不转移）

**状态**：已接受  
**日期**：2026-02

## 背景

当「当前用户」试图绑定一个已被其他 Console 用户绑定的 GitHub account（org/user），或当 installation 已绑到其他 tenant 时，需要策略。

## 决定

- **策略 A**：**拒绝**，不提供自动转移或覆盖。
- **tenant 已被其他用户绑定**：返回 **403 tenant_owned_by_another_user**；前端展示 "This GitHub account is already linked"，主按钮 Contact support。
- **installation 已绑其他 tenant**：返回 **409 installation_already_linked**；禁止覆盖绑定。

## 理由

- 防止归属混乱与恶意抢绑；安全优先。
- MVP 不提供用户自助「转移 owner」；仅支持侧可做「管理员强制解绑」后让用户重新从 Console 发起安装。

## 后果

- 支持流程：用户提交 GitHub account、installation id、证明为 owner/admin；后台人工确认后执行解绑，再让用户重装。
- 详见 RUNBOOK.md 支持流程与审计要求。
