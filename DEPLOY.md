# Deploying Avalon to Coolify (Raspberry Pi)

Runbook for deploying the whole stack (game + email + auth + mongo) to the
8GB Raspberry Pi running Coolify. Everything builds natively on the Pi — no
registry, no CI publish step, no secrets in git.

## What gets deployed

| Service | Source | Host port | Public via tunnel | Purpose |
|---|---|---|---|---|
| `game` | `avalon-spring/` submodule (Spring Boot) | 48080 | `avalon.blu3berry.com` | Game REST API |
| `email` | `EmailHandlerAvalon/` (Django) | 48081 | optional `avalon-email.blu3berry.com` | Password-reset emails |
| `forwardauth` | `ForwardAuth/` (Flask) | 5000 | no (internal) | JWT auth check |
| `mongo` | `mongo:4.4.18` image | — (internal) | no | Database |

Public exposure is via your **Cloudflare Zero Trust tunnel**, not
Coolify/Traefik: a tunnel ingress rule maps `avalon.blu3berry.com` →
`http://localhost:48080`. Host ports follow your `<n>8080` convention
(gyros 18080, sunny 28080, homar 38080 → avalon 48080).

Mongo and forwardauth are **not** published to the host or the tunnel.
Services reach each other over the compose network by name (`mongo`, `game`,
`forwardauth`).

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
| `EMAIL_ALLOWED_HOST` | `*` for a playground, or `avalon-email.blu3berry.com` if you tunnel it | no (defaults to `localhost`) |
| `APP_PASSWORD_EMAIL` | Gmail [app password](https://support.google.com/accounts/answer/185833) | no — only for sending reset emails |
| `EMAIL_ADDRESS` | sender address | no (has a default) |

Generate a secret key:
```bash
openssl rand -base64 48
```

> `EMAIL_ALLOWED_HOST=*` lets Django accept any Host header — fine for a LAN
> playground, tighten it once you have a real domain.

## Step 4 — Expose the game via the Cloudflare tunnel

The compose publishes host ports; the Cloudflare tunnel maps a public hostname
to one. After deploy:

**Local smoke test (no tunnel):** `http://<pi-ip>:48080/` on the LAN.

**Public (your normal pattern):** add a tunnel ingress rule.
1. Cloudflare Zero Trust → **Networks → Tunnels** → your tunnel → **Public
   Hostnames** → **Add a public hostname**.
2. Subdomain: `avalon`, Domain: `blu3berry.com`.
3. Service type: **HTTP**, URL: `localhost:48080`.
4. Save. `https://avalon.blu3berry.com` now front-ends the game API (Cloudflare
   terminates TLS; forwards plain HTTP to `localhost:48080`).

Optional — repeat for the email service (`avalon-email` → `localhost:48081`)
only if the password-reset flow needs to be publicly reachable. Set
`EMAIL_ALLOWED_HOST=avalon-email.blu3berry.com` to match.

## Step 5 — Deploy

Click **Deploy**. Watch the build logs.

- First build is **slow**: Gradle compiles Spring on the Pi (several minutes)
  plus pip installs for the two Python services. Later deploys are cached.
- Expect the build order to resolve `mongo` first, then the app services.

## Step 6 — Verify

1. **Game is up** — hit the root endpoint (locally, then via tunnel):
   ```bash
   curl http://<pi-ip>:48080/          # LAN
   curl https://avalon.blu3berry.com/  # through the tunnel
   # → Im running! :)
   ```
   Or open Swagger UI: `https://avalon.blu3berry.com/swagger-ui.html`

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
Something on the host already owns 48080/48081/5000. Remap that service's host
port in `docker-compose.yml` and update the matching tunnel ingress rule. Host
port 8000 is intentionally avoided — Coolify's dashboard owns it.

### `avalon.blu3berry.com` 502 / not reachable
Tunnel rule points at a port nothing is listening on. Confirm the game
container is up and answering on the LAN (`curl http://<pi-ip>:48080/`) first,
then that the ingress rule targets `localhost:48080`.
