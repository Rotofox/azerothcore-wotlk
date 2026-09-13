# Divergences from Upstream and Project Status

This page answers: *"what is different about this checkout, and what is unfinished or broken?"*

> **No volatile facts.** This page deliberately does **not** pin a HEAD hash, a commit count, or a
> "clean tree" claim — those drifted before. For live values run `git log --oneline` and
> `git status`; the tree always wins over any statement here.

## Fork lineage

- **Upstream**: `azerothcore/azerothcore-wotlk` (master).
- **Fork remote**: `origin = https://github.com/liyunfan1223/azerothcore-wotlk.git`, branch
  **`Playerbot`**. The `liyunfan1223/*` repositories now live under the
  [`mod-playerbots`](https://github.com/mod-playerbots) GitHub org; the old URLs redirect.
- **Upstream merges**: the `Playerbot` branch repeatedly merges upstream master
  ("Merge branch 'azerothcore:master' into Playerbot").
- **This checkout**: the `Playerbot` branch carries local custom commits on top of the fork tip,
  **and** the working tree carries uncommitted custom work (custom systems under `modules/`,
  `client-resources/`, `specs/`, pending SQL). It is built, installed, and running.

## What the fork changes in the core (vs upstream AzerothCore)

The `Playerbot` branch exists to support **mod-playerbots**. Its core-side changes:

1. **`MOD_PLAYERBOTS` compile define** wired into `modules/CMakeLists.txt` and used by ~17 files
   in `src/` (`#ifdef MOD_PLAYERBOTS`), including a dedicated **`PlayerbotsDatabase`** pool, hooks
   in `WorldSession`/`WorldSessionMgr`/`World`/`IWorld`/`Player`/`MotionMaster`/`cs_server.cpp`/
   `DBUpdater`/`DatabaseEnv*`. Details in [architecture.md](architecture.md).
2. **9 `OnPlayerbot*` ScriptMgr hooks** (`PlayerbotScript` in `Scripting/ScriptMgr.h`, impl in
   `Scripting/ScriptDefines/PlayerbotsScript.cpp`) — the bridge the module overrides. See
   [architecture.md](architecture.md).
3. **Playerbots logging**: `Appender.Playerbots` / `Logger.playerbots` in
   `src/server/apps/worldserver/worldserver.conf.dist` → dedicated `Playerbots.log` at runtime.
4. **`GetPlayerbotsDBRevision()`** in `IWorld`/`World` (reported by `.server info` in
   `cs_server.cpp`), so the core knows the bot DB's revision.
5. **CI**: `.github/workflows/core-build-playerbots.yml` builds the `Playerbot` branch (matrix:
   clang/gcc × ubuntu-22.04/24.04, Release).

Beyond the Playerbot core hooks, this checkout layers **custom systems** on top (all currently
built and shipped): Fury (`mod-fury`) + the NexusServer client addon, the item-quality/scaled
random-enchant system (`mod-random-enchants`), QoL (`mod-qol` + `QoLFlightPaths`), the multibot
bridge (`mod-multibot-bridge`), and the account-wide talent + collections stack (`mod-talent`,
`mod-collections`, `mod-transmog`). See [modules.md](modules.md) and [wow-handoff.md](wow-handoff.md).

## Local (non-upstream, non-fork) state

- **Installed runtime**: `env/dist/` contains compiled binaries (`worldserver`, `authserver`),
  client data **v16**, generated configs, startup scripts, and logs (`Server.log`,
  `Playerbots.log`, `Errors.log`, `Auth.log`). The server is **built and running**.
- **Build evidence**: `var/build/obj/CMakeCache.txt` records the last real build (CMake 3.28.3,
  clang++, `CMAKE_BUILD_TYPE=Release`, `CMAKE_INSTALL_PREFIX=.../env/dist`, `SCRIPTS=static`,
  `MODULES=static`, `TOOLS_BUILD=none`, `APPS_BUILD=all`).
- **Modules**: 13 present on disk — 9 independent git clones + 4 untracked local modules. See
  [modules.md](modules.md#module-sources-are-not-in-the-parent-git-repo-read-this-first).
- `apps/installer/includes/os_configs/ubuntu.sh`: the MySQL download/install block is
  **commented out** by a local commit, so `./acore.sh install-deps` skips MySQL on Ubuntu. MySQL
  is already installed and serving the live DBs (user/password `acore`/`acore`).

## Unfinished / broken items

### 1. `modules/TrackingModule.{h,cpp}` — dead WIP "multi-gather" module ⚠️

- `TrackingModule.h` is tracked; `TrackingModule.cpp` is **not tracked**.
- **It is not compiled**: no CMake file references it (the module loader only globs
  `modules/*` **subdirectories** with a `src/` — these files sit at `modules/` root).
- It references **`sEventMgr`**, which does not exist anywhere in `src/` — it would not compile
  even if added to the build.
- It uses TrinityCore-style APIs alien to this codebase and hardcodes a placeholder spell
  (`SPELL_MULTITRACK 12345`).

**Conclusion: dead code today. Do not build on it; if you want a multi-gather module, write it as a
proper AzerothCore module** (see `modules/how_to_make_a_module.md`).

### 2. mod-playerbots is "still under development"

Its README says so explicitly, and the source carries dozens of `TODO`/`FIXME` markers (examples in
[modules.md](modules.md#known-rough-edges-evidence-of-still-under-development)). Expect rough
edges; run it on a test server before relying on it.

### 3. Pending DB update dirs

`data/sql/updates/pending_db_*/` may hold unmerged update files (the world dir currently carries
the 81–85 / pet-scaling revisions). This is normal — the import workflow lives in
`.github/workflows/import_pending.yml`. Don't hardcode a count; list the directory.

### 4. Template vs runtime config drift

Module/world `.conf.dist` templates and the generated runtime `.conf` files under `env/dist/etc/`
can differ (the operator tunes the runtime copy). Treat the runtime config as the live state; see
[configuration.md](configuration.md).

### 5. Minor inconsistencies worth knowing

- In this tree the `deps/acore/` tooling dirs are git **subrepos**, each with its own `.gitrepo`
  marker (`cmake-utils`, `bash-lib`, `joiner`, `mysql-tools`).
- `MaxCoreStuckTime` default in this tree's config is **0** (FreezeDetector disabled).

## Files that are NOT server code (agent tooling)

- `adws/` — SSSF/AI-workflow session data (gitignored).
- `justfile` — SSSF task recipes (not the server build).
- `.env`, `.env.sample` — API keys for agent tooling (gitignored).
- `requests/`, `specs/` — agent planning docs. Ignore them when working on the emulator itself
  (and treat them as historical, not as project state — see [README.md](README.md)).

## Docs status

- **Already existed**: `doc/Logging.md` (logging system), `doc/changelog/` (release changelogs),
  `modules/how_to_make_a_module.md` (module authoring guide).
- **This `documentation/` folder is the onboarding set and the source of truth**: index
  ([README.md](README.md)), [project-overview.md](project-overview.md),
  [repo-layout.md](repo-layout.md), [build-and-run.md](build-and-run.md),
  [architecture.md](architecture.md), [data-layer.md](data-layer.md),
  [configuration.md](configuration.md), [modules.md](modules.md), and this page.

If you change the code, keep these pages honest: the tree wins over any claim here, and
`python3 apps/codestyle/check-docs.py` checks the machine-readable facts in
[state.json](state.json).
