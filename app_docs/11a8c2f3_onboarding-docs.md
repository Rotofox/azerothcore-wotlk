# Repo-root `documentation/` — onboarding docs for the AzerothCore WotLK Playerbot fork

## What changed and why it matters

This change creates a **new `documentation/` folder at the repo root** containing a coherent
set of markdown onboarding pages for this repository — a fork of AzerothCore's Wrath of the
Lich King (WotLK, patch 3.3.5a, client build 12340) server based on liyunfan1223's
`Playerbot` branch, with the `mod-playerbots` module wired into the core. The repo had **no
root `README.md`**, so a coding agent (or human) arriving cold had no entry point; the new
folder fills that gap.

The docs are grounded in the actual tree (written against HEAD `1507ab3f`): every page cites
real paths, config values, ports, commit hashes, and file/line evidence. Rather than glossing
over rough edges, the set **explicitly flags broken/unfinished items** — most importantly that
`modules/TrackingModule.{h,cpp}` is dead WIP code (not compiled, `.cpp` untracked, references a
nonexistent `sEventMgr`), that all `modules/mod-*` sources are gitignored/untracked (a fresh
clone loses them), and that mod-playerbots declares itself "still under development".

The change also adds agent-tooling scaffolding around the docs task: a `.gitignore` update
(ignores `.pi`, `adws/`, sssf runtime files, `.env`, `__pycache__/`, `*.pyc`), a `justfile`
of SSSF task recipes, the original request (`requests/agent-onboarding-docs.md`), and the
task spec (`specs/11a8c2f3_project-documentation.md`). These are not server code and the
docs say so.

## Files that carry it

**The documentation set (the deliverable) — `documentation/`:**

| File | Covers |
|---|---|
| `documentation/README.md` | Index/entry point: what the repo is, quick-facts table (game version, data v16, modules, DBs), page table of contents, status flags |
| `documentation/project-overview.md` | Fork lineage (upstream AzerothCore → liyunfan1223 `Playerbot` branch → local commits), what "Playerbot" means, two-server summary, where version numbers come from |
| `documentation/repo-layout.md` | Purpose of every top-level directory (`src/`, `apps/`, `conf/`, `data/`, `modules/`, `deps/`, `env/`, `var/`, `bin/`, `doc/`, root files) |
| `documentation/build-and-run.md` | Prereqs, build via `acore.sh` dashboard or manual CMake (with the known-good configuration from `var/build/obj/CMakeCache.txt`), config generation, DB setup, client data (v16 download vs extract), running the two servers, Docker |
| `documentation/architecture.md` | The two processes (authserver 3724 / worldserver 8085), worldserver startup pipeline, `src/common/`, `src/server/{shared,database,game}/`, the script/module hook mechanism, the 9 `OnPlayerbot*` ScriptMgr hooks, tools, threading, tests |
| `documentation/data-layer.md` | The four databases (auth, characters, world + mod-playerbots' `acore_playerbots`), `data/sql/` layout, `dbimport` update flow and `Updates.*` settings, module SQL, client data files (dbc/maps/vmaps/mmaps/Cameras) |
| `documentation/configuration.md` | `.conf.dist` templates vs generated `env/dist/etc/*.conf`, key `worldserver.conf` / `authserver.conf` / `playerbots.conf` settings (with runtime values), module configs, logging appenders |
| `documentation/modules.md` | Module system mechanics (CMake discovery/loader, `MOD_PLAYERBOTS` special case), the 7 installed modules with origins, and a deep dive on mod-playerbots (identity, AI/strategies, commands, data, wiring, known rough edges) |
| `documentation/divergences-and-status.md` | Fork lineage vs upstream, the fork's core-side changes, local state, and the explicit unfinished/broken list (dead TrackingModule, playerbots dev-status, empty pending-DB dirs, template/runtime config drift) |

**Supporting (agent tooling, not server code):**

- `.gitignore` — ignores `.pi`, `adws`, sssf runtime (`adws/adw_data/sessions/`, `sssf.db*`), `.env`, `__pycache__/`, `*.pyc`
- `justfile` — SSSF starter recipes (demo, prompt, scout, plan, sdlc chains, session/phase/tail/procs SQLite views, `obs` trace UI)
- `requests/agent-onboarding-docs.md` — the original task request
- `specs/11a8c2f3_project-documentation.md` — the task spec/plan the builder followed (mission, fact base, per-page deliverables, grounding rules, verification checklist, recon addenda)

## How to use or verify it

- **Onboard**: read `documentation/README.md` first; it links to every topic page and maps
  reader intent → page ("want to build → build-and-run.md", "what changed vs upstream →
  divergences-and-status.md").
- **Verify accuracy against the tree** (spot-checks the docs themselves rely on):
  - Ports: `WorldServerPort = 8085` (`src/server/apps/worldserver/worldserver.conf.dist`),
    `RealmServerPort = 3724` (`src/server/apps/authserver/authserver.conf.dist`).
  - `acore.json` = `azerothcore-wotlk`, version `14.0.0-dev`, AGPL3.
  - `env/dist/bin/data-version` = `INSTALLED_VERSION=v16`.
  - Runtime configs in `env/dist/etc/`: `Updates.EnableDatabases = 7`,
    `AiPlayerbot.Enabled = 1`, `AiPlayerbot.RandomBotAccountCount = 240`.
  - Module/remote facts via `git -C modules/<mod> remote -v` and `git branch -a`.
  - Broken-item claims: `grep -rn TrackingModule modules/CMakeLists.txt` → 0 matches;
    `grep -rn sEventMgr src/` → 0 matches.
- **Check link integrity**: `documentation/README.md` links to all 8 topic pages; pages
  cross-link with relative markdown links — a link scan should resolve all of them.
- **Scope guard**: the docs task wrote only under `documentation/`; `doc/`, `src/`, `apps/`,
  `conf/`, `data/`, `modules/`, `env/`, `var/`, `bin/` were untouched, and nothing was built
  or run (binaries in `env/dist/bin/` are treated as evidence only).

Note: the current tree has one additional commit on top of the captured HEAD
(`53212c1ea "Fix factual errors and broken anchors in repo-root documentation/"`) — the diff
being documented here is the state at `1507ab3f`; re-verify any claim against the tree before
relying on it.
