# Deploying Avalon to Coolify (Raspberry Pi)

Runbook for deploying the whole stack (game + email + auth + mongo) to the
8GB Raspberry Pi running Coolify. Everything builds natively on the Pi — no
registry, no CI publish step, no secrets in git.

## What gets deployed

| Service | Source | Host port | Purpose |
|---|---|---|---|
| `game` | `avalon-spring/` submodule (Spring Boot) | 8080 | Game REST API |
| `email` | `EmailHandlerAvalon/` (Django) | 8001 | Password-reset emails |
| `forwardauth` | `ForwardAuth/` (Flask) | 5000 | JWT auth check |
| `mongo` | `mongo:4.4.18` image | — (internal) | Database |

Mongo is **not** published to the host — only the three app services are
reachable. Services talk to each other over Coolify's compose network by
name (`mongo`, `game`).

## Prerequisites

- Coolify running and reachable (you already have this).
- The Pi is a **Pi 4** → mongo is pinned to `4.4.18` (last release its CPU can
  run). If mongo starts and stays up after deploy, that empirically confirms
  the pin is correct — no need to check `uname` separately.

## Step 1 — Add the resource

1. Coolify → pick (or create) a **Project** → **Add New Resource**.
2. Under **Git Based**, choose **Public Repository**.
3. Repo URL: `https://github.com/blu3berry-why/Avalon-Boardgame-with-Kubernetes`
4. Branch: `main`
5. **Build Pack: Docker Compose**
6. Compose file location: `docker-compose.yml` (repo root — leave default)

## Step 2 — Enable submodules (critical)

The `game` service builds from the `avalon-spring/` **git submodule**. If
Coolify clones without submodules, that directory comes up empty and the game
build fails ("no Dockerfile" / empty context).

- In the resource's **Configuration → General** (or **Advanced**), find the
  git submodule / recursive-clone option and enable it.
- If you can't find the toggle in your Coolify version, see
  [Troubleshooting → empty submodule](#empty-submodule) for the fallback.

## Step 3 — Set environment variables

Resource → **Environment Variables** → add:

| Key | Value | Required |
|---|---|---|
| `EMAIL_SECRET_KEY` | a long random string (Django secret) | **yes** — deploy fails without it |
| `EMAIL_ALLOWED_HOST` | `*` for a playground, or the email service's domain | no (defaults to `localhost`) |
| `APP_PASSWORD_EMAIL` | Gmail [app password](https://support.google.com/accounts/answer/185833) | no — only for sending reset emails |
| `EMAIL_ADDRESS` | sender address | no (has a default) |

Generate a secret key:
```bash
openssl rand -base64 48
```

> `EMAIL_ALLOWED_HOST=*` lets Django accept any Host header — fine for a LAN
> playground, tighten it once you have a real domain.

## Step 4 — Choose how you reach the services

**Option A — LAN IP + host ports (simplest, no domain needed).**
The compose publishes host ports, so after deploy the services answer on the
Pi's LAN address:
- Game: `http://<pi-ip>:8080/`
- Email: `http://<pi-ip>:8001/`
- Auth: `http://<pi-ip>:5000/`

Nothing extra to configure.

**Option B — Coolify domain + HTTPS (proper).**
In the resource, assign a domain (FQDN pointing at the Pi) to the `game`
service. Coolify wires Traefik + Let's Encrypt automatically. Do this once the
LAN deploy is green.

## Step 5 — Deploy

Click **Deploy**. Watch the build logs.

- First build is **slow**: Gradle compiles Spring on the Pi (several minutes)
  plus pip installs for the two Python services. Later deploys are cached.
- Expect the build order to resolve `mongo` first, then the app services.

## Step 6 — Verify

1. **Game is up** — hit the root endpoint:
   ```bash
   curl http://<pi-ip>:8080/
   # → Im running! :)
   ```
   Or open Swagger UI: `http://<pi-ip>:8080/swagger-ui.html`

2. **Mongo compatibility confirmed** — in Coolify, check the `mongo` container
   is running and not crash-looping. A stable mongo container = the Pi 4 CPU
   runs 4.4.18 correctly (no `SIGILL`).

3. **RAM headroom** (the strategy metric) — Coolify server dashboard shows
   memory. Below ~2GB free is the "stop adding, start trimming" line.

## Step 7 — Shipping updates later

- **Game backend**: merge changes to `Avalon-3-Spring` master → bump the
  submodule pointer here (`cd avalon-spring && git checkout master && git pull`,
  then commit the pointer in this repo) → Coolify redeploys on push to `main`.
  Cut a release with the release-please PR in the backend repo.
- **Email / auth / compose**: edit here, push to `main`, Coolify redeploys.

## Troubleshooting

### <a name="empty-submodule"></a>Game build fails / `avalon-spring` empty
Coolify didn't init the submodule. Options, cheapest first:
1. Find and enable the submodule/recursive-clone toggle (Step 2).
2. Fallback — publish the Spring image to Docker Hub (a buildx workflow in the
   backend repo) and change the `game` service in `docker-compose.yml` from
   `build:` to `image: <your-dockerhub>/avalon-spring:latest`. More setup, but
   removes the submodule dependency entirely.

### `Invalid mongo configuration, either uri or host/port...`
The game service must set `SPRING_DATA_MONGODB_HOST` only — **not** a full
`SPRING_DATA_MONGODB_URI` (the app's `application.properties` already sets
port + database, and Spring Boot 2.7 rejects having both). The committed
compose is already correct; only relevant if you hand-edit it.

### Django "Invalid HTTP_HOST header"
`EMAIL_ALLOWED_HOST` doesn't match how you're reaching it. Set it to `*` (LAN)
or the exact domain (Option B).

### Port bind error on deploy
Something on the host already owns 8080 or 5000. Remap that service's host
port in `docker-compose.yml` (e.g. `8090:8080`). Port 8000 is intentionally
avoided — Coolify's dashboard owns it.
