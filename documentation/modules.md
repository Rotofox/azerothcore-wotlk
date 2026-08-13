# The Module System and Installed Modules

## Module sources are NOT in git (read this first)

All `modules/mod-*` directories are **independent git clones, ignored by the parent repo's
`.gitignore`** (`/modules/*` ignored except `*.md`, `*.sh`, `CMakeLists.txt`, `*.h`, `*.cmake`).
`git ls-files modules/` shows only the loader infrastructure — **zero module source files are
tracked**. A fresh `git clone` of this repo will not contain the modules; you must re-clone each
one into `modules/` (exactly what the upstream install flow does). In this tree all seven are
present on disk, each with its own `.git`.

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
- **No module ships a `CMakeLists.txt`** — the loader globs `src/` directly. Each module has a
  mostly-empty `include.sh` stub (0 bytes for most; mod-playerbots 288 B, mod-no-hearthstone-cooldown
  340 B) used by the installer/db-assembler.
- **Hook registration**: modules override `ScriptMgr` hooks (`ScriptObject` subclasses registered
  via `Add<mod>Scripts()`), and can be queried through `ModuleMgr` (`src/server/game/Modules/`).
- **Special case — `MOD_PLAYERBOTS`**: `modules/CMakeLists.txt` (lines ~85-93) detects
  `mod-playerbots` and defines `MOD_PLAYERBOTS` for the `database` and `game-interface` targets;
  17 core files are `#ifdef`-wired on it (see [architecture.md](architecture.md)).

## The seven installed modules

| Module | Origin (remote @ commit) | What it does |
|---|---|---|
| `mod-playerbots` | liyunfan1223/mod-playerbots @ `c3eecc0d` (2025-09-28) | AI player-like bots (see deep dive) |
| `mod-account-mounts` | azerothcore/mod-account-mounts @ `65ea80f` (2025-03-18) | Account-wide mounts (learned mounts shared across characters) |
| `mod-ah-bot` | NathanHandley/mod-ah-bot @ `eb7b34f` (2025-09-27) | Auction-house bot that posts/buys auctions to simulate an economy; **no SQL** ("Moved database configuration completely to config") |
| `mod-aoe-loot` | azerothcore/mod-aoe-loot @ `1efc29f` (2025-02-26) | Loot all nearby corpses at once; ships `data/sql/db-world/base/aoe_loot_acore_string.sql` |
| `mod-autobalance` | azerothcore/mod-autobalance @ `8382937` (2025-08-29) | Scales mob/instance difficulty to group size/level; carries `acore-module.json` v2.2.0 metadata; README warns master is "in beta" |
| `mod-no-hearthstone-cooldown` | BytesGalore/mod-no-hearthstone-cooldown @ `832ef5e` (2025-02-25) | Removes the hearthstone cooldown (community fork of the AC module) |
| `mod-random-enchants` | azerothcore/mod-random-enchants @ `02a2e0d` (2025-07-24) | Random enchantments on item drops; ships `data/sql/db-world/item_enchatment_random_tiers.sql` |

Loader entry points present: `playerbots_loader.cpp`, `ah_bot_loader.cpp`, `AB_loader.cpp`,
`aoe_loot_loader.cpp`, `NHC_loader.cpp`, `RE_loader.cpp`. Runtime configs:
`env/dist/etc/modules/{playerbots,AutoBalance,mod_account_mount,mod_ahbot,mod_aoe_loot,mod_no_hearthstone_cooldown,random_enchants}.conf`
(see [configuration.md](configuration.md)).

## mod-playerbots deep dive

### Identity

- **`modules/mod-playerbots/README.md`**: "an AzerothCore module that adds player-like bots to a
  server", **based on [IKE3's Playerbots](https://github.com/ike3/mangosbot)**, and "requires a
  custom branch of AzerothCore to compile and run" — this one. It states **"This project is still
  under development"** and claims "excellent performance, even when running thousands of bots".
- Module checkout: commit `c3eecc0d` ("Merge PR #1676 spec-tab-names", 2025-09-28), **2,210
  commits** in the module's own history.
