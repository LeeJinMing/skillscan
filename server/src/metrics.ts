const startedAt = Date.now();

const counters = {
  requestsTotal: 0,
  reportsUploaded: 0,
  rateLimited: 0,
  auditFailures: 0,
};

export function recordRequest(): void {
  counters.requestsTotal += 1;
}

export function recordReportsUploaded(): void {
  counters.reportsUploaded += 1;
}

export function recordRateLimited(): void {
  counters.rateLimited += 1;
}

export function recordAuditFailure(): void {
  counters.auditFailures += 1;
}

export function metricsSnapshot() {
  return {
    uptime_seconds: Math.floor((Date.now() - startedAt) / 1000),
    requests_total: counters.requestsTotal,
    reports_uploaded_total: counters.reportsUploaded,
    rate_limited_total: counters.rateLimited,
    audit_failures_total: counters.auditFailures,
  };
}

export function metricsText(): string {
  const snapshot = metricsSnapshot();
  return [
    "# TYPE skillscan_uptime_seconds gauge",
    `skillscan_uptime_seconds ${snapshot.uptime_seconds}`,
    "# TYPE skillscan_requests_total counter",
    `skillscan_requests_total ${snapshot.requests_total}`,
    "# TYPE skillscan_reports_uploaded_total counter",
    `skillscan_reports_uploaded_total ${snapshot.reports_uploaded_total}`,
    "# TYPE skillscan_rate_limited_total counter",
    `skillscan_rate_limited_total ${snapshot.rate_limited_total}`,
    "# TYPE skillscan_audit_failures_total counter",
    `skillscan_audit_failures_total ${snapshot.audit_failures_total}`,
    "",
  ].join("\n");
}
