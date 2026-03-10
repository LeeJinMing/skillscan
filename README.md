# SkillScan

给 AI agent 扩展做准入治理。扫描、审批、审计，一条链打通。

## 安装

```bash
pip install -e .
```

## 快速开始

```bash
skillscan scan . -o ./out --html --markdown
```

输出 `out/report.json`、`out/report.html`、`out/report.md`。Verdict：`allowed` / `needs_approval` / `blocked`。

```bash
skillscan demo --fixture needs-approval -o ./demo-out
```

## 接 CI

用 `.github/workflows/skillscan.yml`。跑完上传 report，服务端返回 verdict，门禁按 verdict 放行或阻断。

## 接服务端

要做团队共享、审批、审计，配 DB + GitHub OAuth + GitHub App。见 [server/README.md](server/README.md) 和 [docs/WHEN-TO-PROVIDE-KEYS.md](docs/WHEN-TO-PROVIDE-KEYS.md)。

## 支持输入

- 本地目录：`skillscan scan ./path/to/skill`
- zip：`skillscan scan ./skill.zip`
- GitHub：`skillscan scan org/repo` 或 `skillscan scan https://github.com/org/repo`

## 文档

| 文档 | 说明 |
|------|------|
| [server/README.md](server/README.md) | 服务端启动与接口 |
| [docs/WHEN-TO-PROVIDE-KEYS.md](docs/WHEN-TO-PROVIDE-KEYS.md) | 何时需要 DB / OAuth / App |
| [api/openapi.yaml](api/openapi.yaml) | 接口契约 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 生产部署 |
| [OPEN_SOURCE_BOUNDARY.md](OPEN_SOURCE_BOUNDARY.md) | 开源边界 |
