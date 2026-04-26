# UTILS KNOWLEDGE BASE

## OVERVIEW
`utils/` contains build-oriented tooling and dependency-source trees rather than generic helper code for the product runtime.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Docker generator | `docker/` | Separate Go module for image generation/build composition |
| Xorg dependency sources | `xorg-deps/` | Custom or patched Xorg dependency trees |

## CONVENTIONS
- Treat `docker/` as maintainable first-party tooling.
- Treat `xorg-deps/` as dependency-source territory with a higher bar before editing.

## ANTI-PATTERNS
- Do not treat `utils/` as a catch-all extension point for app/server logic.
- Do not casually hand-edit generated/autotools artifacts under `xorg-deps/`; prefer source patches or regeneration paths.

## NOTES
- `utils/xorg-deps` mixes patched/custom sources with vendored upstream material; verify provenance before changing anything.
