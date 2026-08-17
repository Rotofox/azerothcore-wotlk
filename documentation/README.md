# AzerothCore WotLK (Playerbot fork) — Onboarding Documentation

This folder documents **this repository**: a fork of the open-source
[AzerothCore](https://www.azerothcore.org/) **Wrath of the Lich King (WotLK, patch 3.3.5a,
client build 12340)** private-server emulator, based on
[liyunfan1223's `Playerbot` branch](https://github.com/liyunfan1223/azerothcore-wotlk/tree/Playerbot).
Like upstream AzerothCore it runs as **two server processes** — `worldserver` (the game world,
port 8085) and `authserver` (login/realm list, port 3724) — over **MySQL** databases. Unlike
stock AzerothCore, the core carries the hooks needed by the **Playerbot module**
(`modules/mod-playerbots`), which fills the world with AI-controlled "player-like" bots.

Read this folder top-to-bottom, or jump to a topic:

| Page | What it covers |
|---|---|
| [project-overview.md](project-overview.md) | What this server is, the AzerothCore/fork lineage, what "Playerbot" means, where version numbers come from |
| [repo-layout.md](repo-layout.md) | What every top-level directory is for |
| [build-and-run.md](build-and-run.md) | Prerequisites, how to build (acore.sh dashboard or manual CMake), how to run the two servers, Docker |
| [architecture.md](architecture.md) | The two processes, shared libraries, the game server's subsystems, script/module hooking, threading |
| [data-layer.md](data-layer.md) | The four databases, `data/sql/` layout, the dbimport update flow, client data files (dbc/maps/vmaps/mmaps) |
| [configuration.md](configuration.md) | Template vs generated config files, key settings for worldserver, authserver, playerbots and the other modules, logging |
| [modules.md](modules.md) | How the module system works and what the 7 installed modules (incl. mod-playerbots) do |
| [divergences-and-status.md](divergences-and-status.md) | How this fork diverges from upstream, local state, and unfinished/broken items |

## Quick facts

| Fact | Value |
|---|---|
| Emulated game | World of Warcraft **Wrath of the Lich King 3.3.5a** (client build **12340**) |
| Git remote | `https://github.com/liyunfan1223/azerothcore-wotlk.git` (branch `Playerbot`) |
| `acore.json` version | `14.0.0-dev` (upstream ACDB versioning — not a fork divergence) |
| License | AGPL-3.0 (`acore.json`, `LICENSE`) |
| Upstream base | AzerothCore master, last merged **Sep 27–28 2025** (upstream ~PR #23037 era, merge `f67b86df8`) |
| Client data version | **v16** (`env/dist/bin/data-version` = `INSTALLED_VERSION=v16`, wowgaming/client-data release) |
| Server binaries | `worldserver` (port **8085**), `authserver` (port **3724**) — installed under `env/dist/bin/` |
| Databases | `acore_auth`, `acore_characters`, `acore_world` (core) + `acore_playerbots` (added by mod-playerbots) |
| Modules installed | `mod-playerbots`, `mod-account-mounts`, `mod-ah-bot`, `mod-aoe-loot`, `mod-autobalance`, `mod-no-hearthstone-cooldown`, `mod-random-enchants` |
| Repository state | Working tree clean at HEAD `1507ab3f` (2 local commits on top of the fork) |

## How to read this folder

- **"What is this project?"** → [project-overview.md](project-overview.md)
- **"Where does everything live?"** → [repo-layout.md](repo-layout.md)
- **"How do I build and run it?"** → [build-and-run.md](build-and-run.md)
- **"How does the server work internally?"** → [architecture.md](architecture.md)
- **"How does content/data get into the game?"** → [data-layer.md](data-layer.md)
- **"Which config file controls X?"** → [configuration.md](configuration.md)
- **"What are all these `mod-*` folders?"** → [modules.md](modules.md)
- **"What changed vs upstream, and what is broken?"** → [divergences-and-status.md](divergences-and-status.md)

## Status flags — read before you rely on anything

- ⚠️ **`modules/TrackingModule.h` / `.cpp` is broken, unfinished WIP code** — a "multi-gather"
  module that is *not compiled at all* (referenced by no CMake file), whose `.cpp` is not even
  tracked by git, and which calls an `sEventMgr` that does not exist anywhere in `src/`. It is
  dead code. See [divergences-and-status.md](divergences-and-status.md#unfinished--broken-items).
- ⚠️ **All `modules/mod-*` sources are gitignored/untracked** in this repo (each is an independent
  git clone). A fresh `git clone` of this repo will **not** contain the module sources; they must
  be re-cloned. See [modules.md](modules.md#module-sources-are-not-in-git-read-this-first) and
  [divergences-and-status.md](divergences-and-status.md).
- ⚠️ **mod-playerbots is "still under development"** per its own README; expect rough edges
  (dozens of `TODO`/`FIXME` markers in its source). See [modules.md](modules.md#mod-playerbots-deep-dive).

The rest of this folder was written against the actual tree (commit `1507ab3f`). If a statement
here disagrees with the code, the code wins — and please update the docs.

## Working docs

- [fury-nexusframes-handoff.md](fury-nexusframes-handoff.md) — Agent handoff for the **Fury system + NexusFrames** feature (account-wide kill-based progression + its UI addon). Design lives in `specs/fury-nexusframes-design.md`.
