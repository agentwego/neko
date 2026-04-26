# CLOAKBROWSER APP KNOWLEDGE BASE

## OVERVIEW
`apps/cloakbrowser/` is the most customized app image in this repo and the one directly exercised by the root `Taskfile.yml` smoke/deploy flow.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Image definition | `Dockerfile` | Main CloakBrowser app image |
| Container startup | `entrypoint.sh` | Runtime boot sequence |
| Supervisor processes | `supervisord.conf` | Process topology inside container |
| CDP bridge/health | `cdp-proxy.py`, `cdp-healthcheck.sh` | DevTools proxy and smoke-test surface |
| Browser policy/profile defaults | `policies.json`, `preferences.json`, `openbox.xml` | Local browser/runtime behavior |

## CONVENTIONS
- Keep this subtree aligned with the root `Taskfile.yml`, `deploy/`, and smoke-check expectations.
- Treat CDP proxy, supervisor config, and entrypoint behavior as one runtime chain.

## ANTI-PATTERNS
- Do not change exposed behavior here without checking `go-task verify:smoke` assumptions.
- Do not move app-specific operational logic back into generic `apps/` rules; this subtree is intentionally more specialized.

## NOTES
- If local deployment breaks, inspect this directory together with `deploy/` and `Taskfile.yml` first.
