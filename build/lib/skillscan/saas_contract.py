"""
SaaS POST /reports 响应契约：approval_elevation_applied / approval_scope_matched。
供服务端实现与客户端契约单测使用。
"""
from __future__ import annotations

from typing import Any


def build_post_reports_response(
    scan_id: str,
    verdict_status: str,
    reason: str = "",
    *,
    approval_elevation_applied: bool = False,
    approval_scope_matched: dict[str, Any] | None = None,
    console_url: str = "",
) -> dict[str, Any]:
    """
    构建 POST /reports 响应体（契约固定结构）。
    approval_elevation_applied：本次 verdict 是否由 needs_approval + 审批通过 提升为 approved。
    approval_scope_matched：当 approval_elevation_applied 为 True 时填 scope 信息；否则 null。
    """
    return {
        "scan_id": scan_id,
        "verdict": {"status": verdict_status, "reason": reason},
        "approval_elevation_applied": approval_elevation_applied,
        "approval_scope_matched": approval_scope_matched,
        "console_url": console_url or "",
    }
