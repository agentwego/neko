# DEPLOY KNOWLEDGE BASE

## OVERVIEW
`deploy/` contains local CloakBrowser deployment assets, especially compose env files and systemd integration.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Compose stack | `docker-compose.cloakbrowser.yml` | Main local deployment definition |
| Environment defaults | `.env.cloakbrowser`, `.env.cloakbrowser.example` | Runtime configuration inputs |
| systemd integration | `systemd/` | Service unit and helper scripts |

## CONVENTIONS
- This directory is tied to the CloakBrowser deployment flow exposed through `Taskfile.yml`.
- Keep compose/env/systemd changes aligned; they are part of one operational path.

## ANTI-PATTERNS
- Do not treat deploy assets as generic examples if root automation depends on them.
- Do not change service names, ports, or env contract lightly without checking Taskfile and health-check expectations.

## NOTES
- Root smoke verification spins up this deploy stack and checks health/CDP/supervisor behavior.
