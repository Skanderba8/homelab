# homelab

A calculator app built from scratch as a hands-on DevOps learning project. The app itself is intentionally simple — the point is everything around it: containers, networking, databases, secrets management, CI/CD, and cloud deployment.

---

## what this is

A FastAPI backend with a frontend served by nginx and a PostgreSQL database, fully containerized with Docker Compose, deployed on AWS EC2, accessible at [homelab.skander.cc](http://homelab.skander.cc), and automatically deployed on every git push via GitHub Actions.

---

## stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI (Python) | Simple, fast to write, easy to curl-test |
| Frontend | HTML + nginx | Minimal UI, no framework needed |
| Database | PostgreSQL | Industry standard, runs great in Docker |
| Containers | Docker + Docker Compose | Reproducible, isolated environments |
| CI/CD | GitHub Actions (self-hosted runner) | Auto-deploy on push, runner lives on EC2 |
| Server | AWS EC2 t3.micro | Real cloud server, free tier eligible |
| DNS | Cloudflare | homelab.skander.cc → EC2 IP |

---

## architecture

```
Browser
  │
  │ http://homelab.skander.cc (port 80)
  ▼
Cloudflare DNS → EC2 eu-west-3
  │
  ▼
┌─────────────────────────────────────────┐
│           Docker network                │
│                                         │
│  nginx (port 80, public)                │
│    /        → index.html               │
│    /api/*   → proxy to backend:8000    │
│         │                               │
│         ▼ internal                      │
│  fastapi (port 8000, internal only)     │
│         │                               │
│         ▼ internal                      │
│  postgres (port 5432, internal only)    │
│  data persisted in Docker volume        │
└─────────────────────────────────────────┘
```

Only port 80 is exposed. The backend and database are never reachable from the outside world.

---

## project structure

```
homelab/
├── main.py                        # FastAPI app — all backend logic + postgres
├── Dockerfile                     # builds the backend container
├── docker-compose.yml             # orchestrates nginx, fastapi, postgres
├── nginx.conf                     # serves frontend, proxies /api/* to backend
├── index.html                     # frontend UI
├── .env                           # runtime secrets — GITIGNORED, never commit
├── .gitignore
└── .github/
    └── workflows/
        └── deploy.yml             # CI/CD pipeline
```

---

## api endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | liveness check |
| POST | `/api/add` | a + b |
| POST | `/api/subtract` | a - b |
| POST | `/api/multiply` | a × b |
| POST | `/api/divide` | a ÷ b (handles division by zero) |
| POST | `/api/power` | a ^ b |
| GET | `/api/history` | last 20 calculations |
| DELETE | `/api/history` | clear all history |

All POST endpoints accept `{"a": 10, "b": 5}`.

---

## secrets — how they work

Secrets are never hardcoded in this repo. `docker-compose.yml` uses `${VARIABLE}` placeholders and reads values from a `.env` file in the same directory.

```yaml
# docker-compose.yml reads variables like this:
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  DATABASE_URL: ${DATABASE_URL}
```

The `.env` file is gitignored and never committed. Locally you create it manually. On EC2, Ansible creates it automatically from `vars.yml` in the infra repo.

**Creating `.env` locally:**
```bash
cat > .env << EOF
POSTGRES_USER=youruser
POSTGRES_PASSWORD=yourpassword
POSTGRES_DB=calcdb
DATABASE_URL=postgresql://youruser:yourpassword@db:5432/calcdb
EOF
```

**Verify secrets loaded correctly:**
```bash
docker compose exec db env | grep POSTGRES
docker compose exec backend env | grep DATABASE_URL
```

**Important — changing the postgres password:**
`POSTGRES_PASSWORD` only takes effect on first container creation. If the postgres volume already exists, changing `.env` has no effect. To change the password on a running database:
```bash
docker compose exec db psql -U postgres -c \
  "ALTER USER youruser WITH PASSWORD 'newpassword';"
docker compose restart backend
```

---

## running locally

```bash
git clone https://github.com/Skanderba8/homelab
cd homelab

# create .env file (never commit this)
nano .env

# start containers
docker compose up -d --build

# verify
docker ps
curl http://localhost/api/health
```

---

## ci/cd pipeline

Every push to `main` triggers automatic deployment.

```
git push origin main
        │
        ▼
GitHub detects push → triggers deploy.yml
        │
        ▼
self-hosted runner on EC2 picks up the job
        │
        ├── git pull origin main
        └── docker compose up -d --build
```

The runner is a process running permanently on EC2, installed as a systemd service. It polls GitHub outbound — no open port needed, no SSH from GitHub into the server.

**Current deploy.yml behavior:**
- `docker compose up -d --build` without `down` first — avoids unnecessary downtime
- Compose only restarts containers whose image actually changed
- Build happens on the EC2 itself (no image registry yet)

**Why self-hosted instead of GitHub-hosted:**
GitHub-hosted runners are fresh VMs with no access to your EC2. A self-hosted runner lives on EC2 itself — deployment is just running commands locally.

**Important — multiple runners:**
If more than one runner is registered with the `self-hosted` label, GitHub picks whichever is available. This causes jobs to silently run on the wrong machine. Always check GitHub → Settings → Actions → Runners and remove stale runners.

---

## debugging checklist

If the app isn't loading at homelab.skander.cc, check in this order:

**1. Are containers running?**
```bash
docker ps
# all 3 should show Up: homelab-frontend-1, homelab-backend-1, homelab-db-1
```

**2. Check container logs for errors:**
```bash
docker compose logs --tail=50
docker logs homelab-backend-1   # backend startup errors
```

**3. Is the backend reachable internally?**
```bash
docker compose exec frontend wget -qO- http://backend:8000/health
# should return {"status":"ok"}
# if 500 → backend is up but hitting an error (check logs)
# if connection refused → backend container is down
```

**4. Is nginx config valid?**
```bash
docker compose exec frontend nginx -t
# should say "syntax is ok"
```

**5. Does nginx correctly strip /api before forwarding?**
The nginx config uses trailing slashes on both sides:
```nginx
location /api/ {
    proxy_pass http://backend:8000/;   # trailing slash strips /api prefix
}
```
`/api/add` becomes `/add` at the backend. If you remove either trailing slash, the full path is forwarded and the backend gets `/api/add` which it doesn't have — 404.

**6. Is the .env file present on EC2?**
```bash
cat /home/ubuntu/homelab/.env
ls -la /home/ubuntu/homelab/.env   # should show -rw------- (mode 600)
```
If missing, re-run Ansible from the infra repo.

**7. Does DNS resolve to the right IP?**
```bash
nslookup homelab.skander.cc
curl ifconfig.me   # run on EC2 — should match
```

**8. Is the browser forcing HTTPS?**
The app only runs on HTTP (port 80). Try `http://homelab.skander.cc` explicitly.

**9. Are CI/CD jobs running on the right runner?**
GitHub → Actions → latest run → check `Runner name` in logs. Should say `ec2-runner`.

---

## useful commands

```bash
# containers
docker ps
docker compose up -d --build
docker compose down
docker compose down -v              # wipe volumes (resets database completely)
docker compose logs --tail=50
docker logs homelab-backend-1
docker compose restart backend

# test api
curl http://localhost/api/health
curl -X POST http://localhost/api/add \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 5}'

# verify secrets loaded
docker compose exec db env | grep POSTGRES
docker compose exec backend env | grep DATABASE_URL

# database
docker exec -it homelab-db-1 psql -U skander -d calcdb
  \dt                              # list tables
  SELECT * FROM history;           # see all calculations
  \q                               # exit

# change postgres password (after updating .env)
docker exec -it homelab-db-1 psql -U postgres -c \
  "ALTER USER skander WITH PASSWORD 'newpassword';"
docker compose restart backend

# check runner on EC2
systemctl status actions.runner.*
journalctl -u actions.runner.* -n 50
sudo systemctl restart actions.runner.Skanderba8-homelab.ec2-runner.service

# check DNS
nslookup homelab.skander.cc
curl ifconfig.me   # run on EC2
```

---

## issues encountered and how they were fixed

**"Could not reach API" in the frontend**
The `fetch()` call hits the `catch` block — meaning the request failed entirely, not a 4xx/5xx. Check containers are running and backend logs for startup crashes.

**Backend container exits immediately on startup**
`init_db()` runs at import time. If postgres connection fails (wrong password, db not ready), Python crashes before FastAPI even starts. Check `docker logs homelab-backend-1` for the exact error.

**Postgres password mismatch after changing .env**
`POSTGRES_PASSWORD` only sets the password on first volume creation. Changing it afterward has no effect. Fix: `ALTER USER` inside the container, then restart backend.

**nginx 404 on /api routes**
Check the trailing slash on `proxy_pass`. `proxy_pass http://backend:8000/` (with slash) strips the `/api` prefix. Without the slash, the full path is forwarded and the backend returns 404.

**Secrets visible in git history**
`git log --all -p | grep yourpassword` reveals old commits. Changing the password is the real fix — git history rewriting is cosmetic once the repo is public. Always check `git grep` before pushing.

**docker compose down causes downtime**
`down` then `up` kills the app completely between commands. Use `docker compose up -d --build` directly — Compose only restarts containers whose image changed.

**App not loading despite containers being up**
DNS was pointing to old EC2 IP after a destroy/apply. Fixed by running `terraform apply` which updated the Cloudflare A record automatically.

**CI/CD running on local VM instead of EC2**
Two self-hosted runners registered. Fixed by removing the old runner from GitHub → Settings → Actions → Runners.

**Port 80 already in use**
Old frontend container still running. Fixed with `docker compose down` then `docker compose up -d --build`.

**Docker build using cached old files**
Force a clean build:
```bash
docker compose up -d --build --no-cache
```

---

## things learned

**Docker**
- Dockerfile builds an image. Image = blueprint, container = running instance.
- `expose` makes a port internal only. `ports` maps it to the host (public).
- Containers find each other by service name — Docker's internal DNS resolves `backend`, `db` etc.
- Named volumes persist data outside containers. `down -v` deletes them — resets all state.

**Secrets**
- Never hardcode secrets in files that get committed.
- Docker Compose automatically loads `.env` from the same directory — no configuration needed.
- `${VARIABLE}` in docker-compose.yml reads from `.env`.
- `docker inspect` shows env vars — expected behavior, only accessible via SSH.
- `git grep yourpassword` — always run this before pushing to check for leaks.

**Networking**
- nginx as reverse proxy: one public port handles everything. `/api/*` forwarded internally to FastAPI.
- Trailing slash on `proxy_pass` matters: `http://backend:8000/` strips the matched prefix, `http://backend:8000` does not.

**Database**
- `depends_on` only waits for container start, not postgres readiness. Health checks fix this.
- `condition: service_healthy` waits for `pg_isready` to succeed before starting backend.
- First boot initializes postgres from env vars. Existing volume = env vars ignored on restart.
- `ALTER USER` is the only way to change password on a running database.

**CI/CD**
- GitHub Actions reads `.github/workflows/deploy.yml` on every push to main.
- Self-hosted runner = your server polls GitHub, picks up jobs, runs them locally.
- `docker compose up -d --build` without `down` = zero unnecessary downtime.
- Multiple runners with same label = jobs go to wrong machine.