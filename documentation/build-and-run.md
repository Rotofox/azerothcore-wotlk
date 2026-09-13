# Building and Running

> The server built from this tree is **built, installed, and running**. The facts here are read
> from the build system, the installer scripts, and the live artifacts in `var/build/obj/` and
> `env/dist/`.

## Operator aliases (source of truth: `~/.bashrc` on the server host)

These shell aliases are the operator's canonical commands for this box. If they change, update this
section.

| Alias | Command |
|---|---|
| `wow-compile` | `./acore.sh compiler all` — clean full build |
| `wow-build` | `./acore.sh compiler build` — incremental build |
| `wow-update` | `git pull` here + `git pull` in `modules/mod-playerbots` |
| `wow-updatemods` | `git pull` every module dir under `modules/` |
| `wow-start` | `sudo bash /root/start.sh` — start both servers |
| `wow-stop` | `sudo tmux kill-server` |
| `wow-world` | `sudo tmux attach -t world-session` |
| `wow-auth` | `sudo tmux attach -t auth-session` |
| `wow-worldconf` | edit `env/dist/etc/worldserver.conf` |
| `wow-pbconf` | edit `env/dist/etc/modules/playerbots.conf` |
| `wow-ahconf` | edit `env/dist/etc/modules/mod_ahbot.conf` |

## Prerequisites

- **MySQL 8.x** (the installer scripts target MySQL 8.4 LTS; `deps/` finds the system MySQL via
  `FindMySQL.cmake` and requires >= 8.0). `apps/installer/includes/os_configs/ubuntu.sh` installs
  `mysql-server`; note that **a local commit commented out the MySQL download/install block** in
  that script (a local divergence — see
  [divergences-and-status.md](divergences-and-status.md)). MySQL is already installed and serving
  the live databases.
- **Toolchain**: CMake (the last build used CMake **3.28.3**), **clang** (default; `conf/dist/config.sh`
  sets `CCOMPILERC="/usr/bin/clang"`, `CCOMPILERCXX="/usr/bin/clang++"`) or **GCC ≥ 8.0** (enforced
  fatally in `src/cmake/compiler/gcc.cmake`; `GCC_EXPECTED_VERSION 8.0.0`; SSE2 is forced). MSVC,
  icc and mingw are also supported (`src/cmake/compiler/`).
- Common build deps: boost >= 1.74 (Linux, system), OpenSSL, readline, gperftools, ccache (optional).
  `deps/PackageList.txt` lists every vendored library and version. `./acore.sh install-deps` runs the
  per-OS package installation (see `apps/installer/includes/os_configs/`).
- A **WotLK 3.3.5a game client** (only needed if you extract client data yourself; see below).

## Build path A — the `acore.sh` dashboard (recommended by the project)

`./acore.sh` sources `apps/installer/main.sh` and shows a menu (`menu_items` in that file):

```
init | First Installation          install-deps | Configure OS dep
pull | Update Repository           reset | Reset & Clean Repository
setup-db | Install db only         compiler | Run compiler tool
module | Module manager (search/install/update/remove)
client-data | download client data from github repository (beta)
run-worldserver | execute a simple restarter for worldserver
run-authserver  | execute a simple restarter for authserver
test | Run test framework          docker | Run docker tools
version | Show AzerothCore version service-manager | Run authserver+worldserver in background
```

The flow is: `init` (or `install-deps` → `compiler`) configures and compiles; `client-data`
downloads the client data; `setup-db` creates/imports the databases; `run-worldserver` /
`run-authserver` / `service-manager` start the servers. `bin/acore*` are thin aliases over the same
installer functions (see `bin/README.md`: "Do not implement scripts here").

## Build path B — manual CMake

The canonical option table lives in `conf/dist/config.cmake` (user overrides can be put in
`conf/config.cmake`, which is `include()`d if present):

