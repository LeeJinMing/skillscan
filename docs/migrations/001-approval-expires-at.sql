-- 审批过期与撤销
ALTER TABLE approvals ADD COLUMN IF NOT EXISTS expires_at timestamptz NULL;
ALTER TABLE approvals ADD COLUMN IF NOT EXISTS revoked_at timestamptz NULL;
COMMENT ON COLUMN approvals.expires_at IS '审批过期时间；null=永不过期';
COMMENT ON COLUMN approvals.revoked_at IS '撤销时间；非null表示已撤销';
