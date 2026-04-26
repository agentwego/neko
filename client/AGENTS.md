# CLIENT KNOWLEDGE BASE

## OVERVIEW
`client/` is a standalone Vue 2 + TypeScript application with Vuex state, class-style components, generated emoji data, and a separate toolchain for helper scripts.

## STRUCTURE
```text
client/
├── src/        # App source, components, store, locale, protocol layer
├── tools/      # TS scripts such as emoji generation
├── public/     # Static app assets
└── dev/        # Local dev scripts/container setup
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| App bootstrap | `src/main.ts` | Vue application entry |
| UI components | `src/components/` | Main Vue SFCs |
| State | `src/store/` | Vuex stores |
| Protocol/client bridge | `src/neko/` | Connection/event core; not just UI |
| i18n | `src/locale/` | Translations |
| Generated/support data | `public/emoji.json`, `tools/` | Update generator path, not manual drift |

## CONVENTIONS
- Formatting inherits 2-space LF from `.editorconfig`, plus `client/.prettierrc`: no semicolons, single quotes, trailing commas, 120 columns.
- ESLint is the save-time fixer in workspace settings; do not rely on generic format-on-save behavior.
- TypeScript uses `@/` and `~/` aliases to `src/` and enables decorators.
- `tools/` has its own TS config and runtime assumptions; treat it separately from browser code.

## ANTI-PATTERNS
- Do not treat `src/neko/` as ordinary component code; protocol changes there usually affect server events and session behavior.
- Do not hand-edit generated/vendor-like assets unless there is no generator/source path.
- Do not copy legacy server compatibility behavior into new UI flows unless explicitly required.

## COMMANDS
```bash
(cd client && npm ci)
(cd client && npm run build)
(cd client && npm run lint)
```

## NOTES
- Root TypeScript config delegates here; this is the canonical TS setup for the app.
