# arm64 / Raspberry Pi deployment gotchas

Traps hit deploying this stack to an 8GB Raspberry Pi 4 (ARMv8.0-A, aarch64,
kernel `6.12.47+rpt-rpi-v8`) via Coolify. Read before touching Dockerfiles,
base images, or the mongo pin — most of these fail *silently at build time* or
*instantly at runtime* with no obvious hint.

Before writing a plan that adds a service or bumps an image here, grep this
doc for the artifact you're about to reference.

---

## 1. amd64-only base images

**Symptom:** `docker build` fails on the Pi (or Coolify), or the image builds
but the container won't start with `exec format error`.

**Cause:** Some old/alpine base images publish only `linux/amd64` — there is no
arm64 variant to pull. Confirmed amd64-only this project: `gradle:6.9.3-jdk17-alpine`,
`openjdk:17-alpine`.

**Fix:** Check the manifest before using an image:
```bash
docker manifest inspect <image> | grep -A2 platform   # look for linux/arm64
```
Swap to a multi-arch base. Verified arm64: `gradle:7.6-jdk17`,
`eclipse-temurin:17-jre`, `python:3.10-slim`, `mongo:4.4.18`.

---

## 2. Python 3.8 + Django 4.0 → `backports.zoneinfo` needs a compiler

**Symptom:** `pip install -r requirements.txt` fails on arm64 with
`error: command 'gcc' failed: No such file or directory`, building
`backports.zoneinfo`.

**Cause:** Django 4.0 uses stdlib `zoneinfo` on Python ≥3.9; on 3.8 it pulls
`backports.zoneinfo`, a C extension. No arm64 wheel exists for it on cp38, so
pip compiles from source — and slim images have no `gcc`.

**Fix:** Use `python:3.10-slim` (or any ≥3.9). `zoneinfo` becomes stdlib and the
C-extension dependency disappears entirely — no compiler needed. Do NOT reach
for `apt-get install gcc`; bumping Python is the smaller, cleaner fix.

---

## 3. MongoDB 5.0+ SIGILLs on the Pi 4 CPU

**Symptom:** mongo container crash-loops immediately, or logs
`MongoDB 5.0+ requires ARMv8.2-A or higher, and your current system does not
appear to implement [it]` then dies (SIGILL / illegal instruction).

**Cause:** MongoDB ≥5.0 (and 4.4.19+) is compiled targeting ARMv8.2-A
instructions. The Pi 4's Cortex-A72 is ARMv8.0-A — it doesn't implement them.
The image is labeled plain `arm64`, so Docker/Coolify pull and start it with no
warning; it dies on the first unsupported opcode.

**Fix:** Pin `mongo:4.4.18` — the last release that runs on ARMv8.0-A. Upgrade
path is hardware (Pi 5 / Cortex-A76 is ARMv8.2-A) or swap to FerretDB.
A stable mongo 4.4.18 container staying up is also the cheapest way to *confirm*
the Pi's CPU generation when you can't SSH in.

---

## 4. UTF-16 `requirements.txt` from Windows/PowerShell

**Symptom:** `pip install -r requirements.txt` fails to parse, or reads the
first package name mangled (e.g. `﻿asgiref`). `file requirements.txt` says
`UTF-16, little-endian ... with CRLF`.

**Cause:** PowerShell's `pip freeze > requirements.txt` writes UTF-16 LE with a
BOM. pip on Linux can't parse it.

**Fix:** Re-encode to ASCII/UTF-8, LF, no BOM:
```bash
iconv -f UTF-16LE -t UTF-8 requirements.txt | tr -d '\r' | sed '1s/^\xEF\xBB\xBF//' > tmp && mv tmp requirements.txt
file requirements.txt   # should say: ASCII text
```

---

## General rule

An image tagged `arm64` is necessary but not sufficient — the *CPU sub-version*
(ARMv8.0 vs 8.2) and whether a dependency ships an arm64 *wheel* both matter.
When a build or container fails with no clear error, reproduce the build locally
with `--platform linux/arm64` (on an Apple Silicon Mac this is native) to see
the real message Coolify hides.
