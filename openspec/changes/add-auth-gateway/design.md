# Design

## Context

- The stack runs as one Coolify docker-compose resource on a Raspberry Pi 4 (`DEPLOY.md`).
- Public traffic arrives through a Cloudflare Zero Trust tunnel rule, `avalon.blu3berry.com → http://localhost:48080`. It never passes through Coolify's own Traefik proxy, which owns host ports 80/443/8000.
- avalon-spring reads the caller from `@RequestHeader("Avalon-Header-Logged-In-User-Username")` in its controllers and does no token checking of its own.
- ForwardAuth (`ForwardAuth/app.py`) is a Flask app that is built and running in compose but is never routed to:
  - `/auth` returns a bare 200 with no identity header.
  - It returns 403 on a missing or expired token.
  - It raises an unhandled exception (500) on a malformed one.
  - It signs tokens with the literal key `"secret"`, using a custom `expire` claim rather than the standard `exp`.
- The repo already contains Traefik `forwardAuth` manifests for the earlier Kubernetes deployment (`helm/forwardauth/templates/middleware.yaml`), and k3s, the planned next step in `STRATEGY.md`, ships Traefik as its default ingress.

See `proposal.md` for motivation and `specs/` for the required behaviour.

## Goals / Non-Goals

**Goals:**
- Make every spec scenario in `api-gateway` and `user-auth` true on the Pi deployment, without touching avalon-spring.
- Keep the gateway config close enough to Traefik's Kubernetes CRDs that the k3s step can translate it directly.
- Make rollback a single revert-and-redeploy, with no Cloudflare change in either direction.

**Non-Goals:**
- Stronger password hashing. ForwardAuth uses PBKDF2 with 1000 iterations; migrating stored hashes is its own change.
- Replacing Flask's built-in server with gunicorn.
- Rate limiting login.
- Refresh tokens.
- Exposing Swagger publicly. It falls under the protected catch-all.
- Routing the email service through the gateway.
- Updating the legacy AKS workflows or the `helm/` charts.
- Avalon-mobile changes (production base URL, `forwardauth-api.yaml` 403→401). Those are a follow-up in that repo.

## Decisions

### Traefik as a dedicated compose service, file provider only
Add a `gateway` service running a pinned Traefik v3 image. It gets static config from `traefik/compose/traefik.yml` and routers, middlewares and services from `traefik/compose/dynamic.yml`, both via the **file provider**. No Docker socket is mounted.

- *Why Traefik over Caddy or nginx:* the owner already knows Traefik, and the `forwardAuth` + `authResponseHeaders` model maps one-to-one onto the k3s `Middleware` CRD already in `helm/`. Caddy's `forward_auth` is shorter but would be thrown away at the k3s step.
- *Why not reuse Coolify's Traefik:* the tunnel bypasses it, and configuring it means Coolify-specific labels that disappear with Coolify.
- *Why no Docker provider:* mounting `/var/run/docker.sock` gives the gateway root-equivalent access to the Pi for no benefit, since there are only two fixed upstreams.

### Gateway takes over host port 48080
`gateway` publishes `48080:80`, and `game` and `forwardauth` drop their `ports:` entries. The tunnel rule stays `localhost:48080`, so cut-over and rollback need no Cloudflare edit. This also closes `forwardauth`'s current `5000:5000` host exposure.

### Router layout

| Router | Rule | Middlewares | Service |
|---|---|---|---|
| `auth-public` | `Method(POST) && (Path(/login) \|\| Path(/register))` | `strip-identity` | `forwardauth` (`http://forwardauth:5000`) |
| `health` | `Method(GET) && Path(/)` | `strip-identity` | `game` (`http://game:8080`) |
| `protected` | `PathPrefix(/)` | `strip-identity`, `require-auth` | `game` |

