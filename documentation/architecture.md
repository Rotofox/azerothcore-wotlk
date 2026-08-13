# Server Architecture

Ground truth for this page is the C++ in `src/` (at HEAD `1507ab3f`). It is the upstream
AzerothCore architecture plus the fork's Playerbot integration points, which are called out
explicitly.

## The two processes and how they connect

A running server is **two separate binaries** (both built from this tree, both installed to
`env/dist/bin/`):

```
WoW client (3.3.5a, build 12340)
   │  login handshake (SRP6 + optional TOTP), realm list
   ▼
authserver  ── port 3724 ──  src/server/apps/authserver/   (login/realm server)
   │  "select realm 1 (AzerothCore, 127.0.0.1:8085)"
   ▼
worldserver ── port 8085 ── src/server/apps/worldserver/   (game world server)
```

- **authserver** is event-driven: `src/server/apps/authserver/Main.cpp` starts
  `sAuthSocketMgr.StartNetwork(*ioContext, bindIp, port)` and then runs `ioContext->run()`.
  asio `steady_timer` workers keep the DB alive (`KeepDatabaseAliveHandler`) and expire bans
  (`BanExpiryHandler`, interval `BanExpiryCheckInterval`, default 60 s); the realm list refreshes
  via `sRealmList->Initialize(*ioContext, RealmsStateUpdateDelay)` (default 20 s). The per-session
  state machine lives in `Server/AuthSession.{h,cpp}`: `STATUS_CHALLENGE → STATUS_LOGON_PROOF →
  STATUS_AUTHED`, handling `AUTH_LOGON_CHALLENGE` / `AUTH_LOGON_PROOF` / `REALM_LIST`.
  `Authentication/AuthCodes.{h,cpp}` defines the opcodes/errors. The client build check uses
  `build_info` rows (12340 / 13930 — see [project-overview.md](project-overview.md)).
  **authserver links only the `shared` library — no game code** (`src/server/apps/CMakeLists.txt`).
- **worldserver** is the simulation: `src/server/apps/worldserver/Main.cpp` runs the startup
  pipeline described below, then the world update loop. Extra pieces: `ACSoap/` (SOAP admin
  interface), `RemoteAccess/RASession.cpp` (telnet Remote Access, `Ra.*` config), and
  `CommandLine/CliRunnable.cpp` (in-game console).

### worldserver startup pipeline (`src/server/apps/worldserver/Main.cpp`, `main()`)

1. Parse CLI (`--config`, `--version`, `--dry-run`, Windows service flags).
2. `sConfigMgr` loads the main config (plus module configs via `LoadModulesConfigs`).
3. `AppenderDB` logging → banner (`AzerothCore 3.3.5a  -  www.azerothcore.org`).
4. OpenSSL threads/PRNG setup; PID file; asio `IoContext` + `ThreadPool`
   (`ThreadPool` config, default 2).
5. `sScriptMgr->SetScriptLoader(AddScripts)` and `SetModulesLoader(AddModulesScripts)`.
6. `StartDB()` — opens Login/Character/World DBs (and Playerbots DB when `MOD_PLAYERBOTS`).
7. Realm offline → `LoadRealmInfo` (reads `realmlist` table) → `sMetric->Initialize` (optional
   InfluxDB metrics) → `sSecretMgr->Initialize` → `sWorld->SetInitialWorldSettings()` (loads DBCs
   and DB content).
8. Optional **RA** acceptor (`Ra.Port`, default 3443) and **SOAP** thread (`SOAP.Port`, default
   7878; `SOAP.Enabled` is 0 by default).
9. `sWorldSocketMgr.StartWorldNetwork(*ioContext, worldListener, worldPort, networkThreads)` —
   starts accepting clients on **8085**.
10. Optional `FreezeDetector` watchdog (`MaxCoreStuckTime`; 0 = disabled in this tree's default
    config) → CLI console thread → `WorldUpdateLoop()`: sleep until `MinWorldUpdateTime`
    (default 1 ms) then `sWorld->Update(diff)`.

## Shared foundation — `src/common/`

