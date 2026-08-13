# Repository Layout

Top-level map of the repo (state at HEAD `1507ab3f`, branch `Playerbot`). **Note: there is no
root `README.md`** — this `documentation/` folder is the entry point.

| Entry | What it is |
|---|---|
| `src/` | **C++ source.** `common/` (shared foundation libraries), `server/` (the two apps + game/database/scripts/shared code), `tools/` (DB importer and map/vmap/mmap extractors), `cmake/` (build helpers), `test/` (googletest unit tests). See [architecture.md](architecture.md). |
| `apps/` | **Bash "apps"** used by the installer/ops tooling, not the server: `installer/` (the `acore.sh` dashboard, `includes/functions.sh` downloads client data v16), `bash_shared/`, `startup-scripts/` (`starter`, `run-engine`, `service-manager.sh`, `simple-restarter` — these get copied into the install prefix), `docker/`, `ci/`, `compiler/`, `codestyle/`, `config-merger/`, `DatabaseSquash/`, `EnumUtils/`, `extractor/` (extract client data from a game client), `Fmt/`, `git_tools/`, `grafana/`, `test-framework/`, `valgrind/`, `whitespace_remover/`. |
| `conf/` | **Build/installer configuration**: `dist/config.cmake` (CMake option table, see [build-and-run.md](build-and-run.md)), `dist/config.sh` (installer paths: `SRCPATH`, `BUILDPATH=var/build/obj`, `BINPATH=env/dist`, `DATAPATH`, `ORIGIN_REMOTE=https://github.com/azerothcore/azerothcore-wotlk.git`, compilers default to `/usr/bin/clang` + `/usr/bin/clang++`), `dist/env.ac` (docker/compiler env: `CTYPE=RelWithDebInfo`, `CSCRIPTS=static`, `AC_CCACHE=true`), `dist/env.docker`, `dist/docker-compose.override.yml` (mostly commented-out example). |
| `data/` | **SQL data** for the databases (`base/` squashed dumps, `updates/`, `create/`, …). See [data-layer.md](data-layer.md). |
| `modules/` | **Module system**: `CMakeLists.txt` (module discovery/build + `MOD_PLAYERBOTS` special case), `ModulesLoader.cpp.in.cmake` (generates `AddModulesScripts()`), `ModulesScriptLoader.h`, `create_module.sh`, `how_to_make_a_module.md` — plus the 7 installed `mod-*` module clones (gitignored; see [modules.md](modules.md)) and the broken `TrackingModule.h/.cpp` WIP (see [divergences-and-status.md](divergences-and-status.md)). |
| `deps/` | **Vendored third-party libraries**: `boost/`, `mysql/`, `openssl/`, `recastnavigation/` (mmaps), `g3dlite/`, `gsoap/`, `jemalloc/`, `bzip2/`, `zlib/`, `fmt/`, `argon2/`, `gperftools/`, `SFMT/`, `stdfs/`, `threads/`, `utf8cpp/`, `readline/`, `libmpq/`, `jsonpath/` + `acore/` (AzerothCore's own tooling: `cmake-utils/`, `bash-lib/`, `joiner/`, `mysql-tools/`). `deps/PackageList.txt` documents versions/licenses. Note all four `deps/acore/` tooling dirs (`cmake-utils/`, `bash-lib/`, `joiner/`, `mysql-tools/`) are git **subrepos** — each has a `.gitrepo` marker pinning an upstream commit (e.g. `azerothcore/cmake-utils` @ `1589c53`, method `merge`). `deps/CMakeLists.txt` gates each dep on what is being built. |
| `env/` | **Installed runtime / install prefix** (gitignored except `.gitkeep`): `env/dist/bin/` (compiled `worldserver` + `authserver`, extracted client data v16, `data-version`, logs `Server.log`/`Playerbots.log`/`Errors.log`/`Auth.log`), `env/dist/etc/` (generated `worldserver.conf`, `authserver.conf`, `modules/*.conf` + `.conf.dist` templates), `env/dist/logs/`, the startup-script package copied from `apps/startup-scripts/src/`, and `env/user/` (per-user overrides, empty). |
| `var/` | **Build scratch**: `var/build/obj/` (the CMake build directory — `CMakeCache.txt` records the last real build: CMake 3.28.3, clang++, `Release`, prefix `env/dist`, `SCRIPTS=static`, `MODULES=static`, `TOOLS_BUILD=none`, `APPS_BUILD=all`), `var/ccache/`, `var/docker/`, `var/extractors/` (extractor output: `dbc/`, `maps/`, `mmaps/`, `vmaps/`, `Cameras/`). |
| `bin/` | **Bash alias scripts** (`acore`, `acore-compiler`, `acore-db-export`, `acore-db-pendings`, `acore-import-changelogs`, `acore-installer`). `bin/README.md` says: *"Do not implement scripts here"* — they are thin wrappers over `apps/`. |
| `doc/` | **Existing docs**: `doc/Logging.md` (the logging system) and `doc/changelog/` (release changelogs, `master.md` + `pendings/`). This `documentation/` folder complements, not replaces, these. |
| `acore.sh` | Dashboard entry point → sources `apps/installer/main.sh` (menu: init, install-deps, compiler, module, client-data, run-worldserver, run-authserver, test, docker, service-manager, …). See [build-and-run.md](build-and-run.md). |
| `install.sh` | Thin wrapper that sources the installer (`apps/installer/includes/includes.sh`). |
| `CMakeLists.txt` | Top-level CMake: loads `conf/`, `deps/`, `src/common`, `src/`, then `modules/` (only when worldserver is built), then `src/test` if `BUILD_TESTING`. See [build-and-run.md](build-and-run.md). |
| `PreLoad.cmake` | Extension point; currently inert (only a commented-out Windows example for forcing `CMAKE_INSTALL_PREFIX`). |
| `docker-compose.yml` | Docker services `ac-database` (MySQL 8.4), `ac-authserver`, `ac-worldserver` per upstream convention. See [build-and-run.md](build-and-run.md#docker). |
| `flake.nix` / `flake.lock` | Nix flake for reproducible environments (optional). |
| `.github/` | CI workflows, including the fork's `core-build-playerbots.yml` (builds the `Playerbot` branch with clang/gcc on Ubuntu) and `import_pending.yml` (imports pending DB updates). |
| `.devcontainer/` | VS Code devcontainer (`devcontainer.json` + `docker-compose.yml`). |
| `AUTHORS`, `LICENSE` | Project credits and the AGPL-3.0 license. |
| `pull_request_template.md`, `.git_commit_template.txt`, `.vscode/`, `.editorconfig`, `.gitattributes`, `.suppress.cppcheck` | Contribution/editor tooling. |
| `adws/`, `justfile`, `.env`, `.env.sample`, `requests/`, `specs/` | **Agent tooling, NOT server code.** `adws/` (SSSF/AI-workflow data, gitignored), `justfile` (SSSF recipes), `.env*` (API keys for agent tooling, gitignored), `requests/` and `specs/` (agent docs/planning). Ignore them when working on the emulator. |

## Directory depth: `src/`

- `src/common/` — shared foundation (Asio, Configuration, Cryptography, DataStores, Logging,
  Metric, Navigation, Collision, Threading, IPLocation, Encoding, Utilities, Debugging).
- `src/server/` — `apps/` (worldserver + authserver), `shared/` (DataStores, Network, Packets,
  Realms, Secrets), `database/` (Database worker pools incl. `PlayerbotsDatabase`, Logging,
  Updater), `game/` (the game server subsystems), `scripts/` (content scripts).
- `src/tools/` — `dbimport`, `map_extractor`, `vmap4_extractor`, `vmap4_assembler`, `mmaps_generator`.
- `src/cmake/` — `genrev.cmake` (revision header), `compiler/` (gcc/clang/msvc/icc/mingw settings),
  `macros/` (e.g. `ConfigureModules.cmake`), `googletest.cmake`, `showoptions.cmake`.
- `src/test/` — googletest-based unit tests (`common/`, `server/`, `mocks/`).

See [architecture.md](architecture.md) for what each `src/server/game/` subsystem does, and
[data-layer.md](data-layer.md) for the `data/` tree.
