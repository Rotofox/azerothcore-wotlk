# Configuration

## Template vs generated files

AzerothCore uses the classic `*.conf.dist` → `*.conf` pattern:

- **Tracked templates** (`.conf.dist`) are the documentation-grade defaults:
  - `src/server/apps/worldserver/worldserver.conf.dist` → `worldserver.conf`
  - `src/server/apps/authserver/authserver.conf.dist` → `authserver.conf`
  - `src/tools/dbimport/dbimport.conf.dist` → `dbimport.conf`
  - `modules/*/conf/*.conf.dist` → `env/dist/etc/modules/*.conf`
- **Generated runtime configs** (gitignored) live in `env/dist/etc/` and
  `env/dist/etc/modules/` — these are the files a running server actually reads.

Values cited below are from the **runtime** configs in `env/dist/etc/` (what was actually used to
run the server installed here), with the template cited where they differ.

## Installer / build configuration

| File | Purpose | Key values |
|---|---|---|
| `conf/dist/config.cmake` | CMake option table (see [build-and-run.md](build-and-run.md)) | `SCRIPTS=static`, `MODULES=static`, `APPS_BUILD=all`, `TOOLS_BUILD=none`, `BUILD_TESTING=0`, `USE_COREPCH/USE_SCRIPTPCH=1`, … |
| `conf/dist/config.sh` | Installer paths | `SRCPATH`, `BUILDPATH=var/build/obj`, `BINPATH=env/dist`, `ORIGIN_REMOTE=https://github.com/azerothcore/azerothcore-wotlk.git`, `SKIP_MYSQL_INSTALL=false`, compilers `/usr/bin/clang` + `/usr/bin/clang++` |
| `conf/dist/env.ac` | Docker/compiler env | `CTYPE=RelWithDebInfo`, `CSCRIPTS=static`, `AC_CCACHE=true` |
| `conf/config.cmake` (if present) | User CMake overrides, `include()`d | — |

## `worldserver.conf` — key settings

Runtime values from `env/dist/etc/worldserver.conf` (line numbers from that file):

| Setting | Runtime value | Meaning |
|---|---|---|
| `RealmID` | `1` (line 88) | Realm id; must match a `realmlist` row |
| `WorldServerPort` | `8085` (line 95) | Game-world listening port (client connects here after realm select) |
| `BindIP` | `"0.0.0.0"` (line 102) | Interface to bind |
| `DataDir` | `"."` (line 182) | Where dbc/maps/vmaps/mmaps/Cameras live (relative to the working dir) |
| `LogsDir` | `""` (line 192) | Log directory (empty = next to the binary) |
| `Updates.EnableDatabases` | `7` (line 298) | Bitmask 1=auth, 2=characters, 4=world → all |
| `Updates.AutoSetup` | `1` (line 306) | Auto-apply DB base + updates at startup |
| `Updates.Redundancy` / `ArchivedRedundancy` | `1` / `0` (315/323) | Applied-update retention |
| `Updates.AllowRehash` | `1` (line 332) | Re-read update list on rehash |
| `Updates.CleanDeadRefMaxCount` | `3` (line 344) | Dead-reference cleanup |
| `Ra.IP` / `Ra.Port` | `0.0.0.0` / `3443` (410/417) | Telnet Remote Access |
| `SOAP.Enabled` / `SOAP.IP` / `SOAP.Port` | `0` / `127.0.0.1` / `7878` (432/439/446) | SOAP admin interface (off by default) |
| `ThreadPool` | `2` (line 483) | asio io-context threads |
| `MinWorldUpdateTime` | `1` (line 1062) | ms sleep per world tick |
| `MaxCoreStuckTime` | `0` (line 1080) | FreezeDetector watchdog; 0 = disabled |

