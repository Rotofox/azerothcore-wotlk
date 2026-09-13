# AzerothCore WotLK (Playerbot fork) — Onboarding Documentation

> **This folder is the single source of truth for the project's state.** If a statement here
> disagrees with the code or the runtime, the code/runtime wins — fix this folder. Module `README`s
> (inside `modules/mod-*`) and `specs/` are **not** authoritative: module files may be upstream
> clones that get overwritten on pull, and specs are historical planning artifacts.

This folder documents **this repository**: a fork of the open-source
[AzerothCore](https://www.azerothcore.org/) **Wrath of the Lich King (WotLK, patch 3.3.5a, client
build 12340)** private-server emulator, based on
[liyunfan1223's `Playerbot` branch](https://github.com/liyunfan1223/azerothcore-wotlk/tree/Playerbot)
(the `liyunfan1223/*` repos now live under the
[`mod-playerbots`](https://github.com/mod-playerbots) GitHub org; the old URLs redirect). Like
upstream AzerothCore it runs as **two server processes** — `worldserver` (the game world, port
8085) and `authserver` (login/realm list, port 3724) — over **MySQL**. Unlike stock AzerothCore,
the core carries the hooks needed by the **Playerbot module** (`modules/mod-playerbots`), which
fills the world with AI-controlled "player-like" bots, plus a set of original custom systems
(Fury/NexusServer, quality + random enchants, QoL, multibot bridge).

**Status of this checkout:** built, installed, and running. The runtime lives in `env/dist/`
(binaries, client data v16, generated configs, logs). Treat the running server and the live
databases as the live state; `documentation/` describes it.

Read this folder top-to-bottom, or jump to a topic:

| Page | What it covers |
|---|---|
| [project-overview.md](project-overview.md) | What this server is, the AzerothCore/fork lineage, what "Playerbot" means, where version numbers come from |
| [repo-layout.md](repo-layout.md) | What every top-level directory is for |
| [build-and-run.md](build-and-run.md) | Prerequisites, how to build (acore.sh dashboard or manual CMake), how to run the two servers, Docker, and the operator aliases |
| [architecture.md](architecture.md) | The two processes, shared libraries, the game server's subsystems, script/module hooking, threading |
| [data-layer.md](data-layer.md) | The **four** databases, `data/sql/` layout, the dbimport update flow, client data files (dbc/maps/vmaps/mmaps) |
| [configuration.md](configuration.md) | Template vs generated config files, key settings for worldserver, authserver, playerbots and the other modules, logging |
| [modules.md](modules.md) | How the module system works and what each installed module does |
| [divergences-and-status.md](divergences-and-status.md) | How this fork diverges from upstream and what is unfinished/broken |
| [wow-handoff.md](wow-handoff.md) | A dated engineering handoff (custom systems + hard-won lessons). A snapshot — prefer this folder's other pages for current state. |

## Quick facts

| Fact | Value |
|---|---|
| Emulated game | World of Warcraft **Wrath of the Lich King 3.3.5a** (client build **12340**) |
| Git branch | `Playerbot` |
| Git remote | `https://github.com/liyunfan1223/azerothcore-wotlk.git` (redirects to the `mod-playerbots` org) |
| `acore.json` version | `14.0.0-dev` (upstream ACDB versioning — not a fork divergence) |
| License | AGPL-3.0 (`acore.json`, `LICENSE`) |
| Upstream base | AzerothCore master, merged into the `Playerbot` branch periodically |
| Client data version | **v16** (`env/dist/bin/data-version` = `INSTALLED_VERSION=v16`, wowgaming/client-data release) |
| Server binaries | `worldserver` (port **8085**), `authserver` (port **3724**) — installed under `env/dist/bin/` |
| Databases | `acore_auth`, `acore_characters`, `acore_world` (core) + `acore_playerbots` (added by mod-playerbots) |
| Modules installed | **13** — see [modules.md](modules.md#the-installed-modules) (9 independent git clones + 4 untracked local modules) |
| Client addons | **`NexusServer`** (Fury + Primeris talents + collections; supersedes the standalone `NexusFrames` addon) and **`QoLFlightPaths`** |
| Client patch | **`patch-4.MPQ`** — one consolidated patch (DBCs + addons + icons + instance maps). See `client-resources/README.md` |
| Repository state | Branch `Playerbot`, with uncommitted custom work in the working tree. Do **not** record a HEAD hash here (it drifts); check `git log` / `git status` live. |

### Keeping this folder honest

This folder drifted in the past because **volatile facts were written into prose** (a HEAD hash,
"working tree clean", module commit pins, "N modules", patch filenames, `Status:` headers). The
rules now:

1. **Never hardcode a commit hash, commit count, "clean tree", or per-module commit pin.** Point at
   the live source (`git`, the file, the config) instead.
2. **Durable, checkable facts live in [`state.json`](state.json)** (module inventory, DBs, ports,
   data version, client patch name). `python3 apps/codestyle/check-docs.py` re-derives them from
   the tree and fails on drift. Run it after any change that could touch one of those facts.
3. **Update this folder in the same change** that changes the thing it describes (see AGENTS.md).
4. **Module READMEs and `specs/` are not sources of truth.** Don't patch drift there; patch it here.

## How to read this folder

- **"What is this project?"** → [project-overview.md](project-overview.md)
- **"Where does everything live?"** → [repo-layout.md](repo-layout.md)
- **"How do I build and run it?"** → [build-and-run.md](build-and-run.md)
- **"How does the server work internally?"** → [architecture.md](architecture.md)
- **"How does content/data get into the game?"** → [data-layer.md](data-layer.md)
- **"Which config file controls X?"** → [configuration.md](configuration.md)
- **"What are all these `mod-*` folders?"** → [modules.md](modules.md)
- **"What changed vs upstream, and what is broken?"** → [divergences-and-status.md](divergences-and-status.md)

## Client pipeline (server → client)

Everything client-side is generated on demand into `client-resources/` and then **a human** moves it
to the testing machine (e.g. over SSH) and packs it into **`patch-4.MPQ`**.

> ⚠️ **Agents cannot build or pack MPQ files.** Repository work stops at generating/collecting the
> files under `client-resources/` and documenting the archive layout. The operator packs
> `patch-4.MPQ` manually on the client machine with an MPQ editor (Ladik's MPQ Editor / MPQEditor).
> Never write an instruction that has an agent run an MPQ tool.

- DBC patches: `generate_item_dbc_patch.py` (variant item icons), `generate_enchant_dbc_patch.py`
  (scaled enchant tooltips), `generate_spell_dbc_patch.py` (reagent cleanup), plus the LFG/85-cap
  and QoL generators. See `client-resources/README.md`.
- Addons: `client-resources/NexusServer/` and `client-resources/QoLFlightPaths/`.
- Staging folder for the NexusServer patch set: `client-resources/latest-mpq-patch/`.

One patch file only (`patch-4.MPQ`) unless a concrete client constraint forces another.
