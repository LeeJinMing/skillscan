/**
 * Production mode: fail fast when critical secrets are missing or weak.
 * Demo mode: allow defaults for local dev.
 */
const INSECURE_PATTERNS = [
  "dev_",
  "change_in_production",
  "placeholder",
  "secret",
  "example",
];

const MIN_SECRET_LEN = 32;

function isProduction(): boolean {
  const mode = process.env.SKILLSCAN_MODE ?? process.env.NODE_ENV ?? "";
  return mode.toLowerCase() === "production";
}

function isInsecure(value: string): boolean {
  if (!value || value.length < MIN_SECRET_LEN) return true;
  const lower = value.toLowerCase();
  return INSECURE_PATTERNS.some((p) => lower.includes(p));
}

export function assertProductionSecrets(): void {
  if (!isProduction()) return;

  const errors: string[] = [];

  const sessionSecret = process.env.SESSION_SECRET ?? "";
  if (!sessionSecret || isInsecure(sessionSecret)) {
    errors.push(
      "SESSION_SECRET must be set and at least 32 chars; no dev/placeholder values in production"
    );
  }

  const stateSecret = process.env.STATE_SECRET ?? "";
  if (!stateSecret || isInsecure(stateSecret)) {
    errors.push(
      "STATE_SECRET must be set and at least 32 chars; no dev/placeholder values in production"
    );
  }

  if (process.env.GITHUB_WEBHOOK_SECRET) {
    const whSecret = process.env.GITHUB_WEBHOOK_SECRET;
    if (isInsecure(whSecret)) {
      errors.push(
        "GITHUB_WEBHOOK_SECRET must be at least 32 chars when set; no placeholder in production"
      );
    }
  }

  if (errors.length > 0) {
    throw new Error(
      `Production mode: invalid or missing secrets.\n${errors.join("\n")}\nSet SKILLSCAN_MODE=demo to allow defaults for local dev.`
    );
  }
}