**Fork addition** — the Playerbots logging appender (added by fork commit `b8567b3f6` "conf for
playerbots log", present in the template `worldserver.conf.dist`):

```
Appender.Playerbots=2,5,0,Playerbots.log,w      # line 658
Logger.playerbots=5,Console Playerbots           # line 694
```

This is why the installed server has a dedicated `Playerbots.log`.

## `authserver.conf` — key settings

Runtime values from `env/dist/etc/authserver.conf`:

| Setting | Runtime value | Meaning |
|---|---|---|
| `RealmServerPort` | `3724` (line 57) | Login port |
| `BindIP` | `"0.0.0.0"` (line 65) | Interface to bind |
| `BanExpiryCheckInterval` | `60` (line 154) | Seconds between ban-expiry checks |
| `Updates.EnableDatabases` | `1` (line 303) | Auth server only updates the auth DB |
| `Updates.AutoSetup` | `1` (line 311) | Auto-apply at startup |

(There is no `LoginREST` block in this tree's `authserver.conf.dist`.)

## `playerbots.conf` — key settings (mod-playerbots)

Template: `modules/mod-playerbots/conf/playerbots.conf.dist`. The file's section index lists:
**GENERAL SETTINGS**, **PLAYERBOTS SETTINGS** (GENERAL, SUMMON OPTIONS, MOUNT, GEAR, LOOTING,
TIMERS, DISTANCES, THRESHOLDS, QUESTS, COMBAT, PALADIN BUFFS STRATEGIES, CHEATS, SPELLS,
FLIGHTPATH), **RANDOMBOT-SPECIFIC SETTINGS** (GENERAL, LEVELS, GEAR, QUESTS, ACTIVITIES, SPELLS,
STRATEGIES, RPG STRATEGY, TELEPORTS, BATTLEGROUND & ARENA & PVP, INTERVALS), **PREMADE SPECS**
(WARRIOR, PALADIN, HUNTER, ROGUE, PRIEST, DEATHKNIGHT, …), and SYSTEM SETTINGS (database &
connections, chat, logs). Key options:

| Option | Template default | Runtime value (`env/dist/etc/modules/playerbots.conf`) |
|---|---|---|
| `AiPlayerbot.Enabled` | `1` | `1` |
| `AiPlayerbot.RandomBotAccountCount` | `0` | **`240`** ← operator raised this at runtime |
| `AiPlayerbot.RandomBotGuildCount` | (see file) | `20` |
| `AiPlayerbot.RandomBotMaxLevel` | (see file) | `80` |
| `AiPlayerbot.RandomBotMaxLevelChance` | (see file) | `0` |
| `AiPlayerbot.RandomBotJoinLfg` | `1` | `1` |
| `AiPlayerbot.CommandPrefix` | `""` | (empty — commands are `.bot` etc.) |

> ⚠️ Note the template/runtime divergence: `RandomBotAccountCount` is `0` in the `.conf.dist` but
> `240` in the generated runtime config — the operator customized it. Treat the runtime config as
> the "live" state.

## Other module configs (runtime: `env/dist/etc/modules/`)

| File | Module | Notes |
|---|---|---|
| `playerbots.conf` | mod-playerbots | see above |
| `AutoBalance.conf` | mod-autobalance | per-player difficulty scaling |
| `mod_account_mount.conf` | mod-account-mounts | account-wide mounts |
| `mod_ahbot.conf` | mod-ah-bot | auction-house bot (huge `AuctionHouseBot.*` config tree incl. `AdvancedPricing.*`; no SQL — fully config-driven) |
| `mod_aoe_loot.conf` | mod-aoe-loot | AoE looting |
| `mod_no_hearthstone_cooldown.conf` | mod-no-hearthstone-cooldown | removes HS cooldown |
| `random_enchants.conf` | mod-random-enchants | random item enchantments |

Each also has a `.conf.dist` template alongside it.

## Logging system

The core uses a **log4j-like** logger/appender system (`src/common/Logging/`, documented in
`doc/Logging.md`): config keys `Logger.<name>` map to `Appender.<name>` definitions of the form
`Appender.Name=type,level,flags,file,mode` (e.g. `Appender.Server=2,5,0,Server.log,w`).
The fork adds the `Playerbots` appender/logger pair (see above), so bot activity lands in
`Playerbots.log` while general server activity goes to `Server.log` (and errors to `Errors.log`).

See [data-layer.md](data-layer.md) for the `Updates.*` import flow and
[modules.md](modules.md) for how module configs are discovered.
