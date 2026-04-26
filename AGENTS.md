# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-24
**Commit:** 081d15d0
**Branch:** master

## OVERVIEW
Neko is a multi-domain monorepo for a self-hosted WebRTC virtual browser. The repo splits into a Go server, a Vue 2 client, a Docusaurus docs site, image/runtime assets, deployment files, and Xorg-related build utilities.

## STRUCTURE
```text
./
├── server/     # Go backend, API, WebRTC, websocket, plugins
├── client/     # Vue 2 + TypeScript frontend app
├── webpage/    # Docusaurus docs site and API docs
├── runtime/    # Base runtime image assets and GPU variants
├── apps/       # Per-app container build contexts
├── deploy/     # CloakBrowser compose + systemd deployment
└── utils/      # Docker generator and Xorg dependency sources
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Server startup | `server/cmd/neko/main.go`, `server/cmd/serve.go` | Cobra CLI entry and service wiring |
| HTTP / WebSocket / WebRTC | `server/internal/` | Main backend domains live here |
| Shared server types/helpers | `server/pkg/types`, `server/pkg/utils` | Cross-cutting backend layer |
| Frontend UI/client protocol | `client/src/` | Vue app, store, locale, `src/neko` protocol layer |
| Docs and generated API pages | `webpage/docs`, `webpage/src`, `webpage/scripts` | Docusaurus source, not `versioned_*` outputs |
| Runtime/image behavior | `runtime/`, `apps/` | Base image plus app-specific overlays |
| Local orchestration | `Taskfile.yml`, `deploy/` | CloakBrowser-focused smoke/deploy flow |

## CONVENTIONS
- Global text formatting follows `.editorconfig`: UTF-8, 2 spaces, LF, final newline.
- Root `tsconfig.json` only forwards to `client/tsconfig.json`; TypeScript rules live under `client/` and `webpage/` separately.
- CI is path-scoped: `client/` and `webpage/` validate with Node 18 builds; `server/` PR validation is Docker build based.
- `Taskfile.yml` is not generic repo automation; it is specifically for the CloakBrowser deployment flow.

## ANTI-PATTERNS
- Do not edit generated files such as the root `Dockerfile`; update the generator/template path instead.
- Do not treat `utils/xorg-deps/**`, `package-lock.json`, `go.sum`, or Docusaurus `versioned_*` outputs as normal maintenance targets.
- Do not add new legacy / V2 config keys when touching server config paths; compatibility reads exist, but new work should target current config names.
- Do not extend legacy transport layers (`server/internal/http/legacy`, compatibility fields marked TODO/deprecated) unless the change is explicitly about backward compatibility.

## UNIQUE STYLES
- `server/` is the protocol and systems integration core; `server/pkg/xorg` and `server/pkg/xevent` are first-party glue code, unlike vendored Xorg sources in `utils/xorg-deps`.
- `client/` and `webpage/` are both TypeScript projects but use different toolchains and should be reasoned about separately.
- `apps/` contains many repeated build contexts; prefer documenting shared rules at `apps/` level instead of per browser unless one app diverges sharply.

## COMMANDS
```bash
go-task verify:smoke
(cd client && npm ci && npm run build && npm run lint)
(cd webpage && npm ci && npm run build && npm run typecheck)
docker build -f server/Dockerfile server
```

## NOTES
- Follow the nearest nested `AGENTS.md` for directory-specific rules.
- For docs changes, prefer editing source docs/scripts over generated JSON or versioned snapshots.
- For security issues, follow `SECURITY.md` private disclosure guidance.
