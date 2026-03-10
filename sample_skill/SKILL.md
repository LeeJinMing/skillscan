---
skill_id: kowl64/linux-service-triage
version: 0.1.0
ecosystem: clawdbot
---

# Linux service triage

Collect status then suggest; avoid blind restart.

## Usage

Check status first:

```bash
systemctl status nginx
journalctl -u nginx -n 50
```

If needed, restart (requires approval):

```bash
sudo systemctl restart nginx
```