| Component | What it provides |
|---|---|
| `Asio/` | `Acore::Asio` — boost::asio wrapper (`IoContext`, `Strand`, `SteadyTimer`, `Resolver`) used for all networking/timers |
| `Configuration/` | `sConfigMgr` — loads main + module configs, env-var overrides, typed `GetOption<T>()` |
| `Cryptography/` | `BigNumber`, AES/ARC4/HMAC, Argon2 (password hashing), TOTP (2FA), `OpenSSLCrypto::threadsSetup` |
| `DataStores/` | `DBCFileLoader` — low-level `.dbc` parser; typed `DBCStore<T>` wrappers live in `src/server/shared/DataStores/` |
| `Logging/` | `sLog` — log4j-like loggers/appenders, fmt-style `LOG_INFO` etc. (see `doc/Logging.md`) |
| `Metric/` | `sMetric` — optional InfluxDB metric export (Grafana dashboards in `apps/grafana/`) |
| `Navigation/` | Recast/Detour mmaps support (`dtQueryFilterExt`) |
| `Collision/` | vmaps: `DynamicTree` (GO LOS), `BoundingIntervalHierarchy` (static geometry queries) |
| `Threading/`, `IPLocation/`, `Encoding/`, `Utilities/`, `Debugging/`, `Dynamic/` | Thread helpers, IP geolocation, encodings, misc utilities, `Errors`/`WheatyExceptionReport`, RTTI helpers |
| `Banner.cpp`, `GitRevision.*` | Version banner, build-time git revision (from `genrev.cmake`) |

Grid constants shared by game and tools: `src/common/Collision/Maps/MapDefines.h` defines
`MAX_NUMBER_OF_GRIDS 64`, `MAX_NUMBER_OF_CELLS 8`, `SIZE_OF_GRIDS 533.3333f`.

## `src/server/shared/` and `src/server/database/`

- `shared/` — cross-app code: `DataStores/` (typed DBC stores), `Network/`, `Packets/`,
  `Realms/` (`RealmList` — realm definitions and the `build_info` client-build check),
  `Secrets/` (`sSecretMgr` — AES keys loaded from `authserver.conf`/`secret_digest`).
- `database/` — the DB layer: `Database/DatabaseWorkerPool` (async worker pool with prepared
  statements), `Database/DatabaseLoader`, `Database/Implementation/` (one pool per database —
  `LoginDatabase`, `CharacterDatabase`, `WorldDatabase`, plus the fork's
  **`PlayerbotsDatabase`**, see below), `Logging/` (SQL query logging), `Updater/` (`DBUpdater`
  — applies `data/sql` updates at startup).

### Playerbot integration in the database layer

When built with the module, the core gets a fourth database handle. `grep -rln MOD_PLAYERBOTS src/`
lists exactly **17 files** wired with `#ifdef MOD_PLAYERBOTS`, including:

- `src/server/database/Database/Implementation/PlayerbotsDatabase.{h,cpp}` — a dedicated
  `PlayerbotsDatabase` pool, registered in `DatabaseLoader` and `DatabaseWorkerPool`; it touches
  tables like `playerbots_custom_strategy`, `playerbots_db_store`, `playerbots_random_bots`,
  `playerbots_travelnode*`, `playerbots_enchants`, `playerbots_equip_cache`, `playerbots_guild_tasks`,
  `playerbots_item_info_cache`, `playerbots_dungeon_suggestion_*`, `playerbots_speech*`,
  `playerbots_weightscale*`, `playerbots_rarity_cache`, `playerbots_rnditem_cache`,
  `playerbots_tele_cache` (note: the file does **not** use `PREPARE_STATEMENT` macros).
- `WorldSession`/`WorldSessionMgr`/`World`/`IWorld` (incl. `GetPlayerbotsDBRevision()`),
  `Entities/Player/Player.cpp`, `Movement/MotionMaster.{h,cpp}`, `scripts/Commands/cs_server.cpp`,
  `database/Updater/DBUpdater.cpp` (playerbots DB updates), `DatabaseEnv*`.

The `MOD_PLAYERBOTS` define is added by `modules/CMakeLists.txt` (lines ~85-93) to the `database`
and `game-interface` targets when `mod-playerbots` is present — see [modules.md](modules.md).

## Game server — `src/server/game/`

Each top-level directory is a subsystem (all under `src/server/game/`):

