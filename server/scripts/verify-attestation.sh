#!/usr/bin/env bash
# 验签 attestation.bundle 对 report 的签名；仅调用 cosign，参数定死，stdout 输出固定 JSON。
# 用法: verify-attestation.sh --report <path> --bundle <path> [--expected-issuer <url>] [--expected-identity-regexp <regex>]
# 成功: { "ok": true }
# 失败: { "ok": false, "error": "invalid_signature" | "identity_not_allowed" | "cosign_error" }

set -e
REPORT_PATH=""
BUNDLE_PATH=""
EXPECTED_ISSUER="https://token.actions.githubusercontent.com"
EXPECTED_IDENTITY_REGEXP='^https://github\.com/[^/]+/[^/]+/\.github/workflows/skillscan\.yml@'

while [[ $# -gt 0 ]]; do
  case $1 in
    --report)   REPORT_PATH="$2"; shift 2 ;;
    --bundle)   BUNDLE_PATH="$2"; shift 2 ;;
    --expected-issuer) EXPECTED_ISSUER="$2"; shift 2 ;;
    --expected-identity-regexp) EXPECTED_IDENTITY_REGEXP="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [[ -z "$REPORT_PATH" ]] || [[ -z "$BUNDLE_PATH" ]] || [[ ! -f "$REPORT_PATH" ]] || [[ ! -f "$BUNDLE_PATH" ]]; then
  echo '{"ok":false,"error":"cosign_error"}'
  exit 1
fi

if ! command -v cosign &>/dev/null; then
  echo '{"ok":false,"error":"cosign_error"}'
  exit 1
fi

STDERR=$(mktemp)
if cosign verify-blob "$REPORT_PATH" \
  --bundle "$BUNDLE_PATH" \
  --certificate-oidc-issuer "$EXPECTED_ISSUER" \
  --certificate-identity-regexp "$EXPECTED_IDENTITY_REGEXP" \
  2>"$STDERR"; then
  echo '{"ok":true}'
  rm -f "$STDERR"
  exit 0
fi

if grep -qi "identity" "$STDERR" 2>/dev/null; then
  echo '{"ok":false,"error":"identity_not_allowed"}'
else
  echo '{"ok":false,"error":"invalid_signature"}'
fi
rm -f "$STDERR"
exit 1
