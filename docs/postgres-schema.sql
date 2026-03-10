-- Skill Governance — Postgres 最小表结构（够用、能审计、可扩展）
-- 审批粒度：MVP = repo@commit；未来 = skill_path@commit（同一 repo 多 skill 时更细）
-- 账号与租户：OAuth 只做登录；tenant 从 installation 的 account 派生（见 docs/github-app-binding.md）

-- 0a) 用户（OAuth 回调 upsert）
create table if not exists users (
  id uuid primary key,
  github_user_id bigint not null unique,
  login text not null,
  email text null,
  created_at timestamptz not null default now()
);

-- 0a2) 租户（单人 workspace：谁绑定谁用；owner_user_id 唯一拥有者，无 tenant_members）
create table if not exists tenants (
  id uuid primary key,
  github_account_id bigint not null unique,
  github_account_login text not null,
  github_account_type text not null check (github_account_type in ('Organization','User')),
  owner_user_id uuid not null references users(id),
  created_at timestamptz not null default now()
);

create index idx_tenants_github_account_id on tenants(github_account_id);
create index idx_tenants_owner on tenants(owner_user_id);

-- 0a3) 租户成员与角色（RBAC 基础；owner 自动为 admin）
create table if not exists tenant_members (
  id uuid primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  user_id uuid not null references users(id) on delete cascade,
  role text not null check (role in ('admin', 'approver', 'viewer')),
  created_at timestamptz not null default now(),
  unique (tenant_id, user_id)
);
create index idx_tenant_members_tenant on tenant_members(tenant_id);
create index idx_tenant_members_user on tenant_members(user_id);

-- 0) 允许上报的 workflow（B 绑定：只接受登记过的 identity）
-- workflow_path 必须形如 .github/workflows/*.yml；默认只登记 .github/workflows/skillscan.yml
create table allowed_workflows (
  id uuid primary key,
  org text not null,
  repo text not null,
  workflow_path text not null,
  enabled boolean not null default true,
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint uniq_allowed_workflows_org_repo_path unique (org, repo, workflow_path),
  constraint chk_workflow_path check (workflow_path like '.github/workflows/%.yml')
);

create index idx_allowed_workflows_lookup on allowed_workflows(org, repo, workflow_path) where enabled = true;

-- 0b) GitHub App 绑定用（见 docs/github-app-binding.md）
-- 行由 /github/install/complete 创建并写入 tenant_id；webhook 只更新已有行或同步 repos
create table if not exists github_installations (
  installation_id bigint primary key,
  tenant_id uuid not null references tenants(id),
  account_id bigint not null,
  account_login text not null,
  account_type text not null check (account_type in ('Organization','User')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index github_installations_tenant_idx on github_installations(tenant_id);

-- 0b2) 安装回调 state 载体（防 CSRF/重放）；一次性，用完即废；不含 tenant_id（tenant 在 complete 时由 installation 的 account 决定）
create table if not exists install_sessions (
  id uuid primary key,
  user_id uuid not null references users(id),
  nonce text not null unique,
  expires_at timestamptz not null,
  used_at timestamptz null,
  created_at timestamptz not null default now()
);

create index idx_install_sessions_nonce on install_sessions(nonce);
create index install_sessions_user_id_idx on install_sessions(user_id);
create index install_sessions_expires_idx on install_sessions(expires_at);

create table if not exists repos (
  repo_id bigint primary key,
  full_name text not null unique,
  installation_id bigint not null references github_installations(installation_id),
  enabled boolean not null default true,
  updated_at timestamptz not null default now()
);

create index idx_repos_full_name on repos(full_name);
create index repos_installation_enabled_idx on repos(installation_id, enabled);

-- 0c) Webhook 幂等（见 docs/github-app-binding.md）
create table if not exists github_webhook_deliveries (
  delivery_id text primary key,
  event text not null,
  received_at timestamptz not null default now()
);

-- 0d) 报告存储：Append-only，每次运行一条；share_token 可分享链接，share_expires_at 必填（如 now()+7 days）
-- 见 docs/github-app-binding.md「报告存储与分享」
create table if not exists reports (
  id uuid primary key,
  tenant_id uuid not null references tenants(id),
  repo_id bigint not null references repos(repo_id),
  created_at timestamptz not null default now(),
  status text not null check (status in ('ok','failed')),
  summary jsonb not null,
  artifact_url text null,
  share_token text not null unique,
  share_expires_at timestamptz not null
);

create index reports_repo_created_idx on reports(repo_id, created_at desc);
create index reports_tenant_created_idx on reports(tenant_id, created_at desc);
create index reports_share_expires_idx on reports(share_expires_at);

-- 0e) 数据库限流窗口（多实例可共享）
create table if not exists rate_limits (
  bucket_key text not null,
  bucket_start timestamptz not null,
  count integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (bucket_key, bucket_start)
);

create index rate_limits_updated_idx on rate_limits(updated_at);

-- 取「最新一条」O(1)：/reports 成功入库后 upsert 此表
create table if not exists repo_latest_reports (
  repo_id bigint primary key references repos(repo_id),
  report_id uuid not null unique references reports(id),
  updated_at timestamptz not null default now()
);

-- 1) 扫描记录
create table scans (
  id uuid primary key,
  org_id uuid not null,
  repo text not null,
  commit_sha text not null,
  release_tag text null,
  created_at timestamptz not null default now(),

  scanner_version text not null,
  ruleset_version text not null,
  policy_version text not null,

  verdict_status text not null,   -- blocked | needs_approval | allowed | approved
  verdict_reason text not null,

  report_json jsonb not null,
  skill_paths jsonb null          -- 可选：本次扫描到的 skill 列表 [{path, id, category, verdict}]，未来细粒度审批用
);

create index idx_scans_org_repo_sha on scans(org_id, repo, commit_sha);
create index idx_scans_org_created on scans(org_id, created_at desc);

-- 2) 审批结果（scope 可扩展：先 repo@commit，后 skill_path@commit）
-- MVP：scope_type='repo_commit', scope_key='repo=org/repo', skill_path=null
-- 未来：scope_type='skill_path_commit', scope_key='repo=org/repo;path=skills/xxx/SKILL.md', skill_path 填值
create table approvals (
  id uuid primary key,
  org_id uuid not null,

  scope_type text not null,       -- 'repo_commit' | 'skill_path_commit'
  scope_key text not null,        -- 规范化 key：repo_commit => repo=org/repo；skill_path_commit => repo=org/repo;path=...
  repo text not null,
  commit_sha text not null,
  skill_path text null,           -- 未来用；repo_commit 时为 null

  status text not null,           -- approved | rejected
  decided_by text not null,
  decided_at timestamptz not null default now(),
  expires_at timestamptz null,    -- 过期时间；null=永不过期
  revoked_at timestamptz null,    -- 撤销时间；非 null 表示已撤销
  comment text null
);

create unique index uniq_approvals_scope on approvals(org_id, scope_type, scope_key, commit_sha);

-- 3) 审计事件
create table audit_log (
  id uuid primary key,
  org_id uuid not null,
  actor text not null,
  action text not null,           -- SCAN_CREATED | APPROVED | REJECTED | POLICY_CHANGED | VIEWED
  target_type text not null,      -- scan | approval | policy
  target_id text not null,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index idx_audit_org_created on audit_log(org_id, created_at desc);
