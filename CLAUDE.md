# DowntimeLess: rules for Claude (and any contributor)

VPN fleet monitoring and management: `master/` (FastAPI + SQLite + Telegram bot), `agent/` (stdlib Python collector on each
server), `web/` (React 19 + Vite + Nasim, Persian RTL). Read `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` first.

## Language

- Everything the user sees (UI, bot messages, API error messages): Persian, digits and dates through the formatters.
- Code, comments, commits, technical docs: English. Replies to the owner: Persian.

## Brand (mandatory in the panel, README, bot and any new surface)

Logos live in `assets/brand/` (README) and `web/public/brand/` (panel). Never redraw or recolour them.

| File | Use |
| --- | --- |
| `logo-light.webp` | full logo (shield + "DowntimeLess", dark text) on light backgrounds |
| `logo-dark.webp` | full logo with white text, on dark backgrounds |
| `icon-light.png` / `icon-dark.png` | the shield mark alone, light/dark variant |
| `web/public/icons/*` | favicon, PWA icons (192/512), maskable icons, apple-touch icon (dark tile, white mark) |

Colour tokens (set once in the Nasim palette, components only use tokens, never hex):

| Role | Value |
| --- | --- |
| Brand green: primary accent and important buttons | `#A3E635` |
| Muted olive: low-emphasis surfaces | `#344A2D` |
| Dark background | `#0B1210` |
| Dark card | `#17221C` |
| Dark text | `#F4F8F2` |
| Light background | `#F7FAF5` |
| Light card | `#FFFFFF` |
| Light text | `#142019` |
| Readable accent on light backgrounds (text, links, borders) | `#3F6E18` |

Rules: `#A3E635` is for fills and buttons on dark and for filled buttons with dark text on light; on a light background
use `#3F6E18` for any green text or thin line (contrast). Dark is the default theme, light is a toggle. Status is always a
word plus colour, never colour alone.

## Panel layout (modelled on KasbBook, see `docs/design/kasbbook-dashboard-reference.webp`)

- Sidebar (right side in RTL): logo and project name at the top with the tagline; navigation below; at the bottom the
  "نصب برنامه" (install the app, PWA) button, then the signed-in user, theme toggle and logout.
- Top of the page: page title and short subtitle; actions on the opposite side.
- Phones: bottom tab bar plus the same items in an off-canvas menu; the install button stays reachable.
- PWA: manifest, service worker that never caches `/api/` or user data, install button driven by `beforeinstallprompt`
  (with an iOS "add to home screen" hint), `index.html` and `sw.js` are `no-cache`.

## Web rules

- Bun only. UI only from `@nyxon/nasim` (vendored copy in `web/vendor/nasim`, never edit it). Tokens only: no hex and no `dark:` in components.
- Texts in `src/strings/fa.ts` through `t`; server state in TanStack Query; forms in React Hook Form + Zod; generated client in
  `src/api/generated` and `src/api/zod` (only `bun run api:generate`). Comments are rare, one short line, why not what.
- `web/dist/` is committed: every web change ends with `bun run build` and a commit of `dist/`.
- Checks that must pass: `typecheck`, `lint`, `check:strings`, `check:nasim`, `format:check`, `test`, `api:check`, `build`.
- Always test the signed-out path of every protected route (a render-time redirect loop once crashed `/` for logged-out visitors
  while `/login` alone looked fine). The built-in browser pane is often hidden and unreliable; use headless Chromium
  (Playwright from `~/Documents/GitHub/Seamless_bot/web_frontend/node_modules`).

## Backend rules

- Plain `def` handlers, SQLite with parameterised SQL, epoch seconds, errors from the closed registry in `app/errors.py`
  (Persian messages), `operation_id = <tag>_<function>`. After a schema change: `python -m app.openapi_export ../docs/openapi.json`
  then `bun run api:sync && bun run api:generate` in `web/`.
- Tokens and keys are stored only as SHA-256 hashes. Secrets never go in logs, commits, chat or `.env` files in the repo.
- Anything that changes a server (reboot, upgrade, DNS) is a whitelisted job behind a per-server permission level and a signed-in
  human. API keys never get that power. Failover rules: two probes must agree, never remove the last DNS record.

## Workflow

1. Tests first for behaviour, then the change; `cd master && venv/bin/python -m pytest -q`, `python -m pytest agent/tests -q`.
2. Commit with `<area>: <imperative summary>`, then push to `main` on GitHub (`Emadhabibnia1385/DowntimeLess`).
3. Deploy: `ssh seamless 'sudo DL_YES=1 DL_LANG=fa downtimeless update'` (hard-syncs main, rolls back if unhealthy). Live panel:
   https://downtimeless.nyxon.tech. Domain change: `sudo downtimeless domain <host>`.
4. Never install the agent on, or change, a live VPN server without the owner's explicit yes for that server.

Developer: Emad Habibnia, Telegram @emadhabibnia, GitHub emadhabibnia1385.
