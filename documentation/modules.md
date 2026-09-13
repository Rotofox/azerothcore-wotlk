# The Module System and Installed Modules

> **Source of truth.** This page — not the per-module `README.md` files — describes what is
> installed and what it does. Several modules are upstream git clones whose `README`s are
> upstream-owned and may be stale; the four local modules (`mod-fury`, `mod-qol`, `mod-talent`,
> `mod-collections`) are ours but their `README`s can still lag. When they disagree with this page
> or the tree, the tree wins — fix this page.

## Module sources are NOT in the parent git repo (read this first)

`modules/` is ignored by the parent repo's `.gitignore` (`/modules/*` ignored except `*.md`,
`*.sh`, `CMakeLists.txt`, `*.h`, `*.cmake`). `git ls-files modules/` shows only the loader
infrastructure — **zero module source files are tracked**. A fresh `git clone` of this repo does
not contain the modules.

There are two kinds of module directory in this tree:

- **9 independent git clones** (each has its own `.git`): `mod-playerbots`, `mod-account-mounts`,
  `mod-ah-bot`, `mod-aoe-loot`, `mod-autobalance`, `mod-no-hearthstone-cooldown`,
  `mod-random-enchants`, `mod-multibot-bridge`, `mod-transmog`. Re-clone these after a fresh
  checkout; update them with `wow-updatemods` (pull each). Never commit/push inside them from here.
- **4 local, untracked module directories** (no `.git` — original code that lives only in this
  working tree): `mod-fury`, `mod-qol`, `mod-talent`, `mod-collections`. They are not clones and
  have no upstream; keep them as-is and do not try to `git pull` them.

## How the module system works

- **Discovery**: `GetModuleSourceList` (`src/cmake/macros/ConfigureModules.cmake`) globs
  `modules/*` directories that contain a `src/` subdir.
- **Build**: `modules/CMakeLists.txt` (`CollectSourceFiles`) compiles all sources of each module
  into the **static `modules` library** (`MODULES=static`; `dynamic` produces shared objects,
  `none` disables). Modules are compiled **only when worldserver is built** (root `CMakeLists.txt`
  adds `modules/` after `src/` if worldserver is in `APPS_BUILD`).
- **Registration**: `modules/ModulesLoader.cpp.in.cmake` generates `AddModulesScripts()`, which
  calls each module's `Add<mod>Scripts()` entry point. Every module exposes a
  `src/<name>_loader.cpp` (e.g. `playerbots_loader.cpp` → `Addmod_playerbotsScripts()` →
  `AddPlayerbotsScripts()`). At startup worldserver calls
  `sScriptMgr->SetModulesLoader(AddModulesScripts)` (see [architecture.md](architecture.md)).
- **No module ships a `CMakeLists.txt`** — the loader globs `src/` directly. Some modules carry a
  `conf.sh.dist` / `include.sh` stub used by the installer / db-assembler to register their SQL
  paths.
- **Hook registration**: modules override `ScriptMgr` hooks (`ScriptObject` subclasses registered
  via `Add<mod>Scripts()`), and can be queried through `ModuleMgr` (`src/server/game/Modules/`).
- **Special case — `MOD_PLAYERBOTS`**: `modules/CMakeLists.txt` detects `mod-playerbots` and
  defines `MOD_PLAYERBOTS` for the `database` and `game-interface` targets; 17 core files are
  `#ifdef`-wired on it (see [architecture.md](architecture.md)).

## The installed modules

**13 modules** are present. All are built and shipped in the current server.

| Module | Kind | What it does |
|---|---|---|
| `mod-playerbots` | clone | AI player-like bots (see deep dive below) |
| `mod-account-mounts` | clone | Account-wide mounts (learned mounts shared across characters) |
| `mod-ah-bot` | clone | Auction-house bot that posts/buys auctions to simulate an economy; fully config-driven (no SQL) |
| `mod-aoe-loot` | clone | Loot all nearby corpses at once; ships `data/sql/db-world/base/aoe_loot_acore_string.sql` |
| `mod-autobalance` | clone | Scales mob/instance difficulty to group size/level; carries `acore-module.json` metadata |
| `mod-no-hearthstone-cooldown` | clone | Removes the hearthstone cooldown (community fork of the AC module) |
| `mod-random-enchants` | clone | Item Quality + scaled random-enchant system (variant swap + enchant matrix). Big local rework — see [data-layer.md](data-layer.md) and `specs/db8e1683_item-quality-random-enchants.md` |
| `mod-multibot-bridge` | clone | Server half of the **MultiBot-Chatless** client addon (`MBOT` addon-message protocol) |
| `mod-transmog` | clone | Appearance collection + transmog engine (collection mode) |
| `mod-fury` | local | Account-wide **Fury** kill-based progression (see deep dive below) |
| `mod-qol` | local | Quality-of-life: flight-path/inn/dungeon map pins + click-to-teleport, account-wide taxis, hunter QoL (pet fed, Auto Shot while moving), no reagents, offensive-spell autoattack, GM custom points |
| `mod-talent` | local | Account-wide **Primeris** talent tree (universal soul tree; purchase/refund + aura application) |
| `mod-collections` | local | Account-wide mounts/pets/transmog collections and the addon protocol; bridges into `mod-transmog` |

