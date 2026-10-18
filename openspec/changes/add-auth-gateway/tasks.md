# Tasks

## 1. ForwardAuth: configured signing key and token validation

- [x] 1.1 Add `ForwardAuth/requirements-dev.txt` (`pytest`, `mongomock`, plus `-r requirements.txt`) and a `ForwardAuth/tests/conftest.py`. It sets `JWT_SECRET`, swaps the module's Mongo db for a `mongomock` one, and yields a Flask test client. Verify `python -m pytest ForwardAuth/tests` collects and runs (0 tests is fine at this step).
- [x] 1.2 Read the signing key from `JWT_SECRET` at import. Exit with a message naming `JWT_SECRET` when it is missing or empty. Use it in both `jwt.encode` and `jwt.decode`. Verify with a test that importing the app without `JWT_SECRET` raises/exits, and a test that a token signed with `"secret"` is rejected by `/auth` with 401.
- [x] 1.3 Rewrite `/auth`:
  - 200 with `Avalon-Header-Logged-In-User-Username: <username>` for a valid token.
  - 401 with a JSON `message` body for a missing header, a non-`Bearer ` scheme, a malformed token, a bad signature, a missing `expire` claim or a past `expire`.
  - Catch `jwt.InvalidTokenError`; nothing may return a 5xx.
  - Verify with one pytest per `user-auth` "Token validation" scenario.
- [x] 1.4 Return JSON `{"message": ...}` bodies with `Content-Type: application/json` from `/login` (404 unknown user, 403 wrong password), keeping the codes. Verify with pytest for both error scenarios plus the success scenario: `/login` returns `username` and a `token` that `/auth` accepts.
- [x] 1.5 Add pytest for `/register`: a new user gets 200, then `/login` succeeds; a duplicate gets 409 with a JSON `message`. Verify the whole `ForwardAuth/tests` suite passes.

## 2. Traefik gateway in compose

- [ ] 2.1 Add `traefik/compose/traefik.yml`: an `:80` entrypoint, the file provider pointing at `dynamic.yml`, no API/dashboard, access log to stdout. Verify `docker run --rm -v ./traefik/compose:/etc/traefik <pinned image> traefik --configFile=/etc/traefik/traefik.yml` starts without config errors.
- [ ] 2.2 Add `traefik/compose/dynamic.yml` with the `strip-identity` and `require-auth` middlewares, the `game`/`forwardauth` services, and the three routers with priorities exactly as in `design.md` → Router layout. Verify Traefik logs no router or middleware errors on startup.
- [ ] 2.3 Update `docker-compose.yml`:
  - Add a `gateway` service. Pin a Traefik v3 patch tag whose manifest includes `linux/arm64`, and confirm that with `docker manifest inspect`. It mounts `./traefik/compose` read-only, publishes `48080:80`, and has `depends_on: [game, forwardauth]`.
  - Remove the `ports:` from `game` and `forwardauth`.
  - Add `JWT_SECRET: ${JWT_SECRET:?set in Coolify env}` and `CONNECTION_STRING` (unchanged) to `forwardauth`.
  - Verify `JWT_SECRET=x docker compose config` succeeds and `docker compose config` without it fails naming `JWT_SECRET`.
- [ ] 2.4 Add `tests/gateway_smoke.sh <base-url>`. It covers each `api-gateway` scenario:
  - health without a token
  - register and login through the gateway
  - `POST /lobby/create` without a token → 401, and with a token → 2xx
  - an expired or garbage token → 401
  - forged identity without a token: `GET /tryheader` with `Avalon-Header-Logged-In-User-Username: bob` → 401, not an echo of `bob`
  - forged identity overwritten: `GET /tryheader` with a valid token plus `…: bob` echoes the token's user (`/tryheader` returns the identity the game service received, which makes it a more direct check than the lobby player list). Stripping on `GET /` is not observable from outside, because the game service ignores the header there; `dynamic.yml` covers it by applying `strip-identity` to every router.

  Run it against a local `JWT_SECRET=x docker compose up` (or the Pi LAN) and verify every check prints PASS.
- [ ] 2.5 Update `DEPLOY.md`:
  - Step 3 lists `JWT_SECRET` as required, with the `openssl` command.
  - The "What gets deployed" table adds `gateway` on 48080 and marks `game` and `forwardauth` as internal.
  - Step 4 notes that the tunnel still targets `localhost:48080`, now served by the gateway.
  - Step 6 adds running `tests/gateway_smoke.sh`.
  - Troubleshooting adds "401 on every request" (JWT_SECRET changed or the token is from the old key → log in again).

  Verify every command in the edited sections matches the files as committed.

## 3. Deploy and verify on the Pi

- [ ] 3.1 `[USER-GATE / controller-handled]` Add `JWT_SECRET` to the Coolify resource's environment variables before merging. Verify it is listed in Coolify → Environment Variables.
- [ ] 3.2 `[USER-GATE / controller-handled]` Merge to `main` and let Coolify redeploy. Verify that all four containers plus `gateway` are running, and that `curl https://avalon.blu3berry.com/` returns `Im running! :)`.
- [ ] 3.3 Run `tests/gateway_smoke.sh https://avalon.blu3berry.com` and verify all checks PASS. Also verify that `curl -X POST https://avalon.blu3berry.com/lobby/create` without a token now returns 401, where it was previously served.
- [ ] 3.4 Check Pi free memory in the Coolify dashboard, and record the number in the PR or in `STRATEGY.md`'s metric line. Verify it is above the ~2GB "stop adding" threshold.

## Workflow follow-up

- Avalon-mobile follow-up (separate repo):
  - Add a `production` BuildKonfig flavor with both base URLs set to `https://avalon.blu3berry.com/`.
  - Update `core/data/openapi/forwardauth-api.yaml` so `/auth` documents 401 instead of 403.
  - Play one full game against the live server.
- Archive this change with `/opsx:archive` once 3.3 passes.
