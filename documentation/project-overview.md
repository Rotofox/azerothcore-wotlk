# Project Overview

## What this is

This repository is a **fork of AzerothCore** — an open-source (AGPL-3.0) emulator of
*World of Warcraft: Wrath of the Lich King* (patch **3.3.5a**, client build **12340**) — with the
**Playerbot** system merged in. A server built from this tree lets players log in with the
original 3.3.5a WoW client and play in a world populated by both real players and
AI-controlled "bots" that behave like players.

The project is the upstream AzerothCore core plus the core-side changes required by the
**Playerbot module** (`modules/mod-playerbots`). Concretely, the fork lineage is:

```
azerothcore/azerothcore-wotlk (upstream master)
   └── liyunfan1223/azerothcore-wotlk  branch "Playerbot"   ← origin remote (now under the mod-playerbots org)
          └── this checkout (local custom commits + uncommitted custom work)
```

- Upstream AzerothCore master is merged into the `Playerbot` branch repeatedly.
- The repository's own `master` branch (`origin/master`) is an ancestor of `Playerbot`.
- Local work on top adds the custom systems and this documentation set. There is no fixed list of
  "local commits" here on purpose — the branch and working tree evolve; run `git log`/`git status`
  for the live values. See [divergences-and-status.md](divergences-and-status.md) for what is
  custom.

`acore.json` identifies the project:

```json
{
    "name":  "azerothcore-wotlk",
    "version":  "14.0.0-dev",
    "license":  "AGPL3"
}
```

The `14.0.0-dev` version string follows **upstream AzerothCore's** ACDB versioning (the
post-13.0.0 development line) — it is *not* a fork-specific version bump.

## What "Playerbot" means here

The `Playerbot` branch exists to support **`mod-playerbots`** (liyunfan1223's fork of
[IKE3's Playerbots](https://github.com/ike3/mangosbot), now under the `mod-playerbots` org). The module's README
(`modules/mod-playerbots/README.md`) describes it as "an AzerothCore module that adds player-like
bots to a server", and explicitly states it **requires a custom branch of AzerothCore to compile
and run** — namely this one (`liyunfan1223/azerothcore-wotlk/tree/Playerbot`). Its features, quoted
from the README:

- log in **alt characters as bots** (interact with your own alts, form parties, level up);
- **random bots** that wander the world, complete quests, and behave like players;
- bots that can run most **raids and battlegrounds**;
- highly configurable behavior;
- "excellent performance, even when running thousands of bots".

Players drive bots with chat commands such as `.bot`, `.rndbot`, `.bg`, `.gtask`, `.link`
(implemented in `modules/mod-playerbots/src/cs_playerbots.cpp`); bot behavior is configured in
`modules/mod-playerbots/conf/playerbots.conf.dist`. The README also warns: **"This project is
still under development."**

The core side of that integration is described in [architecture.md](architecture.md) (the
`PlayerbotScript` hooks, the dedicated `PlayerbotsDatabase`) and [modules.md](modules.md)
(the module deep dive).

## Two-server architecture (one paragraph)

Like all AzerothCore builds, a running server is **two separate processes**:

1. **`authserver`** — the login/realm server. The WoW client connects to it first (port **3724**),
   authenticates (SRP6, optional TOTP two-factor), and receives the realm list.
2. **`worldserver`** — the actual game world. The client connects to it on port **8085** after
   selecting a realm; it owns world state, simulation, scripting, and the game databases.

Both are built from this tree and installed to `env/dist/bin/`. See
[architecture.md](architecture.md) for how they work and [build-and-run.md](build-and-run.md) for
how to build/run them.

## Where the version numbers come from

| Number | Source | Meaning |
|---|---|---|
| Game version `3.3.5a` / client build `12340` | `src/common/Banner.cpp` (prints `AzerothCore 3.3.5a  -  www.azerothcore.org`); `data/sql/base/db_auth/build_info.sql` rows `(12340,3,3,5,'a',…)` and `(13930,3,3,5,'a',…)`; `data/sql/base/db_auth/realmlist.sql` default `gamebuild` = `12340` | Which client the server accepts and emulates |
| `14.0.0-dev` | `acore.json` | Upstream ACDB/emulator versioning, not fork-specific |
| Client data `v16` | `env/dist/bin/data-version` (`INSTALLED_VERSION=v16`); written by `inst_download_client_data` in `apps/installer/includes/functions.sh` (`local VERSION=v16`, downloads `data.zip` from `https://github.com/wowgaming/client-data/releases/download/v16/data.zip`) | Release tag of the pre-extracted `dbc/`, `maps/`, `mmaps/`, `vmaps/`, `Cameras/` data |
| Revision banner | Generated at build time by `src/cmake/genrev.cmake` into `revision.h` → `src/common/GitRevision.*` | Git hash/date/branch baked into the binary |

## What you can do with it

- Run a WotLK 3.3.5a private server (see [build-and-run.md](build-and-run.md)).
- Extend it with AzerothCore modules (see [modules.md](modules.md)) or modify core systems
  (see [architecture.md](architecture.md)).
- Populate the world with bots via mod-playerbots (see [modules.md](modules.md#mod-playerbots-deep-dive)).

See [divergences-and-status.md](divergences-and-status.md) for what is unfinished or broken in
this particular checkout.
