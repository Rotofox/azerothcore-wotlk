# AGENT HANDOFF — Fury System + NexusFrames

> **Read this first.** This file gets a new agent up to speed on the **Fury** feature (account-wide kill-based progression with permanent stat rewards) and its **NexusFrames** UI addon. Everything here was verified against this repo during design; trust it, but re-verify line numbers when you code.

---

## 1. What this is

An **account-wide progression system**: every XP-eligible creature kill grants Fury points (party-shared, as if each member killed alone). Fury feeds an account-leveled ladder (**max level 300**, threshold `100×n`, total 4.5M). Each level grants **permanent account-wide stat bonuses** (haste %/level, flat AP+SP per 5, class-primary per 10, extensible item rewards). A client addon (**NexusFrames**, shipped inside `patch-4.MPQ`) shows a micro-button → tabbed window → Fury tab (progress bar + scrollable multi-line reward list + top-center level-up popup).

**Authoritative design:** `specs/fury-nexusframes-design.md` — every decision is locked and confirmed by the engineer. Do not re-litigate; implement as specified.

---

## 2. Where to look first (in priority order)

| Path | What |
|---|---|
| `specs/fury-nexusframes-design.md` | **The design spec** — read this first, fully. |
| `documentation/` | Project onboarding docs (what this fork is, build/run, architecture, modules, data layer). Useful context. |
| `client-resources/README.md` | The client-patch pipeline (DBC patches, `patch-4.MPQ`, pack instructions, WDB-cache rule). **The NexusFrames addon source must land in `client-resources/NexusFrames/`.** |
| `modules/mod-random-enchants/` | **The module reference** — same shape the Fury module must follow (`src/`, `conf/`, `data/sql/{db-auth,db-world}/`, loader, tools/). It implements the quality+enchant system this fork runs. |
| `adws/` + `adws/adw_sssf_config/sssf.config.yaml` | The software factory (ADWs + agent roster). Build the module through it (see §5). |
| `requests/` | Prior factory prompts (specs, build, fixes) — see how runs were prompted. |

---

## 3. Key verified facts (code locations)

### Hooks / APIs the module needs
- `PlayerScript::OnPlayerKilledByCreature(Player*, Creature*)` — `src/server/game/Scripting/ScriptDefines/PlayerScript.h:255`
- `PlayerScript::OnPlayerSave(Player*)` — `PlayerScript.h:350` (fires on the 15-min save cadence + logout; `PlayerSaveInterval = 900000` — WorldConfig.cpp:160)
- Haste %: `ApplyPercentModFloatValue(UNIT_FIELD_BASEATTACKTIME+hand, pct)` + `ApplyPercentModFloatValue(UNIT_MOD_CAST_SPEED, pct)` — `src/server/game/Entities/Unit/Unit.cpp:17160/17173`
- Flat AP: `HandleStatModifier(UNIT_MOD_ATTACK_POWER[, _RANGED], TOTAL_VALUE, …)` — unit mods at `Unit.h:164–165`, percent types `BASE_PCT=1`/`TOTAL_PCT=3` at `Unit.h:128–130`
- Flat SP: `Player::ApplySpellPowerBonus(int32, bool)` — `Player.h:1945` (same API the working matrix SP enchants use)
- Flat stats: `ApplyStatBuffMod(STAT_*, float, bool)` — proven, used by the core enchant path at `PlayerStorage.cpp:4445+`
- Account id: `WorldSession::GetAccountId()` — `WorldSession.h:268`
- Boss detection: `CREATURE_FLAG_EXTRA_DUNGEON_BOSS` (0x10000000, set dynamically) — `CreatureData.h:73`
- XP internals for reference: `GiveXP` Player.cpp:2385 · `RewardPlayerAndGroupAtKill` Player.cpp:12764 · `RewardHonor` Player.cpp:6118

