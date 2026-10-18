# Spec Delta

## Purpose

Issues and validates the login tokens that identify Avalon players: the `/login`, `/register` and `/auth` contract that clients and the gateway rely on.

## ADDED Requirements

### Requirement: Login issues a token
`POST /login` with a correct username and password SHALL return 200 with a JSON body `{"username": <username>, "token": <JWT>}`. The token SHALL expire 24 hours after issue.

#### Scenario: Correct credentials
- **WHEN** a registered user `alice` posts her correct password to `/login`
- **THEN** the response is 200 with `username` = `alice` and a `token` that `/auth` accepts

### Requirement: Login error responses
`POST /login` SHALL return 404 when the username does not exist and 403 when the password is wrong. Both SHALL have a JSON body of the form `{"message": <text>}`.

#### Scenario: Unknown user
- **WHEN** a client posts a username that is not registered to `/login`
- **THEN** the response is 404 with `Content-Type: application/json` and a body containing `message`

#### Scenario: Wrong password
- **WHEN** `alice` posts an incorrect password to `/login`
- **THEN** the response is 403 with `Content-Type: application/json` and a body containing `message`

### Requirement: Registration
`POST /register` SHALL create the user and return 200, or return 409 with a JSON `message` body when the username is already taken.

#### Scenario: New user
- **WHEN** a client posts an unused username and a password to `/register`
- **THEN** the response is 200 and a subsequent `/login` with those credentials succeeds

#### Scenario: Duplicate username
- **WHEN** a client posts an already registered username to `/register`
- **THEN** the response is 409 with a JSON body containing `message`

### Requirement: Token validation returns the caller's identity
`GET /auth` with `Authorization: Bearer <token>` for a valid, unexpired token SHALL return 200 with the token's username in the `Avalon-Header-Logged-In-User-Username` response header.

#### Scenario: Valid token
- **WHEN** `/auth` receives a valid unexpired token issued to `alice`
- **THEN** the response is 200 with `Avalon-Header-Logged-In-User-Username: alice`

### Requirement: Token validation rejects bad tokens with 401
`GET /auth` SHALL return 401 with a JSON `message` body when the `Authorization` header is missing, is not a bearer token, carries a token that is malformed or has an invalid signature, or carries an expired token. It SHALL NOT return a 5xx status for any client-supplied token.

#### Scenario: Missing header
- **WHEN** `/auth` receives a request without an `Authorization` header
- **THEN** the response is 401

#### Scenario: Expired token
- **WHEN** `/auth` receives a correctly signed token whose expiry has passed
- **THEN** the response is 401

#### Scenario: Malformed token
- **WHEN** `/auth` receives `Authorization: Bearer not-a-jwt`
- **THEN** the response is 401, not 500

#### Scenario: Token signed with another key
- **WHEN** `/auth` receives a token signed with a key other than the configured signing key, including the former hardcoded key `secret`
- **THEN** the response is 401

### Requirement: Signing key is configured, not hardcoded
The auth service SHALL sign and verify tokens with a key taken from its deployment configuration, and SHALL refuse to start when no key is configured.

#### Scenario: No key configured
- **WHEN** the auth service starts without a signing key in its environment
- **THEN** it exits with an error naming the missing setting instead of serving requests