Runtime configs live in `env/dist/etc/modules/` (one `.conf` + `.conf.dist` per module; see
[configuration.md](configuration.md#other-module-configs-runtime-envdistetcmodules)).

Loader entry points present include `playerbots_loader.cpp`, `ah_bot_loader.cpp`, `AB_loader.cpp`,
`aoe_loot_loader.cpp`, `NHC_loader.cpp`, `RE_loader.cpp`, plus the loaders for the local modules.

## mod-playerbots deep dive

### Identity

- **`modules/mod-playerbots/README.md`**: "an AzerothCore module that adds player-like bots to a
  server", **based on [IKE3's Playerbots](https://github.com/ike3/mangosbot)**, and "requires a
  custom branch of AzerothCore to compile and run" — this one. It states **"This project is still
  under development"** and claims "excellent performance, even when running thousands of bots".
- Size: **~1,114 source files / ~171,400 lines** under `src/`.

### What it adds

- **Random bots** populating the world (`RandomPlayerbotMgr`, `RandomPlayerbotFactory` —
  configurable account/level/activity counts) and **alt-bots** (log in your own characters as
  bots via `PlayerbotMgr`).
- **AI**: `PlayerbotAI`/`PlayerbotAIBase` with per-class **strategies** under
  `src/strategy/<class>/` plus generic/triggers/values/actions/rpg; **dungeons** and **raids**
  (`src/strategy/dungeons/`, `src/strategy/raids/`); bot **factory** (`src/factory/`); travel
  system (`TravelMgr`/`TravelNode`).
- **Commands**: `.bot`, `.rndbot`, `.bg`, `.gtask`, `.link`/`.unlink`, `.account`, `.playerbots`,
  `.reset`, `.stack`, `.toggle`, `.debug`, `.pmon`, `.tick` (`src/cs_playerbots.cpp`).
- Supporting systems: `GuildTaskMgr`, `ChatFilter`, `PlayerbotCommandServer`, `PerformanceMonitor`,
  `LootObjectStack`, `FleeManager`, `BroadcastHelper`, `PlaceholderHelper`, `RandomItemMgr`.

### Configuration

`conf/playerbots.conf.dist` (sections listed in [configuration.md](configuration.md)) plus
`conf/conf.sh.dist` (registers `sql/{auth,characters,world}/{base,updates}` paths for the db
assembler). Runtime values live in `env/dist/etc/modules/playerbots.conf` (see
[configuration.md](configuration.md#playerbotsconf--key-settings-mod-playerbots)) — e.g.
`AiPlayerbot.Enabled = 1`, `RandomBotAccountCount = 240`, `RandomBotGuildCount = 20`.

### Data

Adds the **`acore_playerbots`** database (`data/sql/playerbots/` — create + base tables:
`ai_playerbot_texts(_chance)`, `playerbots_account_keys/links/type`, `playerbots_custom_strategy`,
`playerbots_db_store`, `playerbots_dungeon_suggestion_*`, `playerbots_enchants`,
`playerbots_equip_cache`, `playerbots_guild_tasks`, `playerbots_item_info_cache`,
`playerbots_preferred_mounts`, `playerbots_random_bots`, `playerbots_rarity_cache`,
`playerbots_rnditem_cache`, `playerbots_speech(_probability)`, `playerbots_tele_cache`,
`playerbots_travelnode(_link/_path)`, `playerbots_weightscale(_data)`, `version_db_playerbots`),
plus `characters` tables (`playerbots_names`, `playerbots_guild_names`, `playerbots_arena_team_names`)
and `world` updates. See [data-layer.md](data-layer.md).

### Wiring into the core

- `src/playerbots_loader.cpp` → `Addmod_playerbotsScripts()` → `AddPlayerbotsScripts()`.
- `MOD_PLAYERBOTS` compile define (modules/CMakeLists.txt special case) activates the core-side
  `PlayerbotsDatabase`, the 9 `OnPlayerbot*` ScriptMgr hooks, and the `#ifdef MOD_PLAYERBOTS`
  blocks in 17 core files (see [architecture.md](architecture.md)).
- `worldserver.conf` has the fork's `Appender.Playerbots` / `Logger.playerbots` (→ `Playerbots.log`).

### Known rough edges (evidence of "still under development")

Sample `TODO`/`FIXME` markers in module source:

- `src/BroadcastHelper.cpp` — `//TODO move texts to sql!`
- `src/PlayerbotAI.cpp` — `// TODO: missing implementation to port`
- `src/PlayerbotAI.cpp` — `/// @TODO: Fix all calls to ApplySpellMod`
- `src/strategy/values/SpellCastUsefulValue.cpp` — `// TODO: workaround`
- `src/strategy/raids/icecrown/RaidIccActions.cpp` — a long comment admitting the plague handling
  "is bugged … it is immpossible to handle plague atm the legit way"
- `src/strategy/generic/BattlegroundStrategy.cpp` — `//TODO: Do Priorities`

Also note the module's DB access style: `PlayerbotsDatabase` in the core does **not** use the
`PREPARE_STATEMENT` macro used elsewhere in `src/server/database` — worth knowing before touching
bot DB code. See [divergences-and-status.md](divergences-and-status.md) for the full status.
