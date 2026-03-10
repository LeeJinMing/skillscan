# ADR-004：Append-only + latest 指针 + 分享链接 7 天

**状态**：已接受  
**日期**：2026-02

## 背景

报告存储与分享方式：只存 latest 会像玩具；要求登录才能看链接会降低转化。需要定存储模型与分享策略。

## 决定

- **报告存储**：**Append-only**（每次运行一条）；UI 默认只展示 **Latest**。
- **取最新**：用 **repo_latest_reports** 指针表，O(1) 取最新 report_id。
- **分享链接**：默认 **可分享链接**（share_token，256-bit 随机）；**7 天过期**；**不要求登录**即可打开 GET /r/:share_token。

## 理由

- 最好卖：客户要「可分享」「可追溯」；只存 latest 不够。
- 最省事：Append-only 插入简单；指针表取最新无需复杂 SQL。
- 最友好：CI 跑完给链接，点开就看；要求登录会明显降低使用率和转化。
- 7 天：够排查 CI，又不过度暴露；后续可按 tenant 可配置或改为 30 天。

## 后果

- reports 表含 share_token、share_expires_at（not null，入库时 now()+7d）。
- 分享页不暴露 tenant_id、installation_id、内部错误；需限流与 token 格式校验防扫描。
- 同一 commit 重跑会多条报告；保留策略见 RUNBOOK（每 repo 保留 N 条或 30 天）。
