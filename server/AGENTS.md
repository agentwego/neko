# SERVER KNOWLEDGE BASE

## OVERVIEW
`server/` is the main Go module for the backend, CLI, API, WebRTC stack, websocket flow, plugins, capture, and X11 integration.

## STRUCTURE
```text
server/
├── cmd/        # CLI entrypoints and service bootstrap
├── internal/   # Runtime-only backend domains
├── pkg/        # Shared packages usable across server subsystems
├── plugins/    # Plugin implementations/build targets
└── dev/        # Local server dev scripts
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Process entry | `cmd/neko/main.go` | Calls Cobra root command |
| Startup wiring | `cmd/serve.go` | Assembles config, desktop, capture, webrtc, websocket, api |
| Internal runtime behavior | `internal/` | Prefer this for server feature work |
| Shared protocol/types | `pkg/types` | Used across API, websocket, webrtc, capture, config |
| Shared helpers | `pkg/utils` | Cross-cutting helper layer |
| X11 / CGO glue | `pkg/xorg`, `pkg/xevent`, `pkg/xinput` | First-party integration code |

## CONVENTIONS
- Prefer `internal/` for server-only logic; use `pkg/` only for genuinely shared packages.
- Keep dependency direction flowing toward `pkg/types` and `pkg/utils`, not the other way around.
- `openapi.yaml` is an API contract artifact; treat it as a public interface surface, not incidental docs.

## ANTI-PATTERNS
- Do not introduce new code that depends on legacy compatibility fields marked TODO/remove/deprecated.
- Do not blur first-party X11 glue with vendored Xorg dependency sources under `../utils/xorg-deps`.
- Do not assume PR validation runs `go test`; CI primarily validates Docker builds, so run targeted tests yourself when changing server logic.

## COMMANDS
```bash
(cd server && go test ./...)
docker build -f server/Dockerfile server
```

## NOTES
- See `server/internal/AGENTS.md` for domain-level rules inside runtime code.
