# homelab

A calculator app built from scratch as a hands-on DevOps learning project. The app itself is intentionally simple — the point is everything around it: containers, networking, databases, CI/CD, and cloud deployment.

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
│           Docker Network                │
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

## project structure

```
homelab/
├── main.py                        # FastAPI app — all backend logic + postgres
├── Dockerfile                     # builds the backend container
├── docker-compose.yml             # orchestrates nginx, fastapi, postgres
├── nginx.conf                     # serves frontend, proxies /api/* to backend
├── index.html                     # frontend UI
├── .gitignore
└── .github/
    └── workflows/
        └── deploy.yml             # CI/CD pipeline
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
        ├── docker compose down
        └── docker compose up -d --build
```

The runner is a process running permanently on EC2. It polls GitHub outbound — no open port needed, no SSH from GitHub into the server.

**Why self-hosted instead of GitHub-hosted:**
GitHub-hosted runners are fresh VMs on GitHub's servers. They have no access to your private EC2. A self-hosted runner lives on EC2 itself, so deployment is just running commands locally — no SSH juggling needed.

**Important — multiple runners:**
If you have more than one runner registered with the `self-hosted` label, GitHub picks whichever is available. This can cause jobs to silently run on the wrong machine (e.g. your old local VM). Always check GitHub repo → Settings → Actions → Runners and remove any stale runners.

---

## running locally

```bash
git clone https://github.com/Skanderba8/homelab
cd homelab
docker compose up -d --build
docker ps
curl http://localhost/api/health
```

---

## useful commands

```bash
# containers
docker ps
docker compose up -d --build
docker compose down
docker compose down -v          # wipe volumes (resets database)
docker logs homelab-backend-1
docker logs homelab-frontend-1
docker compose restart frontend

# database
docker exec -it homelab-db-1 psql -U skander -d calcdb
  \dt                           # list tables
  SELECT * FROM history;        # see all calculations
  \q                            # exit

# test api
curl http://localhost/api/health
curl -X POST http://localhost/api/add \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 5}'

# check app is reachable
curl http://homelab.skander.cc/api/health
curl localhost:80               # run on EC2 to verify nginx is up

# check DNS points to correct IP
nslookup homelab.skander.cc
curl ifconfig.me                # run on EC2 — should match nslookup result

# check GitHub runner status on EC2
systemctl status actions.runner.*
journalctl -u actions.runner.* -n 50   # runner logs
sudo systemctl restart actions.runner.Skanderba8-homelab.ec2-runner.service
```

---

## debugging checklist

If the app isn't loading at homelab.skander.cc, check in this order:

**1. Are containers running?**
```bash
docker ps
# all 3 should show as Up: homelab-frontend-1, homelab-backend-1, homelab-db-1
```

**2. Is nginx responding locally?**
```bash
curl localhost:80
# should return your index.html
```

**3. Does DNS resolve to the right IP?**
```bash
nslookup homelab.skander.cc     # check what IP domain resolves to
curl ifconfig.me                # run on EC2 — get its actual public IP
# both should match — if not, run terraform apply to update Cloudflare record
```

**4. Is the browser forcing HTTPS?**
Try `http://homelab.skander.cc` explicitly — the app only runs on HTTP (port 80), not HTTPS.

**5. Are CI/CD jobs running on the right runner?**
Check GitHub repo → Actions → latest run → look for `Runner name` in the logs.
Should say `ec2-runner`, not `skander-VirtualBox` or any local machine name.
If wrong, go to Settings → Actions → Runners and remove the stale runner.

**6. Did git pull actually update the files?**
```bash
git log --oneline -3            # check latest commit hash
git show HEAD --stat            # see which files changed in last commit
cat index.html                  # verify file content matches what you committed
```

If `git pull` says "Already up to date" but files don't match GitHub, the runner may be on the wrong machine.

---

## issues encountered and how they were fixed

**App not loading despite containers being up**
DNS was pointing to the old EC2 IP after a destroy/apply. Fixed by running `terraform apply` which updated the Cloudflare A record automatically.

**CI/CD running on local VM instead of EC2**
Had two self-hosted runners registered. GitHub picked the local one. Fixed by removing the old runner from GitHub repo → Settings → Actions → Runners.

**git pull says "Already up to date" but files didn't update**
The workflow was running on the local VM runner (see above), not EC2. Files were up to date on the local machine but EC2 never got the pull.

**Port 80 already in use**
Old frontend container still running when trying to start a new one. Fixed with `docker compose down` then `docker compose up -d --build`.

**Docker build cached old files**
`docker compose up --build` uses cache by default. If a file change isn't being picked up, force a clean build:
```bash
docker compose up -d --build --no-cache
```

---

## things learned

**Docker**
- Dockerfile builds a single reusable image. Image = blueprint, container = running instance.
- Docker Compose orchestrates multiple containers. Each service gets its own container.
- `expose` makes a port internal only. `ports` maps it to the host (public).
- Containers find each other by service name — Docker has internal DNS that resolves `backend`, `db` etc to the right container IP automatically.
- Named volumes persist data outside containers. `docker compose down -v` deletes them — useful for resetting state.

**Networking**
- nginx as a reverse proxy means one public port handles everything. `/api/*` gets forwarded internally to FastAPI.
- CORS issues happen when a browser calls a different origin. Two fixes: CORS middleware in FastAPI (quick fix), and routing all calls through nginx on the same origin (proper fix).

**Database**
- `depends_on` only waits for the container to start, not for postgres to be ready to accept connections.
- Health checks (`pg_isready`) fix this — Docker marks the container healthy only when postgres actually responds.
- `condition: service_healthy` makes the backend wait for that signal before starting.
- First boot initializes postgres with credentials from environment variables. If a volume exists from a previous run with different credentials, postgres ignores the new ones — `down -v` wipes the volume and forces re-initialization.

**CI/CD**
- GitHub Actions reads `.github/workflows/deploy.yml` on every push to main.
- Self-hosted runner = your server polls GitHub, picks up jobs, runs them locally.
- No open port needed — outbound connection from server to GitHub, not the other way around.
- Multiple runners with the same label causes jobs to go to the wrong machine — keep only one runner registered at a time.
- Runner is installed as a systemd service so it survives EC2 reboots.