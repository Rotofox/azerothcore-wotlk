# Data Layer — Databases, SQL, and Content Import

## The four databases

A running server uses **four MySQL databases** (this fork has one more than stock AzerothCore):

| Database | Created by | Holds |
|---|---|---|
| `acore_auth` | `data/sql/create/create_mysql.sql` | Accounts, access/bans/mutes, `realmlist` (realms + ports + `gamebuild`), `build_info` (accepted client builds, e.g. 12340/13930), `motd`, `autobroadcast`, logs, `secret_digest`, `uptime` |
| `acore_characters` | `data/sql/create/create_mysql.sql` | Players, guilds, groups, auctions, mail, instances, arena teams, character data (base dumps in `data/sql/base/db_characters/`) |
| `acore_world` | `data/sql/create/create_mysql.sql` | Game content: creature/quest/spell/item/gameobject templates etc. (base dumps in `data/sql/base/db_world/` — 298 files) |
| `acore_playerbots` | `modules/mod-playerbots/data/sql/playerbots/create/create_mysql.sql` | Bot AI data added by mod-playerbots (see below) |

The core's three pools are opened by `StartDB()` (`LoginDatabase`, `CharacterDatabase`,
`WorldDatabase`); the fourth is opened by the fork's `PlayerbotsDatabase` when `MOD_PLAYERBOTS` is
defined (see [architecture.md](architecture.md)). The default MySQL user is `acore`.

## `data/sql/` layout

```
data/sql/
├── archive/          # old squashed dumps
├── base/             # the squashed baseline (db_auth/, db_characters/, db_world/)
│   ├── database-squash.md   # explains the squash/import process (maintainers only)
│   ├── db_auth/      # 18 files: account*.sql, realmlist.sql, build_info.sql, motd*.sql, …
│   ├── db_characters/
│   └── db_world/     # 298 files of content templates
├── create/           # create_mysql.sql (CREATE DATABASE), drop_mysql.sql
├── custom/           # gitignored; operator-custom SQL
├── old/              # legacy dumps
└── updates/          # incremental updates
    ├── db_auth/ db_characters/ db_world/        # dated update files (e.g. 2025_09_27_03.sql)
    ├── pending_db_auth/ pending_db_characters/ pending_db_world/   # CI-imported new updates
    └── README.md
```

The `pending_db_*` directories are the in-flight drop box for new updates; the world dir currently
carries the 81–85 / pet-scaling revisions (list the directory for the live set). The CI import
workflow is `.github/workflows/import_pending.yml`.

**Never hand-edit anything under `data/sql/` except `data/sql/updates/pending_db_*/`** — `base/`,
`archive/`, and `updates/db_*/` are immutable (see `.agents/docs/sql-guidelines.md`).

## How content is imported and applied

1. **Create** the databases: `data/sql/create/create_mysql.sql` (via `./acore.sh setup-db` or
   manually).
