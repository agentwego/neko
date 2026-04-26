# APPS KNOWLEDGE BASE

## OVERVIEW
`apps/` contains per-application container build contexts layered on top of the shared runtime image.

## STRUCTURE
```text
apps/
├── firefox/
├── chromium/
├── cloakbrowser/
├── remmina/
├── vlc/
└── ...other browser/desktop variants
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Shared pattern | `apps/<app>/Dockerfile` | Main app image extension point |
| Flavor-specific overrides | `Dockerfile.*` | Variant-only image deltas |
| App startup/processes | `supervisord.conf`, `entrypoint.sh`, helper scripts | Local runtime behavior |
| CloakBrowser-specific stack | `cloakbrowser/` | Most customized app subtree in this repo |

## CONVENTIONS
- Most app directories are repeated build-context variants; keep shared conventions at `apps/` level unless one app diverges heavily.
- App-specific shell/config files should stay local to the app subtree.

## ANTI-PATTERNS
- Do not duplicate runtime-wide fixes here if they belong in `runtime/`.
- Do not assume every app subtree has unique rules; many should stay governed by this parent file.

## NOTES
- `cloakbrowser/` is the most operationally important local app because the root `Taskfile.yml` targets it directly.