- Size: **1,114 source files / 171,401 lines** under `src/` (measured with `wc -l` on
  `*.cpp`/`*.h`).

### What it adds

- **Random bots** populating the world (`RandomPlayerbotMgr`, `RandomPlayerbotFactory` —
  configurable account/level/activity counts) and **alt-bots** (log in your own characters as
  bots via `PlayerbotMgr`).
- **AI**: `PlayerbotAI`/`PlayerbotAIBase` with per-class **strategies** under
  `src/strategy/<class>/` (deathknight, druid, hunter, mage, paladin, priest, rogue, shaman,
  warlock, warrior) plus generic/triggers/values/actions/rpg; **dungeons** (`src/strategy/dungeons/`,
  7,927 lines) and **raids** (`src/strategy/raids/`, 27,453 lines — naxxramas, ulduar, icecrown,
  moltencore, aq20, …); bot **factory** (`src/factory/`, 6,690 lines); travel system
  (`TravelMgr`/`TravelNode`).
- **Commands**: `.bot`, `.rndbot`, `.bg`, `.gtask`, `.link`/`.unlink`, `.account`, `.playerbots`,
  `.reset`, `.stack`, `.toggle`, `.debug`, `.pmon`, `.tick` (`src/cs_playerbots.cpp`).
- Supporting systems: `GuildTaskMgr`, `ChatFilter`, `PlayerbotCommandServer`, `PerformanceMonitor`,
  `LootObjectStack`, `FleeManager`, `BroadcastHelper`, `PlaceholderHelper`, `RandomItemMgr`.

### Source map (top level of `src/`)

`PlayerbotAI*`, `PlayerbotMgr*`, `RandomPlayerbotMgr*`, `RandomPlayerbotFactory*`,
`PlayerbotAIConfig*` (config parsing), `Playerbots.cpp`/`Playerbots.h` (module entry —
`AddPlayerbotsScripts`), `playerbots_loader.cpp`, `cs_playerbots.cpp` (commands), `TravelMgr*`,
`TravelNode*`, `Talentspec*`, `GuildTaskMgr*`, `ChatFilter*`, `BroadcastHelper*`, `ChatHelper*`,
`Helpers*`, `AiFactory*`, `ServerFacade*`, `FleeManager*`, `LootObjectStack*`,
`PerformanceMonitor*`, `PlayerbotSecurity*`, `PlayerbotTextMgr*`, `PlayerbotDbStore*`,
`PlayerbotDungeonSuggestionMgr*`, `PlayerbotCommandServer*`, `RandomItemMgr*`, plus `strategy/`
and `factory/` trees.

### Configuration

`conf/playerbots.conf.dist` (sections listed in [configuration.md](configuration.md)) plus
`conf/conf.sh.dist` (registers `sql/{auth,characters,world}/{base,updates}` paths for the db
assembler). Runtime values in `env/dist/etc/modules/playerbots.conf`: `AiPlayerbot.Enabled = 1`,
`RandomBotAccountCount = 240`, `RandomBotGuildCount = 20`, `RandomBotMaxLevel = 80`.

### Data

Adds the **`acore_playerbots`** database (`data/sql/playerbots/` — create + 30 base tables:
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

- `src/BroadcastHelper.cpp:657` — `//TODO move texts to sql!`
- `src/PlayerbotAI.cpp:643` — `// TODO: missing implementation to port`
- `src/PlayerbotAI.cpp:3149` — `/// @TODO: Fix all calls to ApplySpellMod`
- `src/strategy/values/SpellCastUsefulValue.cpp:43` — `// TODO: workaround`
- `src/strategy/raids/icecrown/RaidIccActions.cpp:486` — a long comment admitting the plague
  handling "is bugged … it is immpossible to handle plague atm the legit way"
- `src/strategy/generic/BattlegroundStrategy.cpp:67` — `//TODO: Do Priorities`

Also note the module's DB access style: `PlayerbotsDatabase` in the core does **not** use the
`PREPARE_STATEMENT` macro used elsewhere in `src/server/database` — worth knowing before touching
bot DB code. See [divergences-and-status.md](divergences-and-status.md) for the full status flags.
