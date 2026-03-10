# Release Checklist

发布前必做检查。

## CLI (skillscan)

- [ ] `python tests/test_fixtures.py` 全部通过
- [ ] `pip install .` 后 `skillscan --help`、`skillscan demo --fixture allowed` 可用
- [ ] `skillscan scan . --format v1` 产出 `report.json` 且通过 `scripts/validate_report_schema.py`
- [ ] `pyproject.toml` 版本号已更新
- [ ] `skillscan/__init__.py` 版本号与 pyproject 一致
- [ ] `skillscan/rules/`、`skillscan/fixtures/`、`skillscan/schema/` 与仓库根对应文件同步（`python scripts/sync-rules.py pkg-to-root` 或 `root-to-pkg`）

## Server

- [ ] `npm run build` 成功
- [ ] `npm test` 全部通过
- [ ] 生产模式（`NODE_ENV=production`）下缺 SESSION_SECRET/STATE_SECRET 时启动失败
- [ ] `GET /readyz` 在 DB 不可达时返回 503

## CI

- [ ] `.github/workflows/skillscan.yml` 中 test、install-smoke、scan 均通过
- [ ] release 触发时 gate 正确（blocked 阻断、allowed/approved 放行）

## 文档

- [ ] README 安装与快速上手步骤有效
- [ ] `docs/WHEN-TO-PROVIDE-KEYS.md` 与当前行为一致
- [ ] `CHANGELOG` 或 release notes 已更新（若有）

## 发布后

- [ ] 新版本 CLI 可从 PyPI 或 release 资产安装
- [ ] 官方 workflow 路径 `.github/workflows/skillscan.yml` 未变（attestation identity 依赖）
