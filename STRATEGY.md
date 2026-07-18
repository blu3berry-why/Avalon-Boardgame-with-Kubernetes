---
name: Avalon
last_updated: 2026-07-18
---

# Avalon Strategy

## Target problem

A four-year-old multi-service college project (Avalon boardgame backend) sits undeployed on stale stacks — no arm64 images, EOL frameworks, dead Heroku/Azure leftovers — while an 8GB Raspberry Pi with Coolify sits ready. There is no self-hosted playground to practice real containerization and Kubernetes on real hardware.

## Our approach

Keep the deliberately multi-service architecture — the services being separate IS the point, it's what makes this a container/k8s playground. Deploy pragmatically: Coolify + docker-compose first to get a working baseline on the Pi, then a k3s experiment once it works. Modernize services incrementally, never blocking a working deploy.

## Who it's for

**Primary:** Me (Matyi) — hiring this project as a self-hosting/Kubernetes learning playground that stays honest by having a real deployable product inside it.

**Secondary:** Friends — playing Avalon online once the playground produces a playable game. Portfolio audience comes last.

## Key metrics

- **Deployed and reachable** — game API answers over the internet from the Pi; checked by hitting the health endpoint.
- **Full game playable end-to-end** — a complete Avalon round via API/frontend; checked with tester scripts (`Avalon-tester` / `tests/`).
- **Pi RAM headroom** — free memory on the Pi after all services up; below ~2GB free = stop adding, start trimming.
- **Stack freshness** — services on supported (non-EOL) framework versions; count goes up as modernization lands.

## Tracks

### Deploy pipeline

Arm64 multi-arch images (buildx), GitHub Actions CI, Coolify compose deployment.

_Why it serves the approach:_ nothing else matters until images actually run on the Pi.

### Service modernization

Spring backend → Boot 3.x/Kotlin 2.x as the game service; Django email + ForwardAuth updated in place; Ktor GameLogic retired.

_Why it serves the approach:_ incremental, per-service updates keep multi-service architecture alive without a rewrite.

### k3s experiment

Single-node k3s on the Pi, slim manifests (no kube-prometheus dump), decide Coolify vs k3s with real RAM numbers.

_Why it serves the approach:_ the Kubernetes learning goal, gated behind a working Coolify baseline.

### Playable game

Frontend revival (Avalon-Angular) + whatever the API needs so friends can actually play.

_Why it serves the approach:_ the playground stays honest — it ships a real product.

## Not working on

- Full kube-prometheus stack on the Pi — eats ~2GB+; a lightweight alternative can join the k3s track later.
- Minikube — k3s or nothing.
- Merging services into a monolith — efficient, but defeats the purpose.
- Modernizing the retired Ktor GameLogic service.