| Subsystem | Purpose (from the headers) |
|---|---|
| `World/` | `World`, `WorldConfig`, `WorldState` — the world tick, game loop, session/world state |
| `Maps/` + `Grids/` | `Map`, `MapMgr`, `MapInstanced`, `MapUpdater`, `TransportMgr`; grid cells (`MAX_NUMBER_OF_GRIDS`/`CELLS`, `SIZE_OF_GRIDS`), grid loading, terrain (`GridTerrainData`) |
| `Entities/` | Object model: `Object` → `Unit` → `Player`/`Creature`/`GameObject`/`Item` inheritance |
| `AI/` | `CreatureAI`, `ScriptedAI`, SmartScripts (`SmartAI`), core AI (`CoreAI`) |
| `Scripting/` | `ScriptMgr` — the hook/event registry that scripts and modules register into; `ScriptObject` base classes; `ScriptDefines/` (incl. fork's `PlayerbotsScript.cpp`) |
| `Modules/` | `ModuleMgr` — module registry (`AddModulesScripts()` lands here) |
| `Handlers/` | Network CMSG packet handlers: `AuthHandler`, `CharacterHandler`, `MovementHandler`, `ChatHandler`, `QuestHandler`, `SpellHandler`, … |
| `Spells/` | `Spell`, `SpellMgr`, `SpellInfo`, `SpellEffects`, auras |
| `Movement/` | `MotionMaster`, `MovementGenerator`, splines, waypoints |
| `Battlegrounds/`, `Battlefield/`, `OutdoorPvP/`, `ArenaSpectator/` | PvP systems |
| `DungeonFinding/` | LFG dungeon finder (consumes `OnPlayerbotCheckLFGQueue`) |
| `Instances/`, `Guilds/`, `Groups/`, `AuctionHouse/`, `Loot/`, `Mails/`, `Quests/`, `Reputation/`, `Calendar/`, `Petitions/` | Standard game systems |
| `Warden/` | Anti-cheat |
| `Weather/`, `Addons/`, `Autobroadcast/`, `Motd/`, `Tickets/`, `Texts/`, `Chat/`, `Conditions/`, `Pools/`, `Skills/`, `Combat/`, `Accounts/`, `Achievements/`, `Events/`, `Globals/`, `Cache/`, `Time/`, `Tools/`, `Miscellaneous/` | Supporting systems |

### The script/module hook mechanism

- **Content scripts** (`src/server/scripts/`) — per-continent script libraries
  (`EasternKingdoms`, `Kalimdor`, `Northrend`, `Outland`, `World`, `Spells`, `Commands`,
  `Custom`, `Events`, `OutdoorPvP`, `Pet`) compiled into the `scripts` target; a generated loader
  (`src/server/scripts/ScriptLoader.cpp.in.cmake` → `AddScripts()`) calls each library's
  `Add<Zone>Scripts()` registration function.
- **Modules** (`modules/`) — discovered by CMake, compiled into the `modules` static library (or
  dynamic), registered via a generated loader (`modules/ModulesLoader.cpp.in.cmake` →
  `AddModulesScripts()` → each module's `Add<mod>Scripts()`). Modules register hooks into
  `ScriptMgr` / `ModuleMgr`. `worldserver` links `modules scripts game …` and calls
  `SetModulesLoader(AddModulesScripts)` at startup. Full mechanics in [modules.md](modules.md).
- **Playerbot hooks in the core** — `PlayerbotScript` (in `Scripting/ScriptMgr.h` lines ~117-125,
  implementation `Scripting/ScriptDefines/PlayerbotsScript.cpp`) declares 9 `OnPlayerbot*` hooks:
  `OnPlayerbotCheckLFGQueue`, `OnPlayerbotCheckKillTask`, `OnPlayerbotCheckPetitionAccount`,
  `OnPlayerbotCheckUpdatesToSend`, `OnPlayerbotPacketSent`, `OnPlayerbotUpdate`,
  `OnPlayerbotUpdateSessions`, `OnPlayerbotLogout`, `OnPlayerbotLogoutBots`. They are consumed in
  `DungeonFinding/LFGQueue.cpp`, `Server/WorldSession.cpp`, `Server/WorldSessionMgr.cpp`,
  `World/World.cpp`, `Entities/Player/Player.cpp`, `Maps/Map.cpp` etc. — the core calls into the
  module; the module overrides the hooks.

## Tools — `src/tools/`

- `dbimport/` — the DB updater (applies `data/sql` base + updates; config
  `src/tools/dbimport/dbimport.conf.dist`). See [data-layer.md](data-layer.md).
- `map_extractor/`, `vmap4_extractor/`, `vmap4_assembler/`, `mmaps_generator/` — client data
  extractors (gated by `TOOLS_BUILD`; link vendored `mpq`, `zlib`, `Recast`, `g3dlib`).

## Threading model (what the headers show)

- **worldserver**: one main **World thread** runs `WorldUpdateLoop()` → `sWorld->Update(diff)`;
  map updates are parallelized by `MapUpdater` (per-map update threads); networking runs on
  asio io-context threads (`ThreadPool`, default 2, plus network threads); SOAP runs on its own
  thread; RA runs on the io-context.
- **authserver**: single io-context event loop (`ioContext->run()`) with asio timers for
  DB-ping/ban-expiry/realm-refresh.

## Tests — `src/test/`

Googletest-based unit tests in `src/test/` (`common/`, `server/`, `mocks/`). Building them requires
`BUILD_TESTING=ON`, which fetches googletest (`src/cmake/googletest.cmake`) and adds lcov/genhtml
coverage targets. Run via `./acore.sh test` or the generated test binaries. The last real build of
this tree had `BUILD_TESTING` off, so no test binaries are installed in `env/dist/bin`.

See [modules.md](modules.md) for the module system and [divergences-and-status.md](divergences-and-status.md)
for the fork-specific caveats.
