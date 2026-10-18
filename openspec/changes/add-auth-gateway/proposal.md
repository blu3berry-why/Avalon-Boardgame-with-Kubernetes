# Proposal

## Why

The deployed stack has no authentication in front of the game API. The Cloudflare tunnel maps `avalon.blu3berry.com` straight to the `game` container. avalon-spring identifies the caller only by the `Avalon-Header-Logged-In-User-Username` request header, and nothing in the stack sets that header, so any client can claim to be any user. `/login` and `/register` return 404 because ForwardAuth is never routed to. As a result no client, old or new, can sign in, and the new KMP mobile app (Avalon-mobile) cannot be played against the live server. Fixing this is the blocker for the strategy metric "full game playable end-to-end".

## What Changes

- Add a **Traefik** gateway service to `docker-compose.yml` that becomes the only public entry point. It takes over host port `48080`, so the existing Cloudflare tunnel rule keeps working unchanged.
  - Routes `POST /login` and `POST /register` to ForwardAuth.
  - Puts every other game route behind a `forwardAuth` middleware that calls ForwardAuth `/auth`. On success it copies `Avalon-Header-Logged-In-User-Username` from the auth response onto the upstream request.
  - Always removes any client-supplied `Avalon-Header-Logged-In-User-Username` header, on public routes as well as protected ones.
  - Keeps `GET /` (health) public.
- **ForwardAuth `/auth`** returns the token's username in `Avalon-Header-Logged-In-User-Username` on success.
- **BREAKING**: ForwardAuth `/auth` returns **401** (was 403) for a missing, malformed or expired token, and never 500. Clients that treated 403 as "logged out" must treat 401 that way. Avalon-mobile already does; the legacy app ignores the status.
- **BREAKING**: ForwardAuth signs and verifies JWTs with a key from the required `JWT_SECRET` environment variable instead of the hardcoded `"secret"`. Every token issued before the deploy becomes invalid, so every user logs in once more.
- ForwardAuth `/login` error responses return a proper JSON body. Today the `Response(dict)` calls emit a malformed body.
- `game` and `forwardauth` stop publishing host ports. They are reachable only on the compose network, through the gateway.

## Capabilities

### New Capabilities
- `api-gateway`: the public entry point. Which routes are public and which are protected, how the caller's identity reaches the game service, and that clients cannot forge that identity.
- `user-auth`: issuing and validating login tokens. The `/login`, `/register` and `/auth` contract, token signing-key handling, and the status codes clients rely on.

### Modified Capabilities
<!-- none: openspec/specs/ is empty -->

## Impact

- **Files**:
  - `docker-compose.yml`: new `gateway` service; port changes for `game` and `forwardauth`; `JWT_SECRET` added to `forwardauth`.
  - New `traefik/compose/` static and dynamic config.
  - `ForwardAuth/app.py`, plus ForwardAuth tests (new).
  - `DEPLOY.md`.
- **Deploy**: a new required Coolify environment variable, `JWT_SECRET`. The tunnel rule is unchanged.
- **Clients**:
  - Avalon-mobile: works as designed once its base URLs point at `https://avalon.blu3berry.com/`. Its `forwardauth-api.yaml` needs the `/auth` 403→401 update; that's a follow-up in that repo.
  - Legacy Android app: keeps working, because it sends `Authorization: Bearer` to the same host. Users re-login once.
- **Not touched**:
  - avalon-spring: it already trusts the header.
  - The email service: it talks to `game` over the compose network.
  - The legacy AKS/Helm workflows and `helm/` charts.
