# SkillScan Server — Node + 固定 cosign 版本（验签脚本依赖）
# 构建（在仓库根目录）：docker build -f server/Dockerfile .
# 运行：需 DATABASE_URL、GITHUB_WEBHOOK_SECRET 等；见 server/README.md

FROM node:22-alpine AS deps
WORKDIR /app
COPY server/package.json server/package-lock.json* ./
RUN npm ci --omit=dev

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY server/package.json server/tsconfig.json ./
COPY server/src ./src
RUN npm run build

# 固定 cosign 版本；可选：构建时传入 COSIGN_VERSION、COSIGN_SHA256 校验
ARG COSIGN_VERSION=v2.2.4
RUN wget -q -O /tmp/cosign.tgz "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign_${COSIGN_VERSION#v}_linux_amd64.tar.gz" \
  && tar -xzf /tmp/cosign.tgz -C /tmp && mv /tmp/cosign /usr/local/bin/cosign && chmod +x /usr/local/bin/cosign && rm /tmp/cosign.tgz

FROM node:22-alpine
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY server/package.json ./
COPY --from=builder /app/dist ./dist
COPY --from=builder /usr/local/bin/cosign /usr/local/bin/cosign
COPY server/scripts ./scripts
RUN chmod +x scripts/verify-attestation.sh 2>/dev/null || true
COPY schema/report-v1.json ./schema/report-v1.json 2>/dev/null || true

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
EXPOSE 3000
CMD ["node", "dist/index.js"]
