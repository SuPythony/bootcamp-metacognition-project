# Aporeka — Deployment Guide

The product runs on the team's **AWS EC2 instance** (instance details in team channel, not in this repo).

---

## Topology

- One EC2 host runs both backend (FastAPI on port 8000) and frontend (static build served by nginx on port 80/443).
- Nginx is the public-facing entry: serves frontend static files, reverse-proxies `/api/*` to the FastAPI on 127.0.0.1:8000 (so SSE works without CORS gymnastics).
- HTTPS via Let's Encrypt (`certbot --nginx`). Re-uses the EC2 instance's public DNS or a team-provided subdomain.
- No load balancer, no autoscaling — this is a demo box.

---

## Process management

- Backend: `systemd` unit running `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`. Single worker because session state is in-memory; sticky sessions on multiple workers would need shared storage (out of scope for v1).
- Frontend: built into `frontend/dist/` at deploy time, served as static files. No node process in production.
- Logs to journald; `journalctl -u aporeka` reads them.

---

## Environment variables (production)

Backend env vars (`/etc/aporeka.env`, `chmod 600`, read via `EnvironmentFile=` in the systemd unit):

| Var | Value |
|---|---|
| `OPENROUTER_API_KEY` | Secret — never in repo or Docker image |
| `LLM_MODEL_TUTOR` | `google/gemini-2.5-flash` |
| `LLM_MODEL_CLASSIFIER` | `qwen/qwen3-6b` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `PERSONA_DIR` | `./personas` |
| `ALLOWED_ORIGINS` | public hostname (CSV) |
| `LOG_LLM_CALLS` | `false` in production |
| `LLM_MAX_TOKENS` | `2048` |

Frontend is built with `VITE_API_URL=/api` and `VITE_USE_MOCK=false`. The frontend never talks directly to OpenRouter.

---

## Deploy steps (manual v1)

```bash
# 1. SSH to EC2
ssh <instance>

# 2. Pull latest
git pull

# 3. Backend
cd backend
.venv/bin/pip install -e ".[dev,math]"
sudo systemctl restart aporeka

# 4. Frontend
cd ../frontend
npm install && npm run build
sudo cp -r dist/* /var/www/aporeka/

# 5. Reload nginx
sudo nginx -t && sudo systemctl reload nginx
```

A `deploy/deploy.sh` script wrapping these steps with `set -e` and a health check is tracked in ISSUES.md #2.

---

## Health check

`GET /health` returns `{"status": "ok", "model": LLM_MODEL_TUTOR}`. Use this to confirm the server is up and the env is configured before declaring a deploy successful. (Not yet implemented — see ISSUES.md #2.)

---

## Persona files in production

`backend/personas/*.json` is the only on-disk state. It survives restarts because it's a regular directory, not a tmpfs. Back up periodically:

```bash
# daily cron (not yet configured — see ISSUES.md #2)
tar -czf ~/persona-backups/personas-$(date +%Y%m%d).tar.gz backend/personas/
```

If the host is rebuilt, persona files must be preserved out-of-band — they are the only thing in this system that cannot be regenerated.

---

## Out of scope (v1)

Auth tokens, Firebase/cloud storage, cross-session learning, multi-user concurrency at scale, persona editing UI, teacher dashboards, mobile-first layout.
