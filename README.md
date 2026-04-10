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

---

## running locally

```bash
git clone https://github.com/YOUR_USERNAME/homelab
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