- The rules above are shown in short form. In the dynamic config each `Method`/`Path` argument is a backtick-quoted string, e.g. ``Path(`/login`)``.
- Explicit `priority` values (auth-public 100, health 90, protected 1) make the precedence independent of rule length.
- `strip-identity` is a `headers` middleware with `customRequestHeaders: {Avalon-Header-Logged-In-User-Username: ""}`. In Traefik an empty value deletes the header.
- `require-auth` is `forwardAuth` with `address: http://forwardauth:5000/auth` and `authResponseHeaders: [Avalon-Header-Logged-In-User-Username]`. Traefik replaces the request header with the auth response's value, so the strip on protected routes is defence in depth rather than the only guard.
- On a non-2xx auth response Traefik returns that response to the client unchanged, which gives the spec's 401 pass-through for free.

### ForwardAuth fixes stay minimal and compatible
- **Signing key:** read `JWT_SECRET` from the environment at import. If it is missing or empty, exit with a message naming the variable. Compose also declares it as `${JWT_SECRET:?set in Coolify env}`, so a missing value fails at deploy time, not at first request. That's the same pattern as `EMAIL_SECRET_KEY`.
- **Token format:** keep the custom `expire` claim and HS256, so the token shape clients receive is unchanged.
  - Decode inside `try/except jwt.InvalidTokenError`.
  - A missing `expire` claim, a wrong signature, malformed input, a non-`Bearer ` scheme or a past expiry all return 401 with a JSON `message` body.
  - *Alternative considered:* switching to the standard `exp` claim so PyJWT checks expiry itself. That's cleaner, but it changes the token payload for no user-visible gain. Leave it for the hashing/token-hardening change.
- **Identity header:** `/auth` sets `Avalon-Header-Logged-In-User-Username` from the token's `username` claim.
- **Login errors:** replace `Response({...})` with JSON responses and keep the existing 404 and 403 codes. Avalon-mobile's auth spec and its "a 401 from `/login` means wrong password" carve-out depend on those codes not moving.

### Tests
- **ForwardAuth unit tests** use pytest with Flask's test client and `mongomock` in place of the Mongo client. They cover every `user-auth` scenario, live in `ForwardAuth/tests/`, and take their dependencies from a new `ForwardAuth/requirements-dev.txt`, so the runtime image stays the same.
- **Gateway behaviour** is checked by `tests/gateway_smoke.sh`, a curl script taking a base URL. It walks the `api-gateway` scenarios against a running stack: local `docker compose up`, the Pi on the LAN, or the public hostname. Traefik config has no meaningful unit-test seam, so a black-box smoke test is the honest check.

## Risks / Trade-offs

- **The gateway is a new single point of failure for the whole public API.** → It's one small container with static config. Rollback is reverting the merge commit; Coolify redeploys and `game` re-publishes 48080.
- **Every existing session is invalidated by the new signing key.** → Acceptable for a playground. The legacy and new apps both fall back to the login screen; it's called out in the proposal.
- **Deploying before `JWT_SECRET` is set fails the whole compose deploy, not just ForwardAuth.** → Setting it in Coolify is a user-gate task before merge, and `DEPLOY.md` Step 3 lists it as required.
- **Coolify may inject its own proxy labels into compose services.** → Labels are inert for a file-provider-only Traefik, and Coolify's proxy has no domain assigned to these services, so it doesn't route them.
- **Pi RAM**: Traefik adds roughly 30–60 MB. → Check against the `STRATEGY.md` "~2GB free" line in the verify step.
- **`/auth` is called on every protected request, including the mobile app's 2-second game polling.** ForwardAuth verifies the JWT without a database lookup, so the per-request cost is CPU-only. → Watch latency in the smoke test, and revisit only if polling feels slow.

## Migration Plan

1. `[USER-GATE]` Add `JWT_SECRET` (`openssl rand -base64 48`) to the Coolify resource's environment.
2. Merge. Coolify redeploys: `gateway` binds 48080, while `game` and `forwardauth` no longer publish ports.
3. Run `tests/gateway_smoke.sh https://avalon.blu3berry.com` and check Pi memory in the Coolify dashboard.
4. **Rollback:** revert the merge commit and push. The tunnel is untouched either way. `JWT_SECRET` can stay set; the old code ignores it.
