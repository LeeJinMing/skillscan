import type { Pool } from "pg";

/** Error body per api/openapi.yaml components.schemas.Error */
export type ErrorCode =
  | "invalid_request"
  | "not_authenticated"
  | "state_invalid_or_expired"
  | "tenant_owned_by_another_user"
  | "installation_already_linked"
  | "repo_not_enrolled"
  | "quota_exceeded"
  | "rate_limited"
  | "invalid_signature"
  | "identity_not_allowed"
  | "report_digest_mismatch"
  | "schema_invalid"
  | "internal_error"
  | "forbidden"
  | "workflow_not_allowed";

export interface ErrorBody {
  code: ErrorCode;
}

declare module "fastify" {
  interface FastifyInstance {
    db: Pool | null;
  }
}
