# Deploying Avalon to Coolify (Raspberry Pi)

Runbook for deploying the whole stack (game + email + auth + mongo) to the
8GB Raspberry Pi running Coolify. Everything builds natively on the Pi — no
registry, no CI publish step, no secrets in git.

## What gets deployed

| Service | Source | Host port | Public via tunnel | Purpose |
|---|---|---|---|---|
| `gateway` | `traefik:v3.7.14` image, config in `traefik/compose/` | 48080 | `avalon.blu3berry.com` | Public entry point: routes login/register, authenticates everything else |
| `game` | `avalon-spring/` submodule (Spring Boot) | — (internal) | via `gateway` | Game REST API |
| `email` | `EmailHandlerAvalon/` (Django) | 48081 | optional `avalon-email.blu3berry.com` | Password-reset emails |
| `forwardauth` | `ForwardAuth/` (Flask) | — (internal) | `/login`, `/register` via `gateway` | Issues and checks JWTs |
| `mongo` | `mongo:4.4.18` image | — (internal) | no | Database |

Public exposure is via your **Cloudflare Zero Trust tunnel**, not
Coolify/Traefik: a tunnel ingress rule maps `avalon.blu3berry.com` →
`http://localhost:48080`. Host ports follow your `<n>8080` convention
(gyros 18080, sunny 28080, homar 38080 → avalon 48080).

Only `gateway` (and optionally `email`) is published to the host. `game`,
`forwardauth` and `mongo` are reachable only over the compose network by name.
The gateway sends `POST /login` and `POST /register` to forwardauth, keeps
`GET /` public as a health check, and checks every other request against
forwardauth `/auth`. On success it sets `Avalon-Header-Logged-In-User-Username`,
the header avalon-spring trusts as the caller, and it always drops any value a
client sent for it.

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
| `JWT_SECRET` | a long random string (login token signing key) | **yes** — deploy fails without it. Changing it logs every user out |
| `EMAIL_SECRET_KEY` | a long random string (Django secret) | **yes** — deploy fails without it |
| `EMAIL_ALLOWED_HOST` | `*` for a playground, or `avalon-email.blu3berry.com` if you tunnel it | no (defaults to `localhost`) |
| `APP_PASSWORD_EMAIL` | Gmail [app password](https://support.google.com/accounts/answer/185833) | no — only for sending reset emails |
| `EMAIL_ADDRESS` | sender address | no (has a default) |

Generate each secret key separately:
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
3. Service type: **HTTP**, URL: `localhost:48080` (the `gateway`, not the game
   service directly).
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
   Swagger UI is behind the gateway's auth now, so it needs a bearer token.

2. **Auth gateway works**: run the smoke test, which registers a throwaway
   user and walks every gateway rule:
   ```bash
   tests/gateway_smoke.sh https://avalon.blu3berry.com
   # → ALL PASS
   ```

3. **Mongo compatibility confirmed** — in Coolify, check the `mongo` container
   is running and not crash-looping. A stable mongo container = the Pi 4 CPU
   runs 4.4.18 correctly (no `SIGILL`).

4. **RAM headroom** (the strategy metric) — Coolify server dashboard shows
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
Something on the host already owns 48080/48081. Set `GATEWAY_PORT` /
`EMAIL_PORT` in the resource's environment to another host port and update the
matching tunnel ingress rule. The same variables let a second Coolify resource
deploy a branch next to production for testing, e.g. `GATEWAY_PORT=48090`,
`EMAIL_PORT=48091`. It gets its own mongo volume. Host
port 8000 is intentionally avoided — Coolify's dashboard owns it.

### `avalon.blu3berry.com` 502 / not reachable
Tunnel rule points at a port nothing is listening on. Confirm the `gateway`
and `game` containers are up and the gateway answers on the LAN
(`curl http://<pi-ip>:48080/`) first, then that the ingress rule targets
`localhost:48080`. A 502 from the gateway itself means `game` or `forwardauth`
is down. Check those containers' logs.

### 401 on every request after a deploy
Tokens are signed with `JWT_SECRET`. Tokens issued before the key was set or
changed are rejected, so log in again. If a fresh login also gets 401, check
that the `forwardauth` container is running and has `JWT_SECRET` set.
