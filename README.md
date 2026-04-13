# homelab

A calculator app built from scratch as a hands-on DevOps learning project. The app itself is intentionally simple — the point is everything around it: containers, networking, databases, secrets management, CI/CD, cloud deployment, and image registries.

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
| Image Registry | AWS ECR | Private registry — images built in CI, pulled on EC2 |
| CI/CD | GitHub Actions (hosted runners) | Build image, push to ECR, SSH deploy on every push |
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
│    /        → index.html                │
│    /api/*   → proxy to backend:8000     │
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
├── Dockerfile                     # builds the backend container image
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
ECR_REPOSITORY_URL=<account-id>.dkr.ecr.eu-west-3.amazonaws.com/homelab
EOF
```

**Important — changing the postgres password:**
`POSTGRES_PASSWORD` only takes effect on first container creation. If the postgres volume already exists, changing `.env` has no effect. To change the password on a running database:
```bash
docker compose exec db psql -U postgres -c \
  "ALTER USER youruser WITH PASSWORD 'newpassword';"
docker compose restart backend
```

---

## ci/cd pipeline

Every push to `main` triggers automatic deployment via two sequential jobs.

```
git push origin main
        │
        ▼
Job 1: build-and-push (GitHub-hosted runner)
  ├── checkout code
  ├── authenticate to ECR
  ├── docker build
  └── docker push (tagged with git SHA + latest)
        │
        ▼ (only runs if Job 1 succeeded)
Job 2: deploy (GitHub-hosted runner)
  ├── SSH into EC2
  ├── git pull origin main
  ├── docker compose pull
  └── docker compose up -d
```

EC2 never builds anything — it only pulls the pre-built image from ECR. Every deployed image is permanently addressable by its git SHA for easy rollbacks.

**GitHub Actions secrets required:**

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user with ECR push permissions |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |
| `ECR_REPOSITORY_URL` | `<account-id>.dkr.ecr.eu-west-3.amazonaws.com/homelab` |
| `SSH_HOST` | `homelab.skander.cc` |
| `SSH_USER` | `ubuntu` |
| `SSH_PRIVATE_KEY` | contents of `~/.ssh/homelab-ec2` |

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
docker logs homelab-backend-1
```

**3. Is the backend reachable internally?**
```bash
docker compose exec frontend wget -qO- http://backend:8000/health
```

**4. Is nginx config valid?**
```bash
docker compose exec frontend nginx -t
```

**5. Does nginx correctly strip /api before forwarding?**
```nginx
location /api/ {
    proxy_pass http://backend:8000/;   # trailing slash strips /api prefix
}
```
`/api/add` becomes `/add` at the backend. Remove either trailing slash and the backend gets `/api/add` — 404.

**6. Is the .env file present on EC2?**
```bash
cat /home/ubuntu/homelab/.env
ls -la /home/ubuntu/homelab/.env   # should show -rw------- (mode 600)
```

**7. Does DNS resolve to the right IP?**
```bash
nslookup homelab.skander.cc
curl ifconfig.me   # run on EC2 — should match
```

**8. Is the browser forcing HTTPS?**
The app only runs on HTTP (port 80). Try `http://homelab.skander.cc` explicitly.

---

## useful commands

```bash
# containers
docker ps
docker compose up -d
docker compose down
docker compose down -v              # wipe volumes (resets database)
docker compose logs --tail=50
docker compose restart backend

# test api
curl http://localhost/api/health
curl -X POST http://localhost/api/add \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 5}'

# database
docker exec -it homelab-db-1 psql -U skander -d calcdb
  \dt                              # list tables
  SELECT * FROM history;
  \q                               # exit

# change postgres password
docker exec -it homelab-db-1 psql -U postgres -c \
  "ALTER USER skander WITH PASSWORD 'newpassword';"
docker compose restart backend

# trigger deploy without code changes
git commit --allow-empty -m "redeploy" && git push

# check DNS
nslookup homelab.skander.cc
curl ifconfig.me   # run on EC2
```

---

## issues encountered and how they were fixed

**"Could not reach API" in the frontend**
The `fetch()` call hits the `catch` block — request failed entirely. Check containers are running and backend logs for startup crashes.

**Backend container exits immediately on startup**
`init_db()` runs at import time. If postgres connection fails, Python crashes before FastAPI starts. Check `docker logs homelab-backend-1` for the exact error.

**Postgres password mismatch after changing .env**
`POSTGRES_PASSWORD` only sets the password on first volume creation. Fix: `ALTER USER` inside the container, then restart backend.

**nginx 404 on /api routes**
Trailing slash on `proxy_pass` matters. `http://backend:8000/` strips the `/api` prefix. Without it, the full path is forwarded and backend returns 404.

**docker compose down causes downtime**
`down` then `up` kills the app completely between commands. Use `docker compose up -d` directly — Compose only restarts containers whose image changed.

**App not loading despite containers being up**
DNS was pointing to old EC2 IP after a destroy/apply. Fixed by running `terraform apply` which updated the Cloudflare A record automatically.

**SSH authentication failing from GitHub Actions**
Multiple issues stacked:
- `appleboy/ssh-action` fingerprint verification kept failing — abandoned in favour of plain `ssh` command
- `printf '%s'` strips trailing newline causing `error in libcrypto` — fixed with `echo | tr -d '\r'`
- `SSH_USER` secret was set to `skander` instead of `ubuntu` — root cause, found via `/var/log/auth.log`

**ECR image not found on first deploy**
Fresh ECR registry is empty — `docker compose pull` fails. Ansible now checks image count before starting containers and skips on first provision. First real deploy happens via GitHub Actions after pushing a commit.

---

## things learned

**Docker**
- Dockerfile builds an image. Image = blueprint, container = running instance.
- `expose` makes a port internal only. `ports` maps it to the host.
- Containers find each other by service name — Docker's internal DNS resolves `backend`, `db` etc.
- Named volumes persist data outside containers. `down -v` deletes them — resets all state.

**ECR**
- Build once in CI, pull everywhere — EC2 should never compile code.
- Every image gets two tags: `latest` (what EC2 pulls) and the git SHA (permanent addressable record).
- EC2 authenticates to ECR via IAM instance profile — no credentials stored on the server.

**Secrets**
- Never hardcode secrets in files that get committed.
- Docker Compose automatically loads `.env` from the same directory.
- `git log --all -p | grep yourpassword` — always run before pushing to check for leaks.

**Networking**
- nginx as reverse proxy: one public port handles everything. `/api/*` forwarded internally to FastAPI.
- Trailing slash on `proxy_pass` matters: `http://backend:8000/` strips the matched prefix.

**Database**
- `depends_on` only waits for container start, not postgres readiness. Health checks fix this.
- `condition: service_healthy` waits for `pg_isready` before starting backend.
- First boot initializes postgres from env vars. Existing volume = env vars ignored on restart.

**CI/CD**
- GitHub Actions reads `.github/workflows/deploy.yml` on every push to main.
- `needs:` ensures deploy job never runs if build+push failed.
- `docker compose up -d` without `down` = only changed containers restart.
- Check `/var/log/auth.log` on the server when SSH auth fails — it shows the exact rejection reason and what username was used.
*