| Option | Choices (default) | Meaning |
|---|---|---|
| `SCRIPTS` | `none` / `static` / `dynamic` / `minimal-static` / `minimal-dynamic` (**static**) | Build the content scripts in `src/server/scripts` |
| `MODULES` | `none` / `static` / `dynamic` (**static**) | Build the modules in `modules/` |
| `APPS_BUILD` | `none` / `all` / `auth-only` / `world-only` (**all**) | Which server apps to build |
| `TOOLS_BUILD` | `none` / `all` / `db-only` / `maps-only` (**none**) | Which `src/tools` binaries to build |
| `BUILD_TESTING` | 0/1 (**0**) | Fetch googletest and build `src/test` unit tests (+ lcov/genhtml coverage targets) |
| `USE_COREPCH` / `USE_SCRIPTPCH` | 0/1 (**1**) | Precompiled headers (a `NOPCH` build disables them) |
| `WITH_WARNINGS` | 0/1 (**0**) | Show all warnings |
| `WITH_COREDEBUG`, `WITH_PERFTOOLS`, `WITH_DYNAMIC_LINKING`, `WITH_STRICT_DATABASE_TYPE_CHECKS`, `WITHOUT_METRICS`, `WITH_DETAILED_METRICS`, `WITHOUT_GIT`, `ENABLE_VMAP_CHECKS`, `CONFIG_ABORT_INCORRECT_OPTIONS` | 0/1 | Various feature switches (see the file for comments) |
| `WITH_SOURCE_TREE` | `no` / `flat` / `hierarchical` (**hierarchical**) | IDE source grouping |

Per-module/per-script/per-app/per-tool variables (e.g. `SCRIPTS_EVENTS`, `MODULES_*`, `WORLDSERVER`,
`DBIMPORT`, …) accept `default` / `disabled` / `static` / `dynamic` (or `enabled` for apps/tools).

A typical configure+build+install (matching the **known-good configuration** recorded in
`var/build/obj/CMakeCache.txt` from the last real build of this tree: CMake 3.28.3, clang++, build
type `Release`, `SCRIPTS=static`, `MODULES=static`, `TOOLS_BUILD=none`, `APPS_BUILD=all`, C++20,
PCH on, install prefix `env/dist`):

```bash
cmake ../.. -DCMAKE_BUILD_TYPE=Release -DSCRIPTS=static -DMODULES=static -DTOOLS_BUILD=none -DAPPS_BUILD=all -DCMAKE_INSTALL_PREFIX=$PWD/../../env/dist
cmake --build . --config Release -j $(nproc)
cmake --install . --config Release
```

Build order (root `CMakeLists.txt`): `add_subdirectory(deps)` → `src/common` → hook
`BEFORE_SRC_LOAD` → `src/` (adds `genrev`, `server`, and `tools` unless `TOOLS_BUILD=none`) →
**`modules/` only when worldserver is built** → hook `AFTER_SRC_LOAD` → `src/test` if
`BUILD_TESTING`. The revision header is generated by `src/cmake/genrev.cmake` into
`var/build/obj/revision.h` (git hash/date/branch baked into the binary banner).

## Products

- `worldserver` — game world server (links `modules scripts game gsoap readline gperftools` +
  `acore-core-interface`; see `src/server/apps/CMakeLists.txt`).
- `authserver` — login/realm server (links **only** `shared` — no game code).
- Tools, gated by `TOOLS_BUILD`: `dbimport` (DB updater), `map_extractor`, `vmap4_extractor`,
  `vmap4_assembler`, `mmaps_generator`.

All binaries install to `bin/` under the install prefix (`install(TARGETS ... DESTINATION bin)`),
i.e. `env/dist/bin/` with the default prefix — which is exactly what is sitting there in this tree.

## Configuration generation

On first run (or via the installer), the servers copy their `.conf.dist` templates to `.conf`:

- `src/server/apps/worldserver/worldserver.conf.dist` → `env/dist/etc/worldserver.conf`
- `src/server/apps/authserver/authserver.conf.dist` → `env/dist/etc/authserver.conf`
- Module configs: `modules/*/conf/*.conf.dist` → `env/dist/etc/modules/*.conf` (the
  "Modules config list" block in `modules/CMakeLists.txt` drives the installer).

See [configuration.md](configuration.md) for the key settings.

## Database setup

