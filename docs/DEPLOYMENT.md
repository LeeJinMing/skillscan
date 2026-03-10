# SkillScan 生产部署手册

本文档描述如何将 SkillScan 部署到生产环境，包括 TLS、反向代理、备份、恢复和回滚。

## 前置条件

- Postgres 12+
- Node.js 20+
- 反向代理（Nginx / Caddy / Traefik）
- 生产环境必须设置：`NODE_ENV=production` 或 `SKILLSCAN_MODE=production`

## 生产模式强制要求

当 `NODE_ENV=production` 或 `SKILLSCAN_MODE=production` 时，服务启动前会校验：

- `SESSION_SECRET`：必填，至少 32 字符，禁止 dev/placeholder
- `STATE_SECRET`：必填，至少 32 字符，禁止 dev/placeholder
- `GITHUB_WEBHOOK_SECRET`（若配置）：至少 32 字符

本地开发可设 `SKILLSCAN_MODE=demo` 使用默认值。

## 部署步骤

### 1. 数据库

```bash
psql $DATABASE_URL -f docs/postgres-schema.sql
```

### 2. 环境变量

参考 `server/.env.example`，至少配置：

- `DATABASE_URL`
- `SESSION_SECRET`
- `STATE_SECRET`
- `PUBLIC_BASE_URL`（对外访问地址）
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` / `GITHUB_OAUTH_CALLBACK_URL`（OAuth 登录）
- `GITHUB_WEBHOOK_SECRET`（收 webhook 时必填）
- `GITHUB_APP_ID` / `GITHUB_PRIVATE_KEY`（GitHub App 安装绑定）

### 3. 反向代理与 TLS

建议在反向代理层终止 TLS，不暴露 Node 直连。

**Nginx 示例**：

```nginx
server {
    listen 443 ssl http2;
    server_name api.skillscan.example.com;
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**信任代理**：若需 `req.ip` 正确，在 Fastify 中配置 `trustProxy: true`。

### 4. 启动服务

```bash
cd server
npm ci --omit=dev
npm run build
npm start
```

或使用 Docker：

```bash
docker build -f server/Dockerfile .
```

## 备份与恢复

### 备份

- **Postgres**：`pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql`
- **建议频率**：每日全量 + 关键操作前快照

### 恢复

```bash
psql $DATABASE_URL < backup_YYYYMMDD.sql
```

恢复后重启服务。

## 回滚

### 应用回滚

1. 切回上一版本镜像或代码
2. 重启服务
3. 检查 `/healthz`、`/readyz`

### 数据库回滚

- 若 schema 未变：仅恢复数据即可
- 若 schema 已升级：需执行对应 down 迁移或从备份恢复

## 扩容

- **水平扩容**：多实例 + 共享 Postgres，`RATE_LIMIT_BACKEND=database`
- **垂直扩容**：增加 Node 内存、Postgres 连接池

## 健康检查

- `GET /healthz`：服务存活
- `GET /readyz`：依赖就绪（DB 连通性）；DB 不可达时返回 503
- `GET /metrics`：Prometheus 格式指标

详见 [`docs/RUNBOOK.md`](RUNBOOK.md)。
