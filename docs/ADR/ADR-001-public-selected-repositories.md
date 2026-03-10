# ADR-001：Public App + Selected repositories

**状态**：已接受  
**日期**：2026-02

## 背景

GitHub App 安装时可选 "All repositories" 或 "Selected repositories"。需要决定 MVP 支持哪种。

## 决定

- **Public App**：支持公网安装，入口多（搜索、Marketplace、朋友链接）；用户可能绕过 Console 直接安装。
- **只允许 "Selected repositories"**：不提供 "All repositories" 选项。

## 理由

- **Selected**：权限最小、归属清晰；用户显式选 repo，服务端只同步这些 repo 的 enrollment；未选 repo 一律 401 repo_not_enrolled。
- **All**：会立刻复杂（权限边界、账单归属、跨 org）；MVP 不做。

## 后果

- 产品/文档必须引导用户安装时只选 Selected repositories。
- 若未来有企业需求「全 org 扫描」，再单独评估。
