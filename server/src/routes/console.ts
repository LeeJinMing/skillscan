/**
 * Web 管理台：Scans / Approvals / Audit 页面
 * 需登录；数据通过现有 API 获取
 */
import type { FastifyInstance, FastifyPluginOptions } from "fastify";
import { getSessionUserId } from "../session.js";
import type { ErrorBody } from "../types.js";

function layout(title: string, body: string, baseUrl: string): string {
  return `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title)} - SkillScan</title>
<style>
  *{box-sizing:border-box} body{font-family:system-ui,sans-serif;margin:0;background:#f6f8fa}
  .nav{background:#24292f;color:#fff;padding:.75rem 1.5rem;display:flex;gap:1.5rem;align-items:center}
  .nav a{color:#fff;text-decoration:none} .nav a:hover{text-decoration:underline}
  .main{max-width:960px;margin:0 auto;padding:1.5rem}
  table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}
  th,td{padding:.75rem 1rem;text-align:left;border-bottom:1px solid #eaeef2}
  th{background:#f6f8fa;font-weight:600}
  .badge{display:inline-block;padding:.2em .5em;border-radius:4px;font-size:.85em}
  .badge-allowed{background:#d4edda;color:#155724}
  .badge-approved{background:#cce5ff;color:#004085}
  .badge-needs_approval{background:#fff3cd;color:#856404}
  .badge-blocked{background:#f8d7da;color:#721c24}
  .btn{padding:.4em .8em;border-radius:4px;border:none;cursor:pointer;font-size:.9em}
  .btn-primary{background:#0969da;color:#fff} .btn-primary:hover{background:#0550ae}
  .btn-danger{background:#cf222e;color:#fff} .btn-danger:hover{background:#a40e26}
  .empty{color:#6e7781;padding:2rem;text-align:center}
</style></head>
<body>
  <nav class="nav">
    <a href="${baseUrl}/console">SkillScan</a>
    <a href="${baseUrl}/console">控制台</a>
    <a href="${baseUrl}/console/scans">扫描</a>
    <a href="${baseUrl}/console/approvals">待审批</a>
    <a href="${baseUrl}/console/audit">审计</a>
  </nav>
  <main class="main">${body}</main>
</body></html>`;
}

