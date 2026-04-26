# RUNTIME KNOWLEDGE BASE

## OVERVIEW
`runtime/` holds the shared base image filesystem and startup configuration used by app images, including Xorg, PulseAudio, D-Bus, and GPU-flavored variants.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Base image setup | `Dockerfile` | Common runtime layer |
| GPU-specific variants | `Dockerfile.intel`, `Dockerfile.nvidia`, `intel/`, `nvidia/` | Flavor-specific behavior |
| Supervisor/dbus startup | `supervisord*.conf`, `dbus` | Process orchestration |
| Display/audio defaults | `xorg.conf`, `default.pa`, `.Xresources` | Runtime environment knobs |
| Theme/font overrides | `fontconfig/`, `fonts/`, `icon-theme/` | Runtime assets copied into image |

## CONVENTIONS
- Treat this directory as base-image infrastructure shared by many app images.
- GPU subdirectories should only contain flavor-specific deltas, not duplicate base behavior without need.

## ANTI-PATTERNS
- Do not assume a runtime tweak only affects one browser image; changes here usually fan out across apps.
- Do not add app-specific behavior here when it belongs under `apps/<name>/`.

## NOTES
- Prefer parent-level rules here; the Intel/NVIDIA subtrees are small variants, not independent products.
