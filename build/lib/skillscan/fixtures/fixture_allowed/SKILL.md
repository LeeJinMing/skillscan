---
skill_id: fixture/allowed-only
version: 0.1.0
ecosystem: clawdbot
category: devops
---

# Allowed only (read-only diagnostics)

Read-only commands only: status, logs, listen ports, HTTP head.

```bash
systemctl status nginx
journalctl -u nginx -n 20
ss -tlnp
curl -I http://localhost/
```
