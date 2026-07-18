# Session Retrospective — Avalon revival + Pi/Coolify deploy

**Date:** 2026-07-18
**Project:** Avalon-Boardgame-with-Kubernetes
**Duration signals:** commits 550958e → f3865d0 (10 commits this session) + 2 merged PRs in Avalon-3-Spring; ~20 turns
**Scope:** conversation

## 1. Trial rule hits

| Rule | Fired? | Helped / friction / ignored | Note |
|---|---|---|---|
| Forced-choice / pre-select default in decisions | ~6× | helped | Every AskUserQuestion carried a Recommended default + reason; kept a long build-debug chain moving instead of stalling on menus |
| Post-task prompting advice | yes (mostly (b)) | neutral | Quiet-when-established exception engaged after 3× "prompt was clear" |
| Name the reference frame for comparisons/audits | 1× | helped | "what should we do" → named the deciding frame (strategy = k8s learning playground) before recommending |
| Proactive suggestions | several | helped | mongo cache cap, duplicate-workflow fold, security debt all surfaced unprompted |
| Branch-base preflight | relevant | moot | User drove branch choices; repo PR-protection forced branches anyway |
| Trial rule review at wrap | yes | helped | Produced this retro |

(No threshold-watch line — no prior retros exist to count against.)

## 2. Prompting advice (deduplicated)

No advice repeated 2+ times. One single-occurrence item noted for the record (not promoted): naming the Spring rewrite repo (`Avalon-3-Spring`) and the exact Pi model up front would have saved ~2 discovery round-trips — the hardware model materially changed the mongo-pin decision.

## 3. Recurring gotchas

| Gotcha | Times seen | Central home candidate |
|---|---|---|
| arm64 incompatibility in old images: amd64-only bases (`gradle:6.9.3-alpine`, `openjdk:17-alpine`), Python 3.8 + Django pulling `backports.zoneinfo` needing gcc, mongo pinned 4.4.18 for ARMv8.0-A | 3 | new doc: `docs/arm64-pi-gotchas.md` |
| Windows-origin file encoding: both `requirements.txt` were UTF-16 LE + BOM (PowerShell `pip freeze >`), broke pip on Linux | 2 | same doc |

## 4. Memory entries written this session

- `avalon-revival-state.md` — full revival state: Pi 4 target, mongo pin, submodule wiring, deploy-success + verification, parked tracks (updated ~5× across session)
- `cheap-agent-models.md` — use Sonnet/Haiku for subagents (Pro plan token budget)
- `MEMORY.md` — index for the above

## 5. Unresolved / deferred

- Firebase creds — mount `avalon-blu3berry-firebase-adminsdk.json` or strip Firebase (memory)
- k3s spike — Avalon-only, measure RAM, decide migration (STRATEGY.md track)
- mongo WiredTiger cache cap — sized to ~3.4GB on a shared 8GB Pi (memory)
- Playable game — revive Avalon-Angular frontend (STRATEGY.md track)
- Security — ForwardAuth hardcoded JWT key `"secret"` + Django fallback SECRET_KEY (memory)
- Fold duplicate `Tests`/`Test` workflow + README badge in Avalon-3-Spring (memory)

None sit in a real backlog file — only memory + STRATEGY.md tracks.

## 6. Action items (drafted — user reviews + applies)

- [ ] **(Pattern 1)** Create `docs/arm64-pi-gotchas.md` consolidating the arm64 + Windows-encoding traps hit this session (amd64-only bases, py3.8 zoneinfo/gcc, mongo ARMv8.2 pin, UTF-16 requirements). Each = Symptom / Cause / Fix / repro. Useful ahead of the k3s track, which will re-hit arm64.
- [ ] **(Pattern 4)** Create `docs/backlog.md` with the 6 deferred items from §5 so they aren't only in memory.
- [ ] **(Pattern 15-adjacent — sandbox, not allowlist)** Widen this project's sandbox network allowlist via `/sandbox` to include `services.gradle.org`, `repo.maven.apache.org`, `registry-1.docker.io` / `*.docker.io` so `gradle build` and `docker build` run sandboxed instead of needing `dangerouslyDisableSandbox` each time. This is a Docker/Gradle-heavy repo — friction will recur.
- [ ] **(quick win, next session)** Cap mongo WiredTiger cache in `docker-compose.yml` (`command: mongod --wiredTigerCacheSizeGB 1`) so it stops being sized to grab ~3.4GB on the shared Pi.

## 7. Cost ledger

No subagents dispatched and no mid-session main-loop model switch (the `/model` → Opus 4.8 applied to *new* sessions only). All work ran inline — the cheapest path. Note: the `cheap-agent-models` preference was recorded but never exercised this session because zero agents were spawned.

## 8. Permission ledger

| Command / tool | Times prompted | Already allowlisted? | Class | Promote to allowlist? |
|---|---|---|---|---|
| `docker build --platform linux/arm64` | 2 | no | mechanic (needs network) | no — not an allowlist item; widen sandbox network instead (§6) |
| `./gradlew build` / `test` | 2 | no | mechanic (needs network) | no — same, sandbox network |
| `docker manifest inspect` | 2 | no | mechanic (needs network) | no — same |

**Hook friction:** `sleep 45` blocked once by the background-work polling guard (adapted to an until-loop) — only 1×, below the 2× threshold, no action. `gh pr create` failed with a TLS cert error 2× (tool/keychain issue, not sandbox) — fell back to `curl` against the allowlisted `api.github.com`; worth remembering the curl fallback for PR creation in this environment.

**Drafted allowlist delta:** none — the recurring friction is sandbox *network scope* (build hosts), not command allowlisting. Addressed by the §6 `/sandbox` action.