1. Create the databases: `data/sql/create/create_mysql.sql` creates `acore_auth`,
   `acore_characters`, `acore_world` (and grants to the `acore` MySQL user). mod-playerbots adds a
   fourth database, `acore_playerbots` (`modules/mod-playerbots/data/sql/playerbots/create/create_mysql.sql`).
2. Import base dumps: `data/sql/base/{db_auth,db_characters,db_world}/` (the squashed baseline).
3. Apply updates: the **`dbimport`** tool (`src/tools/dbimport/`, config
   `src/tools/dbimport/dbimport.conf.dist`) applies base + update SQL files; `./acore.sh setup-db`
   wraps this. Updates are controlled by the `Updates.*` settings in the server configs
   (`Updates.EnableDatabases` bitmask, `AutoSetup`, …). See [data-layer.md](data-layer.md).

## Client data (dbc/maps/vmaps/mmaps)

Two options:

1. **Download** (what the installer does): `./acore.sh client-data` →
   `inst_download_client_data` in `apps/installer/includes/functions.sh` downloads `data.zip`
   release **v16** from `https://github.com/wowgaming/client-data/releases/download/v16/data.zip`
   into the bin directory, unzips it, and writes `data-version` (`INSTALLED_VERSION=v16`).
   This is what produced `env/dist/bin/{dbc,maps,mmaps,vmaps,Cameras}`.
2. **Extract yourself**: run `apps/extractor/extractor.sh` against a 3.3.5a client installation
   using the built tools (`map_extractor`, `vmap4_extractor`/`vmap4_assembler`, `mmaps_generator`).
   Output lands in `var/extractors/` (which currently contains copies of `dbc/`, `maps/`, `mmaps/`,
   `vmaps/`, `Cameras/`).

At runtime the servers read these from `DataDir` (in `env/dist/etc/worldserver.conf` it is `"."`,
i.e. relative to the working directory where `worldserver` is started — normally `env/dist/bin`).

## Running the servers

Start `worldserver` (world port **8085**) and `authserver` (login port **3724**), from
`env/dist/bin` (or use the startup scripts):

- `apps/startup-scripts/src/` — `starter`, `run-engine`, `service-manager.sh`, `simple-restarter`,
  `migrate-registry.sh`, `conf.sh.dist` (+ `examples/`). Copies of these are installed into
  `env/dist/`. `./acore.sh run-worldserver` / `run-authserver` / `service-manager` wrap them.
  `service-manager.sh` runs both servers in the background with logging; `simple-restarter`
  auto-restarts a crashed server and supports GDB crash dumps.

On first start the servers apply pending DB updates (see [data-layer.md](data-layer.md)) and
generate their `.conf` files if missing. Both servers are **currently running** under tmux
(`world-session` / `auth-session`; see the operator aliases above).

## Docker

`docker-compose.yml` defines `ac-database` (MySQL 8.4), `ac-authserver` and `ac-worldserver`
services. `conf/dist/env.docker` provides the docker environment (`DATAPATH=/azerothcore/env/dist/data`,
`CTYPE=RelWithDebInfo`, `CSCRIPTS=static`, `AC_CCACHE=true`). `conf/dist/docker-compose.override.yml`
is a mostly-commented-out example of an override file. For mod-playerbots under Docker, the module
README's "Docker Installation" section (marked **experimental**) instructs you to clone the module
into `modules/` and mount it into the `ac-worldserver` container via a `docker-compose.override.yml`.

## Known-good configuration (evidence from this tree)

`var/build/obj/CMakeCache.txt` records the last real build:

```
CMAKE_BUILD_TYPE:STRING=Release
CMAKE_CXX_COMPILER:UNINITIALIZED=/usr/bin/clang++
CMAKE_INSTALL_PREFIX:PATH=/home/nexus-user/azerothcore-wotlk/env/dist
SCRIPTS:STRING=static
MODULES:STRING=static
TOOLS_BUILD:STRING=none
APPS_BUILD:STRING=all
```

The result is installed and **running**: `env/dist/bin/{worldserver,authserver}`,
client data v16, generated configs, and logs (`Server.log`, `Playerbots.log`, `Errors.log`,
`Auth.log`) are all present. Manage the running processes with the operator aliases above.
