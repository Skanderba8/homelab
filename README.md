# homelab

A calculator app built from scratch as a hands-on DevOps learning project. The app itself is intentionally simple — the point is everything around it: containers, networking, databases, secrets management, CI/CD, cloud deployment, image registries, HTTPS, and observability.

---

## what this is

A FastAPI backend with a frontend served by nginx and a PostgreSQL database, fully containerized with Docker Compose, deployed on AWS EC2, accessible at [homelab.skander.cc](https://homelab.skander.cc), and automatically deployed on every git push via GitHub Actions. HTTPS is handled by Traefik with automatic Let's Encrypt certificates. Metrics and logs are collected by Prometheus, Loki, and Grafana.

---

## stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI (Python) | Simple, fast to write, easy to curl-test |
| Frontend | HTML + nginx | Minimal UI, no framework needed |
| Database | PostgreSQL | Industry standard, runs great in Docker |
| Containers | Docker + Docker Compose | Reproducible, isolated environments |
| Reverse proxy | Traefik | Automatic TLS, routes traffic to correct container |
| TLS | Let's Encrypt via Traefik | Auto-provisioned and auto-renewed certs |
| Image Registry | AWS ECR | Private registry — images built in CI, pulled on EC2 |
| CI/CD | GitHub Actions (hosted runners) | Smart build — only rebuilds what changed, deploys on push |
| Server | AWS EC2 t3.micro | Real cloud server, free tier eligible |
| DNS | Cloudflare | homelab.skander.cc → EC2 IP |
| Metrics | Prometheus + cAdvisor | Per-container CPU, memory, network |
| Logs | Loki + Promtail | Container log aggregation |
| Dashboards | Grafana | Visualises metrics and logs at grafana.skander.cc |

---

## architecture

```
Browser
  │
  │ https://homelab.skander.cc (port 443)
  ▼
Cloudflare DNS → EC2 eu-west-3
  │
  ▼
┌─────────────────────────────────────────────┐
│              Docker network                 │
│                                             │
│  Traefik (ports 80 + 443, public)           │
│    port 80  → redirect to 443               │
│    port 443 → TLS termination               │
│    homelab.skander.cc  → frontend:80        │
│    grafana.skander.cc  → grafana:3000       │
│         │                                   │
│         ▼ internal HTTP                     │
│  nginx / frontend (port 80, internal)       │
│    /        → index.html                    │
│    /api/*   → proxy to backend:8000         │
│         │                                   │
│         ▼ internal                          │
│  fastapi backend (port 8000, internal)      │
│         │                                   │
│         ▼ internal                          │
│  postgres (port 5432, internal)             │
│  data persisted in Docker volume            │
│                                             │
│  prometheus (scrapes cadvisor)              │
│  cadvisor   (container metrics)             │
│  loki       (log storage)                   │
│  promtail   (ships container logs to loki)  │
│  grafana    (dashboards at grafana.skander.cc) │
└─────────────────────────────────────────────┘
```

Only ports 80 and 443 are exposed. Everything else is internal.

---

## project structure

```
homelab/
├── main.py                          # FastAPI app — all backend logic + postgres
├── backend.Dockerfile               # builds the backend container image
├── frontend.Dockerfile              # builds the frontend container image
├── docker-compose.yml               # orchestrates all services
├── nginx.conf                       # serves frontend, proxies /api/* to backend
├── index.html                       # frontend UI
├── prometheus.yml                   # prometheus scrape config
├── loki.yml                         # loki storage config
├── promtail.yml                     # promtail log shipping config
├── grafana/
│   └── provisioning/
│       ├── dashboards/
│       │   ├── dashboards.yml       # tells grafana where to find dashboard files
│       │   └── homelab.json         # auto-provisioned container dashboard
│       └── datasources/
│           └── datasources.yml      # auto-configures prometheus + loki on startup
├── .env                             # runtime secrets — GITIGNORED, never commit
├── .gitignore
└── .github/
    └── workflows/
        └── deploy.yml               # CI/CD pipeline
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
GRAFANA_PASSWORD=yourpassword
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

Every push to `main` runs a `changes` job first to detect which files changed. Only affected services are built and deployed. Pushes that only touch infra config (compose, monitoring config) skip the image build entirely and just apply the config change on the server.

```
git push origin main
        │
        ▼
Job: changes (dorny/paths-filter)
  ├── backend changed? → build + push backend, pull backend on EC2
  ├── frontend changed? → build + push frontend, pull frontend on EC2
  └── neither changed? → deploy-infra: git pull + docker compose up -d only
```

This means a compose change (e.g. bumping a memory limit or a monitoring version) deploys in ~10 seconds with zero image pulling. An app code change builds only the affected image.

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

## https and routing

Traefik replaced direct nginx port exposure. It runs on ports 80 and 443, terminates TLS, and routes traffic to the correct container based on the `Host` header.

- `http://homelab.skander.cc` → Traefik redirects to HTTPS automatically
- `https://homelab.skander.cc` → Traefik forwards to frontend container
- `https://grafana.skander.cc` → Traefik forwards to Grafana container

Certificates are provisioned via ACME TLS challenge on first startup and stored in the `traefik-certs` Docker volume. Traefik auto-renews them before expiry. No manual cert management needed.

**Why Traefik and not certbot:** Traefik is a container-native reverse proxy — it discovers services automatically via Docker labels and handles cert lifecycle without cron jobs or manual renewal. Adding a new HTTPS service is just adding labels to a container.

---

## observability

Three components work together: cAdvisor exposes per-container metrics, Prometheus scrapes and stores them, and Grafana visualises them. Promtail ships all container logs to Loki, which Grafana also queries.

**Grafana is provisioned as code** — datasources and dashboards live in `grafana/provisioning/` and are loaded automatically on startup. Destroying and rebuilding the server restores the full dashboard with no manual steps.

The dashboard at `grafana.skander.cc` shows CPU usage, memory usage, network in/out, current memory per container, and container uptime. All panels use the `name` label to filter to `homelab-*` containers only.

**Memory limits** are set on every container to prevent the monitoring stack from starving the app on the t3.micro's 1GB RAM. A 512MB swapfile provides a safety net against OOM kills.

| Container | Limit |
|---|---|
| backend | 128MB |
| frontend | 32MB |
| db | 128MB |
| traefik | 64MB |
| grafana | 128MB |
| prometheus | 128MB |
| loki | 64MB |
| promtail | 64MB |
| cadvisor | 64MB |

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
# should show all services Up
```

**2. Check container logs for errors:**
```bash
docker compose logs --tail=50
docker logs homelab-backend-1
```

**3. Is Traefik routing correctly?**
```bash
docker logs homelab-traefik-1 2>&1 | tail -20
# look for certificate errors or routing mismatches
```

**4. Is the cert valid?**
```bash
curl -v https://homelab.skander.cc 2>&1 | grep -i cert
# should show Let's Encrypt issuer, not TRAEFIK DEFAULT CERT
```

**5. Is the backend reachable internally?**
```bash
docker compose exec frontend wget -qO- http://backend:8000/health
```

**6. Is nginx config valid?**
```bash
docker compose exec frontend nginx -t
```

**7. Does nginx correctly strip /api before forwarding?**
```nginx
location /api/ {
    proxy_pass http://backend:8000/;   # trailing slash strips /api prefix
}
```

**8. Is the .env file present on EC2?**
```bash
cat /home/ubuntu/homelab/.env
ls -la /home/ubuntu/homelab/.env   # should show -rw------- (mode 600)
```

**9. Does DNS resolve to the right IP?**
```bash
nslookup homelab.skander.cc
curl ifconfig.me   # run on EC2 — should match
```

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

# check memory usage
free -h
docker stats --no-stream

# check memory limits applied
docker inspect homelab-grafana-1 | grep -i memory

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
Multiple issues stacked: `appleboy/ssh-action` fingerprint verification kept failing — abandoned in favour of plain `ssh` command. `printf '%s'` strips trailing newline causing `error in libcrypto` — fixed with `echo | tr -d '\r'`. `SSH_USER` secret was set to `skander` instead of `ubuntu` — root cause, found via `/var/log/auth.log`.

**ECR image not found on first deploy**
Fresh ECR registry is empty — `docker compose pull` fails. Ansible now checks image count before starting containers and skips on first provision. First real deploy happens via GitHub Actions after pushing a commit.

**Traefik serving self-signed cert instead of Let's Encrypt**
Traefik v3.0 requires Docker API 1.40+ but the EC2 Docker daemon exposed API 1.24. Traefik couldn't discover containers, never triggered ACME, and fell back to its default self-signed cert. Fixed by downgrading to `traefik:v2.11` which supports older Docker APIs.

**Loki crashing with gRPC deadline exceeded**
`grafana/loki:latest` pulled a version that fails on a single-node setup without explicit config. Fixed by pinning to `grafana/loki:2.9.0` and providing a minimal `loki.yml` with `inmemory` ring store and filesystem storage.

**Grafana dashboard showing no data after provisioning**
Dashboard JSON used `${DS_PROMETHEUS}` as the datasource UID but Grafana assigned it a fixed UID (`PBFA97CFB590B2093`) at startup. Fixed by replacing the placeholder with the actual UID in `homelab.json`.

**High memory pressure on t3.micro**
Monitoring stack (Grafana 142MB + Prometheus 85MB + Loki 64MB + cAdvisor 63MB) consumed more RAM than the app itself. Fixed by adding `mem_limit` to every container in compose and a 512MB swapfile to prevent hard OOM kills.

**Deploys taking 5 minutes on every push**
`docker compose pull` was pulling all 9 images on every deploy, including infrastructure images that never change. Fixed with `dorny/paths-filter` in GitHub Actions — only app images are pulled when their source files change. Infra-only commits skip the build entirely.

---

## things learned

**Docker**
- Dockerfile builds an image. Image = blueprint, container = running instance.
- `expose` makes a port internal only. `ports` maps it to the host.
- Containers find each other by service name — Docker's internal DNS resolves `backend`, `db` etc.
- Named volumes persist data outside containers. `down -v` deletes them — resets all state.
- `mem_limit` caps how much RAM a container can use — without it a runaway process can OOM the whole host.

**Traefik**
- Discovers containers automatically via Docker socket and labels — no static config files needed.
- `traefik.enable=true` + `Host()` rule + `certresolver` label = automatic HTTPS for any service.
- Falls back to a self-signed cert if ACME fails — check logs for the actual error before assuming cert issuance worked.
- Version matters: v3.0 requires Docker API 1.40+. Check `docker version` before picking a Traefik version.

**Let's Encrypt**
- TLS challenge requires port 443 to be reachable before the cert is issued.
- Rate limit: 5 real certs per domain per week. Use staging CA while debugging.
- Certs are stored in a Docker volume — wipe the volume to force re-issuance.

**ECR + IAM**
- EC2 instances authenticate to ECR via IAM instance profiles — no credentials stored on the server.
- IAM has three separate resources: the role (what), the policy attachment (permissions), and the instance profile (the EC2 wrapper).
- `force_delete = true` on ECR is necessary for destroy/rebuild cycles.

**CI/CD architecture**
- Build once in CI, run anywhere — EC2 should never compile code.
- Every image gets two tags: `latest` (what EC2 pulls) and the git SHA (permanent record).
- `dorny/paths-filter` makes CI aware of what actually changed — avoids unnecessary builds and pulls.
- `needs:` in GitHub Actions ensures deploy never runs if build failed.
- Separate `deploy-infra` job handles config-only changes without touching images.

**Observability**
- cAdvisor exposes container metrics. Prometheus scrapes and stores them. Grafana visualises.
- Loki stores logs. Promtail ships them. Same Grafana instance queries both.
- Provision datasources and dashboards as code — never configure Grafana manually.
- The `name` label in cAdvisor metrics identifies containers. Filter with `name=~"homelab-.+"` to exclude host cgroups.
- `latest` image tags for monitoring tools can pull broken versions. Pin to explicit versions.

**Debugging SSH**
- `/var/log/auth.log` on the server shows exactly why SSH connections are accepted or rejected.
- `ssh-keygen -y -f keyfile` derives the public key from a private key — use to verify they match.
- `cat -A` shows line endings — every line in an SSH key must end with `$` (Unix newline).

**Ubuntu 24.04 quirks**
- `awscli` removed from apt — use pip3 with `--break-system-packages`.
- Python packages require `--break-system-packages` flag for system-wide pip installs.

**Secrets management**
- Never hardcode secrets in files that get committed.
- Docker Compose automatically loads `.env` from the same directory.
- Postgres stores its password in a volume. Changing the env var after first boot has no effect — use `ALTER USER` inside the container.

**AWS**
- Security groups are stateful firewalls — ingress and egress rules defined separately.
- `expose` in docker-compose = internal only. Security group controls what reaches the host.
- AMIs are region-specific.

**Cloudflare**
- Terraform's Cloudflare provider updates DNS automatically when EC2 IP changes.
- `proxied = false` = DNS only. Set to `true` later for DDoS protection and HTTPS termination.
- TTL 60 = DNS records update within 60 seconds.

---

## what's next

- **Secrets management** — move secrets from `vars.yml`/`.env` into AWS Secrets Manager. EC2 fetches them at runtime instead of Ansible writing them at deploy time.
- **Alerting** — Grafana alerts to email or Slack when a container is down or memory exceeds 80%.
- **Uptime monitoring** — HTTP health check hitting `/api/health` every minute with alerting on failure.
- **Multi-environment** — `staging` branch + separate Terraform workspace for testing infra changes before prod.
- **Terraform remote state** — move `terraform.tfstate` to S3 so it's not sitting on a local machine