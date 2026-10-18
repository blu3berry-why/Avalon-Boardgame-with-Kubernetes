# Spec Delta

## Purpose

The single public entry point to the Avalon backend: decides which requests reach the game service unauthenticated, authenticates the rest, and is the only source of the caller identity the game service trusts.

## ADDED Requirements

### Requirement: Single public entry point
The gateway SHALL be the only Avalon service reachable from outside the deployment. The game and auth services SHALL NOT be reachable except through the gateway.

#### Scenario: Game service not directly reachable
- **WHEN** a client on the host or the internet connects to the game service's container port without going through the gateway
- **THEN** the connection is refused because no host port is published for it

#### Scenario: Existing public hostname keeps working
- **WHEN** a client requests `https://avalon.blu3berry.com/`
- **THEN** the request is served through the gateway without changing the Cloudflare tunnel rule

### Requirement: Public auth routes
The gateway SHALL forward `POST /login` and `POST /register` to the auth service without requiring a token, and return the auth service's status code and body unchanged.

#### Scenario: Login reaches the auth service
- **WHEN** a client sends `POST /login` with a valid username and password and no `Authorization` header
- **THEN** the client receives the auth service's 200 response containing `username` and `token`

#### Scenario: Registration reaches the auth service
- **WHEN** a client sends `POST /register` with a new username and no `Authorization` header
- **THEN** the client receives the auth service's 200 response

### Requirement: Public health route
The gateway SHALL forward `GET /` to the game service without requiring a token.

#### Scenario: Health check without a token
- **WHEN** a client sends `GET /` with no `Authorization` header
- **THEN** the client receives the game service's 200 response

### Requirement: Protected game routes
Every request not matched by a public route SHALL be authenticated against the auth service before it reaches the game service. When authentication fails, the gateway SHALL return the auth service's status code and body and SHALL NOT contact the game service.

#### Scenario: Request without a token is rejected
- **WHEN** a client sends `POST /lobby/create` with no `Authorization` header
- **THEN** the client receives 401 and the game service does not receive the request

#### Scenario: Request with an expired token is rejected
- **WHEN** a client sends `GET /game/ABCD` with an expired bearer token
- **THEN** the client receives 401

#### Scenario: Request with a valid token is forwarded
- **WHEN** a client sends `POST /lobby/create` with a valid bearer token for user `alice`
- **THEN** the game service receives the request and the client receives the game service's response

### Requirement: Caller identity comes only from the auth service
On a forwarded protected request, the `Avalon-Header-Logged-In-User-Username` header received by the game service SHALL equal the username the auth service resolved from the token, replacing any value the client sent.

#### Scenario: Identity is set from the token
- **WHEN** a client with a valid token for `alice` sends `POST /lobby/ABCD/join`
- **THEN** the game service receives `Avalon-Header-Logged-In-User-Username: alice`

#### Scenario: Forged identity is overwritten
- **WHEN** a client with a valid token for `alice` sends a request that also carries `Avalon-Header-Logged-In-User-Username: bob`
- **THEN** the game service receives `Avalon-Header-Logged-In-User-Username: alice`

### Requirement: Client-supplied identity is stripped on public routes
The gateway SHALL remove any `Avalon-Header-Logged-In-User-Username` header from requests on public routes before forwarding them.

#### Scenario: Forged identity on a public route
- **WHEN** a client sends `GET /` with `Avalon-Header-Logged-In-User-Username: bob`
- **THEN** the game service receives the request without that header