2. **Import the baseline**: the squashed dumps under `data/sql/base/`. The squash process itself is
   documented in `data/sql/base/database-squash.md` (maintainer-only; "a squash needs to be done on
   a clean database").
3. **Apply updates**: the **`dbimport`** tool (`src/tools/dbimport/Main.cpp` + `dbimport.conf.dist`)
   applies `data/sql/updates/*` incrementally, tracking applied files in the `updates` /
   `updates_include` tables of each DB. The servers can also run it automatically at startup via the
   `Updates.*` settings in `worldserver.conf` / `authserver.conf`:

   | Setting | Runtime value (this tree) | Meaning |
   |---|---|---|
   | `Updates.EnableDatabases` | `7` (worldserver) / `1` (authserver) | Bitmask: 1=auth, 2=characters, 4=world; 7=all. (authserver only updates auth) |
   | `Updates.AutoSetup` | `1` | Automatically apply base + updates at startup |
   | `Updates.Redundancy` / `Updates.ArchivedRedundancy` | `1` / `0` | Keep N copies of each applied update |
   | `Updates.AllowRehash` | `1` | Re-read update list without re-applying |
   | `Updates.CleanDeadRefMaxCount` | `3` | Garbage-collect dead references |

## Module SQL

Each module ships its own SQL and registers it with the db assembler:

- Modules carry `data/sql/` or `sql/` trees (`{auth,characters,world}/base` + `updates`).
- mod-playerbots' `conf/conf.sh.dist` (sourced from `include.sh`) registers
  `$MOD_PLAYERBOTS_ROOT/sql/{auth,characters,world}/{base,updates}/` custom paths for the db
  assembler (`db_assembler.sh`).
- mod-playerbots additionally defines the whole **`acore_playerbots`** database:
  `create/create_mysql.sql` + base tables in `data/sql/playerbots/base/` — e.g.
  `ai_playerbot_texts(_chance)`, `playerbots_account_keys/links/type`, `playerbots_custom_strategy`,
  `playerbots_db_store`, `playerbots_dungeon_suggestion_*`, `playerbots_enchants`,
  `playerbots_equip_cache`, `playerbots_guild_tasks`, `playerbots_item_info_cache`,
  `playerbots_preferred_mounts`, `playerbots_random_bots`, `playerbots_rarity_cache`,
  `playerbots_rnditem_cache`, `playerbots_speech(_probability)`, `playerbots_tele_cache`,
  `playerbots_travelnode(_link/_path)`, `playerbots_weightscale(_data)`, plus
  `version_db_playerbots` (DB revision tracking, reported by the core's
  `GetPlayerbotsDBRevision()`).
- **Custom modules** add their own tables (applied at startup via `Updates.AutoSetup`):
  `mod-fury` → `account_fury` (acore_auth); `mod-random-enchants` → `mod_re_rates`,
  `mod_re_item_variants`, `mod_re_spec_archetype`, `mod_re_suffix_boost`,
  `mod_re_class_archetype`, `mod_re_pool_rates`, and the `spellitemenchantment_dbc` matrix mirror
  (acore_world); `mod-qol` → `account_taxi` (acore_auth) + `mod_qol_pins` / `mod_qol_points`
  (acore_world); `mod-talent` → the account talent / Primeris tables; `mod-collections` and
  `mod-transmog` → appearance/collection tables.

The runtime `env/dist/etc/modules/playerbots.conf`'s `AiPlayerbot.*` settings control whether bots
are created/populated (see [configuration.md](configuration.md)).

## Client data files (not SQL)

Game content that is **not** in the database lives in binary data files, consumed by the servers at
runtime from `DataDir` (here `env/dist/bin`):

| Directory | Content | Produced by |
|---|---|---|
| `dbc/` | Client database files (spells, items, maps, …) loaded via `DBCStore<T>` | `map_extractor` or the v16 download |
| `maps/` | Terrain map files | `map_extractor` |
| `vmaps/` | Static collision geometry (LOS) | `vmap4_extractor` + `vmap4_assembler` |
| `mmaps/` | Movement meshes (pathfinding) | `mmaps_generator` |
| `Cameras/` | Camera paths | `map_extractor` / download |

Two ways to obtain them:

1. **Download** the pre-extracted package: `./acore.sh client-data` downloads release **v16** of
   `wowgaming/client-data` (`data.zip`) and writes `env/dist/bin/data-version`
   (`INSTALLED_VERSION=v16`). This is what produced the copies in `env/dist/bin/`.
2. **Extract** from a 3.3.5a client with `apps/extractor/extractor.sh` + the built tools
   (`map_extractor`, `vmap4_extractor`, `vmap4_assembler`, `mmaps_generator`; enabled with
   `TOOLS_BUILD`). Output lands in `var/extractors/` (which currently holds copies of `dbc/`,
   `maps/`, `mmaps/`, `vmaps/`, `Cameras/`), then is installed into the `DataDir`.

See [build-and-run.md](build-and-run.md) for the data setup steps and
[configuration.md](configuration.md) for the `DataDir`/`Updates.*` settings.
