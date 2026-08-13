# Divergences from Upstream and Project Status

This page answers: *"what is different about this checkout, and what is unfinished or broken?"*
Everything below was verified against the tree and git history at HEAD `1507ab3f`.

## Fork lineage

- **Upstream**: `azerothcore/azerothcore-wotlk` (master).
- **Fork remote**: `origin = https://github.com/liyunfan1223/azerothcore-wotlk.git`, branch
  **`Playerbot`** (the fork's other branches: `master`, `Testing`, `Playerbot-250911`,
  `Playerbot-20250908`, `movement-rewrite`, `modify_char_sel`, `fix_header_include`,
  `fix_salvaged_siege_engine_ai`, `revert_spell_crash`).
- **Upstream merges**: the `Playerbot` branch repeatedly merges upstream master
  ("Merge branch 'azerothcore:master' into Playerbot"). Latest: `f67b86df8` (2025-09-28) merging
  upstream `5d443d3cd` (2025-09-27, upstream ~PR #23037 era). The fork's own `master` is an
  ancestor of `Playerbot`.
- **This checkout**: 2 local commits on top of the fork:
  - `24c4e5664` "initial commit" (daedalus, 2026-08-14) — commented out the MySQL install block in
    `apps/installer/includes/os_configs/ubuntu.sh` and added `modules/TrackingModule.h` (see below).
  - `1507ab3f` "Add spec for repo-root documentation/ onboarding pages" — added this
    documentation task's spec, `justfile`, `requests/`, and a `.gitignore` update.

## What the fork changes in the core (vs upstream AzerothCore)

The `Playerbot` branch exists to support **mod-playerbots**. Its core-side changes:

1. **`MOD_PLAYERBOTS` compile define** wired into `modules/CMakeLists.txt` (lines ~85-93, added by
   fork commit `12d41d131` "Big update.") and used by **17 files** in `src/` (`#ifdef MOD_PLAYERBOTS`),
   including a dedicated **`PlayerbotsDatabase`** pool, hooks in `WorldSession`/`WorldSessionMgr`/
   `World`/`IWorld`/`Player`/`MotionMaster`/`cs_server.cpp`/`DBUpdater`/`DatabaseEnv*`. Details in
   [architecture.md](architecture.md).
2. **9 `OnPlayerbot*` ScriptMgr hooks** (`PlayerbotScript` in `Scripting/ScriptMgr.h`, impl in
   `Scripting/ScriptDefines/PlayerbotsScript.cpp`) — the bridge the module overrides. See
   [architecture.md](architecture.md).
3. **Playerbots logging**: `Appender.Playerbots` / `Logger.playerbots` in
   `src/server/apps/worldserver/worldserver.conf.dist` (commit `b8567b3f6` "conf for playerbots log")
   → dedicated `Playerbots.log` at runtime.
4. **`GetPlayerbotsDBRevision()`** in `IWorld`/`World` (reported by `.server info` in
   `cs_server.cpp`), so the core knows the bot DB's revision.
5. **CI**: `.github/workflows/core-build-playerbots.yml` builds the `Playerbot` branch (matrix:
   clang/gcc × ubuntu-22.04/24.04, Release).

## Local (non-upstream, non-fork) state

- HEAD `1507ab3f`; working tree clean (`.gitignore`, `justfile`, `requests/`, `specs/` were
  absorbed into the spec commit; `adws/` is gitignored).
- **Installed runtime**: `env/dist/` contains real compiled binaries (`worldserver`, `authserver`),
  client data **v16**, generated configs, startup scripts, and logs (`Server.log`,
  `Playerbots.log`, `Errors.log`, `Auth.log`) — evidence that a server was built **and run** here.
- **Build evidence**: `var/build/obj/CMakeCache.txt` — CMake 3.28.3, clang++,
  `CMAKE_BUILD_TYPE=Release`, `CMAKE_INSTALL_PREFIX=.../env/dist`, `SCRIPTS=static`,
  `MODULES=static`, `TOOLS_BUILD=none`, `APPS_BUILD=all`.
- **Module sources present but untracked/gitignored** (see [modules.md](modules.md#module-sources-are-not-in-git-read-this-first)).
- `apps/installer/includes/os_configs/ubuntu.sh`: the MySQL 8.4 download/install block is
  **commented out** by the local commit — `./acore.sh install-deps` will skip MySQL on Ubuntu until
  that is reverted or MySQL is installed another way.

## Unfinished / broken items

### 1. `modules/TrackingModule.{h,cpp}` — dead WIP "multi-gather" module ⚠️

- `TrackingModule.h` is tracked (added in `24c4e5664`); `TrackingModule.cpp` is **not tracked**.
- **It is not compiled**: no CMake file references it (verified: 0 matches for `TrackingModule` in
  `modules/CMakeLists.txt`, root `CMakeLists.txt`, or `src/`), and the module loader only globs
  `modules/*` **subdirectories** with a `src/` — the files sit at `modules/` root.
- It references **`sEventMgr`**, which **does not exist anywhere in `src/`** (verified by grep) —
  it would not compile even if added to the build.
- It uses TrinityCore-style APIs alien to this codebase: `GetOption<bool>("TrackingModule.EnableSpell")`
  with no config owner, `EVENT_PLAYER_LOGIN`/`EVENT_FLAG_DO_NOT_EXECUTE_IN_WORLD_CONTEXT`,
  `player->AddTrackedGameObject(...)`, `player->SendChatMessage(...)`.
- It hardcodes a placeholder spell: `#define SPELL_MULTITRACK 12345 // Replace this with the spell ID`.

**Conclusion: dead code today. Do not build on it; if you want a multi-gather module, write it as a
proper AzerothCore module** (see `modules/how_to_make_a_module.md`).

### 2. mod-playerbots is "still under development"

Its README says so explicitly, and the source carries dozens of `TODO`/`FIXME` markers — several
concrete examples are cited in [modules.md](modules.md#known-rough-edges-evidence-of-still-under-development)
(including a raid script that admits its plague handling is bugged and "impossible to handle …
the legit way" right now). Expect rough edges; run it on a test server before relying on it.

### 3. Pending DB update dirs are empty

`data/sql/updates/pending_db_{auth,characters,world}/` contain only `create_sql.sh` — no pending
update files. This is a normal state (the import workflow exists in
`.github/workflows/import_pending.yml`), not a bug.

### 4. Template vs runtime config drift

`AiPlayerbot.RandomBotAccountCount` is `0` in `modules/mod-playerbots/conf/playerbots.conf.dist`
but `240` in the generated runtime config `env/dist/etc/modules/playerbots.conf` — the operator
changed it. Runtime config wins; see [configuration.md](configuration.md).

### 5. Minor inconsistencies worth knowing

- The plan/older notes claimed a single subrepo marker at `deps/acore/.gitrepo`; in this tree all
  four `deps/acore/` tooling dirs are git **subrepos**, each with its own `.gitrepo` marker:
  `cmake-utils` (pins `azerothcore/cmake-utils` @ `1589c53`, method `merge`), `bash-lib`,
  `joiner` (pins `azerothcore/joiner` @ `9b74caa`), and `mysql-tools` (pins
  `azerothcore/mysql-tools` @ `6e9f399`).
- `MaxCoreStuckTime` default in this tree's config is **0** (FreezeDetector disabled), not 60.

## Files that are NOT server code (agent tooling)

- `adws/` — SSSF/AI-workflow session data (gitignored).
- `justfile` — SSSF task recipes (not the server build).
- `.env`, `.env.sample` — API keys for agent tooling (gitignored).
- `requests/`, `specs/` — agent planning docs.
Ignore these when working on the emulator itself.

## Docs status

- **Already existed**: `doc/Logging.md` (logging system), `doc/changelog/` (release changelogs),
  `modules/how_to_make_a_module.md` (module authoring guide), upstream docs referenced from CI.
- **This `documentation/` folder adds**: the onboarding set you are reading — index
  ([README.md](README.md)), [project-overview.md](project-overview.md),
  [repo-layout.md](repo-layout.md), [build-and-run.md](build-and-run.md),
  [architecture.md](architecture.md), [data-layer.md](data-layer.md),
  [configuration.md](configuration.md), [modules.md](modules.md), and this page.

If you change the code, keep these pages honest: the tree wins over any claim here.
