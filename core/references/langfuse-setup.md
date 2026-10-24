# Langfuse Self-Hosted Setup (GTM agent Monthly Evaluation)

**Status: ⚠️ BLOCKED on root access — infra prepared, not yet running.**

This doc records the full intended setup, what's already prepared, and the exact
one-command path to finish once root is available. See "Blocker" below.

## Purpose
Self-hosted Langfuse instance on `agent-vm` for the GTM agent monthly evaluation.
Eval pipeline (promptfoo, in `~/.openclaw/workspace/projects/gtm-agent-eval/`) will
ingest traces/evals into Langfuse via the public/secret API keys.

## Architecture
Official Langfuse self-host docker-compose (v4 images, ClickHouse-backed).
Services: `langfuse-web` (:3000), `langfuse-worker` (:3030), `postgres` (:5432),
`clickhouse` (:8123/:9000), `minio` (:9090/:9091), `redis` (:6379).

- **Loopback only** ({{COMPANY}} policy): web binds `3000:3000` (localhost), all
  datastores bind `127.0.0.1`. No public inbound.
- **Persistent volumes** (named, `driver: local`): `langfuse_postgres_data`,
  `langfuse_clickhouse_data`, `langfuse_clickhouse_logs`, `langfuse_minio_data`,
  `langfuse_redis_data`. Survives container restarts.
- **Survives VM reboot**: systemd unit `langfuse.service` (enabled) + `restart: always`
  on every container.

## Location
- Repo + config: `~/langfuse/`
  - `docker-compose.yml` (official, from github.com/langfuse/langfuse)
  - `.env` (secrets + auto-init config)
  - `langfuse.service` (systemd unit)
  - `install.sh` (root install script)
- Setup doc: `~/.openclaw/workspace/references/langfuse-setup.md`

## Project + API Keys
Auto-created on first boot via `LANGFUSE_INIT_*` env vars in `.env`:
- Org: `gtm-agent` / `GTM agent`
- Project: `gtm-agent-eval`
- Public key: `pk-lf-REDACTED_ID`
- Secret key: `sk-lf-REDACTED_ID`
- Bootstrap user: `rep@example.com` (password in `.env`)

**Keys are also stored in `~/.openclaw/.env` as:**
- `LANGFUSE_PUBLIC_KEY=pk-lf-REDACTED_ID`
- `LANGFUSE_SECRET_KEY=sk-lf-REDACTED_ID`
- `LANGFUSE_HOST=http://localhost:3000`

## ⚠️ BLOCKER — Root access required
Docker is **not installed** on this VM, and installing it + the systemd unit
requires root. Current session has **no root path**:
- `sudo` requires a password (user is in `sudo` group but no NOPASSWD).
- Elevated exec is disabled (`tools.elevated.enabled` gate).
- `gcloud` tokens expired (reauth needed); compute SA lacks compute/OSLogin scopes.
- Rootless Docker prereqs (`newuidmap`, `slirp4netns`) not installed (need root).

### Unblock path (one command, once root is available)
```bash
sudo bash ~/langfuse/install.sh
```
This installs Docker Engine + compose plugin, enables Docker, adds
the agent user to the `docker` group, installs+enables the `langfuse.service`
systemd unit, and starts the stack. Then verify:
```bash
docker compose -f ~/langfuse/docker-compose.yml ps
curl -s http://localhost:3000/api/public/health
systemctl status langfuse
```

## Operations

### Restart the stack
```bash
sudo systemctl restart langfuse        # or:
cd ~/langfuse && docker compose restart
```

### Where data lives
Named Docker volumes (persistent, survive container recreation):
```bash
docker volume ls | grep langfuse
# langfuse_postgres_data, langfuse_clickhouse_data, langfuse_clickhouse_logs,
# langfuse_minio_data, langfuse_redis_data
```
Backup = `docker run --rm -v langfuse_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/pg.tgz -C /data .` (repeat per volume).

### Rotate API keys
1. Edit `.env`: change `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` / `..._SECRET_KEY`
   (and the `LANGFUSE_INIT_*` block) to new `pk-lf-`/`sk-lf-` values.
2. Update `~/.openclaw/.env` `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`.
3. `sudo systemctl restart langfuse`.
4. Re-verify health + project.

### Rotate infra secrets (postgres/clickhouse/redis/minio)
Regenerate each with `openssl rand -hex 16`, update `.env`, restart. Note: changing
`POSTGRES_PASSWORD`/`CLICKHOUSE_PASSWORD` after first boot requires updating the
running DB users too (or wipe the volume — destructive).

## Health check
```bash
curl -s http://localhost:3000/api/public/health
# {"status":"OK", ...}
```

## Notes / Constraints
- {{COMPANY}} policy: loopback only, least-privilege, no public inbound. ✓
- This step is **infra only** — no OpenClaw config, cron, or outbound-engine code
  was touched.
- `TELEMETRY_ENABLED=false` (privacy).