function escapeHtml(s: string | number | null | undefined): string {
  const str = s == null ? "" : String(s);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function badgeClass(status: string | number | null | undefined): string {
  const s = String(status ?? "").toLowerCase();
  if (s === "allowed") return "badge-allowed";
  if (s === "approved") return "badge-approved";
  if (s === "needs_approval") return "badge-needs_approval";
  if (s === "blocked") return "badge-blocked";
  return "";
}

export async function consoleRoutes(app: FastifyInstance, _opts: FastifyPluginOptions) {
  const baseUrl: string = process.env.PUBLIC_BASE_URL ?? "http://localhost:3001";

  app.get("/console", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.redirect(`${baseUrl}/auth/github/start`, 302);
    }
    const body = `
      <h1>SkillScan 控制台</h1>
      <p>已登录。请选择：</p>
      <ul>
        <li><a href="${baseUrl}/console/scans">扫描记录</a> — 查看所有扫描结果</li>
        <li><a href="${baseUrl}/console/approvals">待审批</a> — 待审批的 needs_approval 扫描</li>
        <li><a href="${baseUrl}/console/audit">审计日志</a> — 操作记录</li>
      </ul>`;
    return reply.type("text/html").send(layout("控制台", body, baseUrl));
  });

  app.get("/console/scans", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.redirect(`${baseUrl}/auth/github/start`, 302);
    }
    const res = await app.db?.query(
      `SELECT s.id, s.repo, s.commit_sha, s.verdict_status, s.verdict_reason, s.created_at
       FROM scans s
       JOIN tenants t ON t.id = s.org_id
       WHERE t.owner_user_id = $1::uuid
       ORDER BY s.created_at DESC
       LIMIT 50`,
      [userId],
    );
    const rows = res?.rows ?? [];
    let table = "";
    if (rows.length === 0) {
      table = '<p class="empty">暂无扫描记录</p>';
    } else {
      table = `
        <table>
          <thead><tr><th>Repo</th><th>Commit</th><th>状态</th><th>时间</th><th></th></tr></thead>
          <tbody>
            ${rows
              .map(
                (r) =>
                  `<tr>
                    <td>${escapeHtml(String(r.repo))}</td>
                    <td><code>${escapeHtml(String(r.commit_sha).slice(0, 8))}</code></td>
                    <td><span class="badge ${badgeClass(r.verdict_status)}">${escapeHtml(String(r.verdict_status))}</span></td>
                    <td>${new Date(r.created_at).toLocaleString()}</td>
                    <td><a href="${baseUrl}/scans/${r.id}" class="btn btn-primary">查看</a></td>
                  </tr>`,
              )
              .join("")}
          </tbody>
        </table>`;
    }
    const body = `<h1>扫描记录</h1>${table}`;
    return reply.type("text/html").send(layout("扫描", body, baseUrl));
  });

  app.get("/console/approvals", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.redirect(`${baseUrl}/auth/github/start`, 302);
    }
    const res = await app.db?.query(
      `SELECT s.id, s.repo, s.commit_sha, s.verdict_reason, s.created_at
       FROM scans s
       JOIN tenants t ON t.id = s.org_id
       WHERE t.owner_user_id = $1::uuid AND s.verdict_status = 'needs_approval'
       ORDER BY s.created_at DESC
       LIMIT 50`,
      [userId],
    );
    const rows = res?.rows ?? [];
    let table = "";
    if (rows.length === 0) {
      table = '<p class="empty">暂无待审批项</p>';
    } else {
      table = `
        <table>
          <thead><tr><th>Repo</th><th>Commit</th><th>原因</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            ${rows
              .map(
                (r) =>
                  `<tr>
                    <td>${escapeHtml(String(r.repo))}</td>
                    <td><code>${escapeHtml(String(r.commit_sha).slice(0, 8))}</code></td>
                    <td>${escapeHtml(String(r.verdict_reason || "").slice(0, 80))}</td>
                    <td>${new Date(r.created_at).toLocaleString()}</td>
                    <td>
                      <button type="button" class="btn btn-primary" data-action="approve" data-repo="${escapeHtml(String(r.repo))}" data-commit="${escapeHtml(String(r.commit_sha))}">通过</button>
                      <button type="button" class="btn btn-danger" data-action="reject" data-repo="${escapeHtml(String(r.repo))}" data-commit="${escapeHtml(String(r.commit_sha))}" style="margin-left:4px">拒绝</button>
                    </td>
                  </tr>`,
              )
              .join("")}
          </tbody>
        </table>
        <script>
          document.querySelectorAll('[data-action]').forEach(btn=>{
            btn.onclick=async()=>{
              const action=btn.dataset.action;
              const url='${baseUrl}/'+(action==='approve'?'approve':'reject');
              const body={repo:btn.dataset.repo,commit_sha:btn.dataset.commit};
              try{
                const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'include'});
                const d=await r.json();
                alert(d.ok?(action==='approve'?'已通过':'已拒绝'):(d.code||'失败'));
                if(d.ok)location.reload();
              }catch(e){alert('请求失败');}
            };
          });
        </script>`;
    }
    const body = `<h1>待审批</h1>${table}`;
    return reply.type("text/html").send(layout("待审批", body, baseUrl));
  });

  app.get("/console/audit", async (req, reply) => {
    const userId = getSessionUserId(req);
    if (!userId) {
      return reply.redirect(`${baseUrl}/auth/github/start`, 302);
    }
    const res = await app.db?.query(
      `SELECT a.id, a.actor, a.action, a.target_type, a.target_id, a.created_at, a.metadata
       FROM audit_log a
       JOIN tenants t ON t.id = a.org_id
       WHERE t.owner_user_id = $1::uuid
       ORDER BY a.created_at DESC
       LIMIT 50`,
      [userId],
    );
    const rows = res?.rows ?? [];
    let table = "";
    if (rows.length === 0) {
      table = '<p class="empty">暂无审计记录</p>';
    } else {
      table = `
        <table>
          <thead><tr><th>操作</th><th>类型</th><th>目标</th><th>时间</th></tr></thead>
          <tbody>
            ${rows
              .map(
                (r) =>
                  `<tr>
                    <td>${escapeHtml(String(r.action))}</td>
                    <td>${escapeHtml(String(r.target_type))}</td>
                    <td><code>${escapeHtml(String(r.target_id).slice(0, 20))}</code></td>
                    <td>${new Date(r.created_at).toLocaleString()}</td>
                  </tr>`,
              )
              .join("")}
          </tbody>
        </table>`;
    }
    const body = `<h1>审计日志</h1>${table}`;
    return reply.type("text/html").send(layout("审计", body, baseUrl));
  });
}
