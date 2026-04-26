# SERVER INTERNAL KNOWLEDGE BASE

## OVERVIEW
`server/internal/` contains the backend runtime domains that should evolve together but stay cleanly separated by subsystem boundaries.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Config loading / compatibility | `config/` | Includes legacy key migration and warnings |
| HTTP routing | `http/` | Public HTTP handlers and legacy bridge |
| REST-ish API surface | `api/` | Session, room, clipboard, plugins endpoints |
| WebSocket flow | `websocket/` | Event handlers and connection manager |
| WebRTC / input | `webrtc/` | Peer setup, data channel handlers, metrics |
| Media capture | `capture/` | GStreamer pipeline orchestration |
| Desktop integration | `desktop/` | Desktop/X display lifecycle and runtime coordination |
| Membership/session state | `member/`, `session/` | Room/user/session coordination |
| Plugin runtime | `plugins/` | Plugin loading and dependency handling |

## CONVENTIONS
- Keep subsystem boundaries explicit; avoid letting `http`, `websocket`, and `webrtc` accumulate shared ad-hoc state.
- `config/` is an assembly layer, not a general helper package.
- `capture/` and `webrtc/` are lifecycle-heavy; preserve start/stop/rebuild sequencing when editing.

## ANTI-PATTERNS
- Do not add new product logic to `http/legacy/` unless the work is explicitly backward-compatibility maintenance.
- Do not expand temporary compatibility code marked “remove once client is fixed” into new call paths.
- Do not stack more hacks onto capture selector / legacy pipeline branches when a cleaner abstraction is possible.

## NOTES
- When changing protocol behavior, inspect `pkg/types` and client-side `client/src/neko` together.