### Addon-channel data transport (client ⇄ server)
- Server handler: `AddonChannelCommandHandler` — `src/server/game/Chat/Chat.cpp:1050`; protocol = message starts `"AzerothCore\t"` + opcode + 4-char counter + command; dispatch at `ChatHandler.cpp:288`; config `AddonChannel = true` — WorldConfig.cpp:146
- **Client receive pattern:** 3.3.5 has **no** `RegisterAddonMessagePrefix`/`CHAT_MSG_ADDON` (those are 4.1+/Cataclysm). The addon sends via `SendAddonMessage` and receives via `CHAT_MSG_WHISPER` with the LANG_ADDON flag, parsing the body.
- The addon queries the `.fury` command on window open; the server pushes level-up updates; no per-kill polling.

### Gotchas that bit us (learn these)
- **MySQL 8 reserved words:** a column named `rank` in a `mysql -e` query silently fails — qualify/backtick or rename.
- **Client WDB cache:** after any server-side *item stat* change, players must delete `Cache\WDB` with the game **closed** or tooltips show stale stats (bit us twice). Not relevant to Fury (no item-template changes) unless item rewards are added later.
- **SP% is impossible in this fork** (no `SPELL_AURA_MOD_SPELL_POWER_PCT`) — hence AP and SP are both **flat** per the engineer's rule.
- **Modules are gitignored clones** — never commit/push/pull (engineer's standing rule; the factory runs with `--no-commit`).
- **The engine's own lessons:** the pilot-coverage lesson (surface what a run actually delivered) and the "quality color is client-template-bound" lesson (why items are real rows).

---

## 4. Where the deliverables go

| Deliverable | Location |
|---|---|
| Server module | `modules/mod-fury/` (new; modeled on `modules/mod-random-enchants/`) — SQL: `data/sql/db-auth/` for `account_fury` (acore_auth), `data/sql/db-world/` if any world data |
| Addon source | **`client-resources/NexusFrames/`** (`NexusFrames.toc` + `NexusFrames.lua`) — per the engineer's explicit instruction |
| Packed addon | inside `patch-4.MPQ` at `Interface\AddOns\NexusFrames\` (same archive as `DBFilesClient\Item.dbc` + `DBFilesClient\SpellItemEnchantment.dbc`) |
| Design | `specs/fury-nexusframes-design.md` |

---

## 5. The build plan

1. **Server module via the factory** (recommended): write the prompt in `requests/`, launch
   `uv run adws/adw_simple_sdlc.py requests/<slug>.md --no-commit` (the `--no-commit` flag was added deliberately — the engineer never commits). Default roster. The reviewer is the substantive gate.
2. **Addon built directly** (it's Lua + MPQ packaging, not factory-shaped): write `client-resources/NexusFrames/`, then instruct the engineer to pack it into `patch-4.MPQ` at `Interface\AddOns\NexusFrames\` (MPQ editor; addon changes need a client relaunch).
3. **Config:** `env/dist/etc/modules/` — the running configs; the module's `conf/*.conf.dist` ships defaults the installer copies.

---

## 6. Open build-time items (from the design spec §5)

1. Exact addon-channel framing constants + whether module commands route through `AddonChannelCommandHandler::_ParseCommands`.
2. Micro-bar anchor frame name + micro-button textures.
3. `NexusFrames.toc` `## Interface` value (30300 for 3.3.5a — confirm).
4. `OnPlayerSave` fires on logout (it fires from the save path — confirm).
5. Ranged AP mod + the grey-level formula for the XP-eligible gate.
6. `ApplySpellPowerBonus` behavior for flat SP.

---

## 7. Standing project facts the next agent needs

- **This fork:** AzerothCore WotLK 3.3.5a (client 12340) + Playerbot branch; modules are gitignored clones; `env/dist/` is the installed server (built, run, live).
- **The factory:** `adws/` ADWs (`adw_simple_sdlc.py` is the full SDLC; `--no-commit` skips the 3 commit phases); roster `adws/adw_sssf_config/sssf.config.yaml`; trace DB `adws/adw_data/sssf.db`; prompts in `requests/`.
- **Existing custom systems** (already live): the quality+enchant module (`modules/mod-random-enchants/` — variant ladder `mod_re_item_variants` in acore_world, matrix enchants in `spellitemenchantment_dbc`, class pools, `mod_re_rates`), and the client patches in `client-resources/`. Fury sits **on top** of these.
- **Server restarts** are required after item-template/SQL data changes; the module's own tables are read per-roll.
