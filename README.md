# homelab — devops learning project

A simple calculator app built to learn and practice core DevOps concepts hands-on. Every piece of this stack was added deliberately as a learning exercise.

---

## what this project is

A calculator API with a frontend and a database, running on a local VM, fully containerized and automatically deployed via CI/CD. The app itself is simple by design — the point is the infrastructure around it.

---

## stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI (Python) | Simple, fast to write, easy to test with curl |
| Frontend | HTML + nginx | Minimal UI to interact with the API |
| Database | PostgreSQL | Industry standard relational db |
| Containers | Docker + Docker Compose | Reproducible, isolated environments |
| CI/CD | GitHub Actions (self-hosted) | Automated deployment on every push |
| VM | VirtualBox (Linux Mint) | Local environment to simulate a real server |

---

## project structure

```
homelab/
├── main.py                        # FastAPI app — all backend logic
├── Dockerfile                     # recipe to build the backend container
├── docker-compose.yml             # orchestrates all 3 containers
├── nginx.conf                     # nginx routing — serves frontend, proxies API
├── index.html                     # frontend UI
├── .gitignore                     # keeps secrets and junk out of git
├── actions-runner/                # self-hosted GitHub Actions runner (gitignored)
└── .github/
    └── workflows/
        └── deploy.yml             # CI/CD pipeline definition
```

---

## architecture

```
Your Browser
     │
     │ http://VM_IP:8080 (only public port)
     ▼
┌─────────────────────────────────────────────────┐
│                  VirtualBox VM                  │
│                                                 │
│  ┌──────────────────────────────────────────┐   │
│  │           Docker Network                 │   │
│  │                                          │   │
│  │  ┌────────────┐                          │   │
│  │  │  frontend  │ nginx — port 8080        │   │
│  │  │            │                          │   │
│  │  │ /          │→ serves index.html       │   │
│  │  │ /api/*     │→ proxies to backend:8000 │   │
│  │  └─────┬──────┘                          │   │
│  │        │ internal                        │   │
│  │        ▼ http://backend:8000             │   │
│  │  ┌────────────┐                          │   │
│  │  │  backend   │ fastapi — not exposed    │   │
│  │  │            │                          │   │
│  │  │ main.py    │→ handles calculations    │   │
│  │  │            │→ saves to db             │   │
│  │  └─────┬──────┘                          │   │
│  │        │ internal                        │   │
│  │        ▼ http://db:5432                  │   │
│  │  ┌────────────┐                          │   │
│  │  │     db     │ postgres — not exposed   │   │
│  │  │  calcdb    │→ stores history table    │   │
│  │  └────────────┘                          │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

Only one port is exposed to the outside. The backend and database are invisible to the internet — only reachable internally by container name.

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
| GET | `/api/history` | last 20 calculations from db |
| DELETE | `/api/history` | clear all history |

All POST endpoints accept `{"a": 10, "b": 5}`.

---

## how to run

```bash
# clone the repo
git clone https://github.com/YOUR_USERNAME/homelab
cd homelab

# start all containers
docker compose up -d --build

# verify everything is running
docker ps

# test the api
curl http://localhost:8080/api/health
```

---

## ci/cd pipeline

Every push to `main` triggers an automatic deployment.

```
git push origin main
        │
        ▼
GitHub detects push → triggers deploy.yml
        │
        ▼
self-hosted runner on VM picks up the job
        │
        ├── pulls latest code
        ├── docker compose down
        └── docker compose up -d --build
```

The runner is a process running permanently on the VM. It polls GitHub for jobs — no open port needed, the VM reaches out to GitHub, not the other way around.

---

## what i learned

**Docker**
- A Dockerfile builds a single image for a custom app
- Docker Compose orchestrates multiple containers together
- Containers talk to each other by service name (internal DNS)
- `expose` makes a port internal only — `ports` makes it public
- Volumes persist data outside containers so it survives restarts
- `down -v` wipes volumes — useful for resetting db state

**Networking**
- Only expose what needs to be public (in this case, just nginx on 8080)
- nginx acts as a reverse proxy — one public entry point that routes traffic internally
- Browser API calls go through nginx (`/api/*`) instead of hitting the backend directly

**Database**
- postgres runs as its own container with a named volume for persistence
- Health checks tell Docker when postgres is actually ready (not just started)
- `depends_on: condition: service_healthy` makes backend wait for db to be ready
- `psycopg2` connects Python to postgres — uses `%s` placeholders, not `?`

**CI/CD**
- GitHub Actions reads `.github/workflows/deploy.yml` on every push
- `runs-on: self-hosted` uses your own machine instead of GitHub's servers
- Self-hosted runner = your VM connects to GitHub and waits for jobs
- No open ports needed — the VM polls GitHub outbound

---

## best practices applied

- secrets stay out of code — db credentials live in `docker-compose.yml` environment vars, never hardcoded
- backend is not exposed publicly — only nginx faces the outside
- database is not exposed publicly — only backend can reach it
- `.gitignore` covers credentials, venv, pycache, runner binaries
- one command to start everything — `docker compose up -d --build`
- health checks ensure startup order is correct, not just fast
- data persists across container restarts via named volumes
- CI/CD means no manual SSH deploys — push code, it ships

---

## useful commands

```bash
# container management
docker ps                          # see running containers
docker compose up -d --build       # start everything, rebuild images
docker compose down                # stop everything
docker compose down -v             # stop everything + wipe volumes
docker logs homelab-backend-1      # see backend logs
docker compose restart frontend    # restart one container

# database access
docker exec -it homelab-db-1 psql -U skander -d calcdb
  \dt                              # list tables
  SELECT * FROM history;           # see all calculations
  \q                               # exit

# test api
curl http://localhost:8080/api/health
curl -X POST http://localhost:8080/api/add \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 5}'
```