# AGENT HANDOFF — azerothcore-wotlk (Playerbot fork) full state

> **Read this first.** This file gets a new agent up to speed on the whole project — the custom
> progression/loot systems, the client addon, the recent core update, the operational state, and the
> QoL module.
> Last updated: **20/08/2026** (maintenance: server status + custom-table list corrected).
> Design specs live in `specs/`; onboarding docs in `documentation/`; client patch pipeline in
> `client-resources/README.md`.
>
> ⚠️ **This is a dated snapshot, not the source of truth.** For the current state use
> [README.md](README.md) and the other pages in this folder (and the live tree). Where this file
> disagrees, those pages win — fix them, and treat the systems/lessons sections below as historical
> detail that is still useful.

---

## 1. What this is

An **AzerothCore WotLK 3.3.5a** server on the **Playerbot branch**, with custom systems layered on top:

1. **Fury** — account-wide kill-based progression (module `mod-fury`) + **NexusFrames** client addon.
2. **Item Quality + Scaled Random-Enchant system** (module `mod-random-enchants`) — variant quality
   upgrades, a scaled enchant matrix, spec-aware stat pools, empower-not-rewrite, vendor-price scaling.
3. **mod-multibot-bridge** — a client⇄server bridge addon for MultiBot-Chatless (added 17/08/2026).
4. **mod-qol** — quality-of-life: flight-path map pins with click-to-teleport (addon
   `QoLFlightPaths`), hunter QoL (pet fed, Auto Shot while moving/point-blank), no reagents,
   autoattack-on-cast, account-wide taxis, GM custom map points (added 18/08/2026). **See §9.**
5. Stock modules: `mod-account-mounts`, `mod-ah-bot`, `mod-aoe-loot`, `mod-autobalance`,
   `mod-no-hearthstone-cooldown`, `mod-playerbots`.

**Authoritative designs:** `specs/fury-nexusframes-design.md` (Fury v1), `specs/fury-nexusframes-v2-design.md`
(spec-aware roles, empower, prices, minimap button), `specs/db8e1683_item-quality-random-enchants.md`
(quality/enchant module), `specs/qol-module-design.md` (QoL module). The v2 build plan is
`specs/6fb5d859_fury-nexusframes-v2.md`.

---

## 2. Fury system + NexusFrames addon (works)

- **`modules/mod-fury/`** — `OnPlayerCreatureKill` → XP-eligible (non-grey, `Acore::XP::GetGrayLevel`) →
  `(victimLevel × 5 + 10) × bossMult` per party member → in-memory per-account cache (`account_fury` in
  **acore_auth**, lazy insert) → level-up → reward deltas to **all online account characters** →
  immediate DB write on level-up + `OnPlayerSave` persistence. Account-wide ladder max **300**
  (`threshold(n) = 100n`, total 4,515,000). Rewards: +0.1% haste/level, flat AP+SP per 5 (both flat —
  no SP% in this fork), class-primary per 10 (now **spec-aware**).
- **`client-resources/NexusFrames/`** — the original standalone Fury addon; it now ships **folded
  into the `NexusServer` addon** (`Interface\AddOns\NexusServer\modules\fury\`), so the standalone
  files must **not** be packed alongside NexusServer (duplicate frame names collide). See
  `client-resources/latest-mpq-patch/README.md`. UI: minimap button (LibDBIcon port + bundled
  TGA `NexusFramesMinimap.tga`), compact draggable bar, tabbed window, gain flash + combat-log,
  level-up popup, tier-colored reward list.
- **Transport:** server addon channel — receive via **`CHAT_MSG_ADDON`** (3.3.5 HAS the event;
  `RegisterAddonMessagePrefix` is Cata-only). Wire: `"AzerothCore\t"` + opcode + 4-char counter + payload.
- Config: `Fury.*` in `env/dist/etc/modules/fury.conf` (live) / `modules/mod-fury/conf/fury.conf.dist`.
- **History lesson:** the addon's invisible-button saga was caused by the factory using
  **`UIPanelWindowTemplate` — which does NOT exist in 3.3.5** (Vanilla-era, removed); `CreateFrame` with
  an unknown template halts the file at load, killing every frame created after it. All windows/frames
  use plain `CreateFrame` + backdrops. Do not reintroduce unknown templates.

---

## 3. mod-random-enchants (works, v2 features live)

- Quality roll over `{STAY} ∪ tiers` → variant swap to real `item_template` rows (entry ≥ 1,000,000),
  scaled stats ×1.75^tier; enchant matrix (`spellitemenchantment_dbc` mirror, ids 100000–102624) rolls
  into PROP slots 7–9, chained 70/65/60%, **no duplicate stat across the three rolls** (new gate).
- **Spec-aware (v2):** `getArchetype` resolves `mod_re_spec_archetype` (TalentTab id) → class table →
  hard-coded; 5 roles (PHYSICAL/AGILITY/CASTER/HEALER/TANK); feral druid form-aware (bear → TANK pool).
  Kill-switch `RandomEnchants.SpecAware = 1`.
- **Empower-not-rewrite (v2):** `swapToVariant` preserves the random property/suffix + enchants; suffix
  items get a **rank boost** via `mod_re_suffix_boost` (ladder generated from the client DBCs by
  `tools/generate_suffix_boost.py`); capped families logged, not invented.
- **Suffix-factor fix:** `generate_variants.py` now **preserves RandomSuffix** on suffix-bearing variants
  (else relog zeroes the suffix factor → stats vanish). Regenerate 003 + reapply when variants change.
- **Vendor prices:** `TIER_PRICE_MULT` scales Buy/SellPrice per tier in `generate_variants.py`.
- **Test-loot commands:** `.re item [entry]` (create + roll; random eligible base if omitted) and
  `.re crate [count]` (Mystery Crate, entry **9000001** — SQL `006_mod_re_crate.sql`; right-click opens
  via `ItemScript::OnUse`, dummy use-spell 44755 never casts).
- Config: `RandomEnchants.*` in `env/dist/etc/modules/random_enchants.conf`.
- **API rename after the core update:** the new core uses `HandleStatFlatModifier(UnitMods,
  UnitModifierFlatType, float, bool)` and stat buffs go through `HandleStatFlatModifier(UNIT_MOD_STAT_X,
  TOTAL_VALUE, …)` — `ApplyStatBuffMod`/`HandleStatModifier` are gone.

---

## 4. mod-multibot-bridge (added 17/08/2026)

- `modules/mod-multibot-bridge/` — server module for the **MultiBot-Chatless** client addon
  (structured addon-message bridge; `MBOT` protocol). Pairs with **current `mod-playerbots` master**
  (it includes `src/Db/PlayerbotRepository.h` etc.). Config `env/dist/etc/modules/MultiBotBridge.conf`.

---

## 5. The 17/08/2026 core update (what happened, what to know)

The core was rebased onto `origin/Playerbot` (now **efe123fab**; the `liyunfan1223/*` repos were
transferred to the **`mod-playerbots`** GitHub org — same repos, redirect works). ~2,987 upstream
commits landed. The 5 local doc/asset commits were replayed on top (backup branch
`backup/Playerbot-pre-core-pull` holds the pre-rebase state). **Nothing has been pushed.**

Consequences handled:

1. **Module API renames** — fixed in `mod-fury`/`mod-random-enchants` (see §3; `HandleStatModifier` →
   `HandleStatFlatModifier`; `ApplyStatBuffMod` → `HandleStatFlatModifier(UnitMods(UNIT_MOD_STAT_START +
   uint32(stat)), TOTAL_VALUE, …)`). Both modules compile + run.
2. **DB updates** — the auth DB's RBAC update chain was retried to completion by worldserver. All DBs
   are up to date: auth (12 new / 10 archived), characters (9/19), world (666/2204), playerbots (31/0).
3. **Maps/Vmaps/Mmaps re-extraction** — the new core bumped the VMap format; old data was incompatible.
   Extracted fresh with the new-core tools: `map_extractor`, `vmap4_extractor`, `vmap4_assembler
   Buildings vmaps`, `mmaps_generator` (needs `mmaps-config.yaml` — ships at
   `src/tools/mmaps_generator/mmaps-config.yaml`, pass `--config`; `dataDir: "./"`). Fresh output copied
   into `env/dist/bin/{maps,vmaps,mmaps}`. Build the tools with **`CTOOLS_BUILD=all ./acore.sh compiler
   build`** (valid values: none|all|db-only|maps-only).
4. **Config refresh** — `worldserver.conf`, `modules/playerbots.conf`, `modules/random_enchants.conf`
   were rebuilt from their current `.dist` (all keys + comments) with **custom values preserved**;
   originals backed up as `*.bak`. **New keys are marked `# NEW-17/08/2026` directly above the key.**
   One flagged oddity: `PacketSpoon.Policy = 0` in the old worldserver.conf looks like a typo for
   `PacketSpoof.*` (harmless; unknown keys are ignored).
5. **Client data copy** at `~/tmp/wowclient/` (the WoW MPQs) — used for extraction; can be deleted to
   reclaim ~13 GB once mmaps are confirmed good (keep the extracted `maps/ vmaps/ mmaps/` copies in
   `env/dist/bin/`).

---

## 6. Operational facts

- **Aliases** (in `~/.bashrc`): the canonical list now lives in
  [build-and-run.md § Operator aliases](build-and-run.md#operator-aliases-source-of-truth-bashrc-on-the-server-host)
  (`wow-compile`, `wow-build`, `wow-update`, `wow-updatemods`, `wow-start`, `wow-stop`, `wow-world`,
  `wow-auth`, `wow-worldconf`, `wow-pbconf`, `wow-ahconf`).
- **Build config:** `conf/config.sh` doesn't exist (defaults used). `CTOOLS_BUILD=all` enables the
  extractor tools. `TOOLS_BUILD` (CMake) is none|all|db-only|maps-only.
- **DBs:** MySQL 8.0.46, creds `acore`/`acore`; databases `acore_auth`, `acore_characters`,
  `acore_world`, `acore_playerbots`.
- **Custom tables (live):** `account_fury` (acore_auth); `mod_re_rates`, `mod_re_item_variants`,
  `mod_re_spec_archetype`, `mod_re_suffix_boost`, `mod_re_class_archetype`, `mod_re_pool_rates`
  (acore_world). QoL: `account_taxi` (acore_auth), `mod_qol_pins` + `mod_qol_points`
  (acore_world). Crate item entry **9000001**.
- **Server state:** worldserver + authserver **running** — restarted 19/08/2026 00:23 local, so the
  merged configs are live (the confs were merged while the previous instance ran with defaults).
- **WDB cache:** after any item-template or DBC change players must delete `Cache\WDB` (game closed).
  The QoLFlightPaths addon ships in patch-4.MPQ (see §9.7).

---

## 7. Standing gotchas (learned the hard way)

- **Modules are gitignored clones — never commit/push/pull them.** Only the core repo (this one) is
  git-tracked; `git pull`/rebase happens here, module clones are updated by the engineer via
  `git -C modules/<x> pull`.
- **MySQL 8 reserved words:** backtick identifiers in ad-hoc SQL (a column named `rank` fails silently).
- **SP% is impossible** in this fork (no `SPELL_AURA_MOD_SPELL_POWER_PCT`) — flat AP/SP only.
- **3.3.5 addon API facts:** `CHAT_MSG_ADDON` exists (receive addon messages; the prefix-split happens
  client-side — the event arg is the body WITHOUT the "prefix\t" envelope; whispers carry it WITH);
  `RegisterAddonMessagePrefix` is Cata-only; `CombatLog_Print_Combat_Message` doesn't
  exist — write via `COMBATLOG:AddMessage`; micro-button textures are `UI-MicroButton-<Name>-Up/-Down`
  + shared `UI-MicroButton-Hilight` (one 'l'); `UIPanelWindowTemplate` does NOT exist.
- **Lua scoping trap (bit us):** a `local function` referenced by a function defined EARLIER in the
  file binds to the **global** (nil) and crashes at runtime — declare helpers before their callers.
- **DBC coordinate convention:** in WoW world/DBC coords **X runs north-south (north = +X), Y runs
  east-west (west = +Y)**; the world map renders with north up. `GetCurrentMapAreaID()` returns
  **WorldMapArea row id + 1** (Dun Morogh map → 28 = row 27) — the same id space ProjectEbonhold's
  `worldMapRects` keys. See §9.6.
- **`sWorldMapAreaStore` extern is commented out in DBCStores.h** ("use Zone2MapCoordinates...") —
  the symbol still exists; declare `extern DBCStorage<WorldMapAreaEntry> sWorldMapAreaStore;` in a
  module to use it.
- **MPQ packing is manual — agents cannot pack MPQs.** The agent's job ends at generating files into
  `client-resources/` and documenting the layout; the operator packs `patch-4.MPQ` on the client
  machine with an MPQ editor. Never write an agent-facing step that runs an MPQ tool.
- **Factory (`adws/`):** the deterministic test phase is a placeholder echo — "done" = coherent code +
  reviewer approval, never a compile. Runs use `--no-commit`.
- **Line numbers** in specs/docs are pre-verified but drift — re-verify against the live tree.

---

## 8. Where everything lives

| Path | What |
|---|---|
| `specs/fury-nexusframes-design.md` | Fury v1 design (authoritative, locked) |
| `specs/fury-nexusframes-v2-design.md` | v2: spec matrix, empower, prices, minimap button, lessons |
| `specs/db8e1683_item-quality-random-enchants.md` | Quality/enchant module design |
| `specs/6fb5d859_fury-nexusframes-v2.md` | v2 factory plan |
| `specs/qol-module-design.md` | QoL module design + as-built notes (§4.7) |
| `documentation/` | Onboarding: build-and-run, architecture, data-layer, configuration, repo-layout |
| `client-resources/README.md` | DBC patch pipeline (Item.dbc, SpellItemEnchantment.dbc) + MPQ packing |
| `client-resources/NexusFrames/` | Addon source (lua + toc + tga) |
| `modules/mod-fury/`, `modules/mod-random-enchants/`, `modules/mod-multibot-bridge/` | Custom modules |
| `requests/`, `app_docs/` | Factory prompts + write-ups |
| `adws/` | The software factory (SSSF) |

---

## 9. QoL module — mod-qol + QoLFlightPaths addon (added 18/08/2026)

**Design:** `specs/qol-module-design.md` (incl. §4.7 as-built notes). Server module
`modules/mod-qol/`, client addon `client-resources/QoLFlightPaths/` (ships in patch-4.MPQ at
`Interface\AddOns\QoLFlightPaths\`), one small **core patch** in `src/server/game/Spells/Spell.cpp`.

### 9.1 Feature list (verified working unless noted)

| Feature | Where | Notes |
|---|---|---|
| Crate item 9000001 icon | client Item.dbc row (displayid 7925) via `generate_item_dbc_patch.py` | client-side only |
| Auto Shot castable while moving + point-blank | core patch (Spell.cpp, 3 spots: ~3563, ~5818, ~7144 + CombatHandler.cpp) | **requires core rebuild** |
| Hunter pets always well-fed | mod-qol (`QoLWorldScript::OnUpdate` + `QoLPetScript`) | happiness pinned to max |
| Pet/guardian stats +50% (HP, armor, damage) | SQL + core patch (`Pet.cpp`, 8 spell scaling scripts) | all pets incl. temporary guardians — §9.8 |
| Offensive spells auto-trigger autoattack | mod-qol (`QoLAllSpellScript::OnSpellCast`) | damage-effect/negative predicate + force/exclude lists (Bestial Wrath 19574) |
| No reagent costs | mod-qol (`OnStartup` zeroes `SpellInfo::Reagent[]`) | + client Spell.dbc tooltip cleanup (`generate_spell_dbc_patch.py`) |
| World-map pins: flight paths / innkeepers / dungeon entrances / custom points, click-to-teleport | mod-qol server + QoLFlightPaths addon | the big one — §9.3–9.5 |
| Account-wide taxi discovery | mod-qol (`account_taxi` in acore_auth) | max-character normalization at startup; applied on login + character create |
| GM custom points (`.createpoint` / `.deletepoint` / `.listpoints`) | mod-qol (`QoLCommandScript` + `mod_qol_points` table) | live PINADD/PINREM push |

Auto settlements/dungeons are **off by default** (config `QoL.FlightPath.Settlements/Dungeons = 0`).

### 9.2 The core patch (Auto Shot)
Three QoL edits in `Spell.cpp`, all exempting spell 75 (Auto Shot): the cast-completion moving check,
the cast-start auto-repeat moving check, and the min-range `TOO_CLOSE` branch. The DBC already has min
range 0 for Auto Shot (SpellRange 114 = 0/35) — only the server's per-shot `minRange + meleeRange`
check needed the exemption. Keep this patch if the core is ever rebased.

**Starting the auto-attack while moving (CombatHandler.cpp).** The `Spell.cpp` edits only make the
server *accept* an Auto Shot cast that starts while the player runs — they keep a running auto-repeat
alive. They cannot make it *start*: the 3.3.5 client will not initiate an auto-repeat ranged cast while
the player is moving (blizzlike — "you must stop long enough for the Auto Shot to go off"; same rule the
fork's `MultiBotBridge` encodes as `(castTime || IsAutoRepeatRangedSpell()) && isMoving()`). So pressing
the Auto Shot ability mid-run yields no cast packet at all, and the auto-attack only begins once the
player halts.

The one attack signal the client *does* send while running is **`CMSG_ATTACKSWING`** (melee auto-attack
is usable on the move), so `WorldSession::HandleAttackSwingOpcode` now calls a file-local
`StartRangedAutoAttack(player, victim)` after the melee request: if the player has no auto-repeat running,
has a ranged weapon in the ranged slot, knows a spell with `IsAutoRepeatRangedSpell()` (Auto Shot / wand
Shoot), and the victim is inside that spell's max range, it casts that spell server-side
(`TRIGGERED_NONE`, so the normal cast path + the `Spell.cpp` exemptions apply). `Unit::_UpdateAutoRepeatSpell`
then drives every following shot per the ranged swing timer. Consequences:
- right-click / Attack a target in ranged range **while running** now starts Auto Shot (it persists while kiting);
- the `GetCurrentSpell(CURRENT_AUTOREPEAT_SPELL)` guard means repeat attack requests never fire a free extra shot;
- out-of-range targets and melee-only classes are untouched (pure melee request, as before);
- the Auto Shot **ability button** pressed mid-run still does nothing — that is the client withholding the
  cast, and no server-side change can recover a packet the client never sends.

### 9.3 The map addon — how it works
- **Transport:** addon channel, prefix `QOLFP`. Client sends via `SendAddonMessage("QOLFP", body, "WHISPER", UnitName("player"))`; server receives through `PlayerScript::OnPlayerCanUseChat` (the lang==LANG_ADDON path; `Player::Whisper` at Player.cpp:9678 calls the hook). Server replies via `ChatHandler::BuildChatPacket(data, CHAT_MSG_WHISPER, LANG_ADDON, player, player, wire)` + `SendDirectMessage`.
  **CHAT_MSG_ADDON delivers the body WITHOUT the "QOLFP\t" envelope; the CHAT_MSG_WHISPER fallback carries it WITH.** The addon handles both (dedup).
- **Protocol:** `REQ~<cont 1..4>` (request a continent's pins, chunked) · `TP~<cat>~<pinId>` · server→client `DATA~<cont>~<idx>~<total>~<pins>` · `DISC~<pinId>` (flight discovered) · `TPOK/TPERR` · `PINADD/PINREM` (live custom-point changes). Pin wire = `id~cat~mapId~x~y~z~disc~cont~rowId~faction~name`.
- **Coordinate model (critical):** in WoW world/DBC coords **X = north-south (north +), Y = east-west (west +)**. The displayed map is looked up by **`GetCurrentMapAreaID()` = WorldMapArea row id + 1** (Dun Morogh → 28 = row 27; same id space ProjectEbonhold's `worldMapRects`). `ZoneData.lua` = `QOLFP_MAPS[key] = { k(1 cont/2 zone), c(parent cont), left, right, top, bottom }` generated from WorldMapArea.dbc. Pin→map fraction: `relX = (pin.y - left)/(right - left)`, `relY = (pin.x - top)/(bottom - top)`.
- **Views:** zone (pin.rowId+1 == GetCurrentMapAreaID), continent (`pin.cont == box.c`), world/planet (`GetCurrentMapContinent()==0` → all Azeroth continents via `QOLFP_WORLD` = Astrolabe's world box + per-continent offsets), cosmic (`==-1` → pins hidden — UpdateButtons hides all when no valid box).
- **Faction:** server sends `faction` (0 both / 1 alliance / 2 horde) computed from `TaxiNodes.MountCreatureID` ([0]=Horde, [1]=Alliance; 32981=DK mount → both). Client filters with `UnitFactionGroup("player")` — same pattern as ProjectEbonhold's `IsFactionAllowed`.
- **Icons per category:** flight = `Interface\Minimap\Tracking\FlightMaster` (greyed until discovered), settlement = `Innkeeper`, dungeon/raid = bundled `assets\wo_icon_raid.blp`, custom = `INV_Misc_QuestionMark`.
- **Junk filter:** TaxiNodes.dbc is full of quest/dev/transport nodes ("Quest - …", "CC Prologue - GT - …", "Flavor - …", "Generic, World Target …", "Transport, …", "Programmer Isle"). `IsJunkTaxiNode()` in `qol_flightpath.cpp` strips them server-side (name-prefix/needle blacklist).
- **Pin rendering:** buttons parented to `WorldMapButton`, frame level = `WorldMapFrame:GetFrameLevel() + 2015` (Questie's proven value — the map's scroll container sits at ~2000). Map closes on successful teleport (Ebonhold UX).

### 9.4 Account-wide taxis (F8)
`acore_auth.account_taxi` (account_id, node_id). On startup the module scans `characters.taximask`
(space-separated uint32 words) and seeds each account from the character with the **most** discovered
nodes; `OnPlayerLearnTaxiNode` grows it live (SMSG_NEW_TAXI_PATH + `DISC~` push to online
account-mates); applied in `OnPlayerLogin` and `OnPlayerCreate`.

### 9.5 Custom points (`.createpoint`)
`mod_qol_points` table (id, name, map, x, y, z, created_by). `QoLCommandScript` registers the
top-level commands; creating/removing broadcasts PINADD/PINREM to all online players; teleports are
free-for-all (gated by the shared cost/cooldown config). A discovery gate (explored-zone or
flight-in-zone) is a documented future option — the server has no clean exploration getter.

### 9.6 Hard-won knowledge for the next agent
- **The row-id convention** (`GetCurrentMapAreaID()` = WorldMapArea row id + 1) is the key that made
  zone matching exact — earlier attempts used AreaTable ids and failed. ProjectEbonhold's
  `worldMapRects` + `ConvertToMapRelativeCoords` was the reference.
- **`sWorldMapAreaStore`** extern is commented out of DBCStores.h — declare it in the module.
- **Lua forward-reference trap** — a local used by a function defined earlier binds to nil global.
- **The addon channel** transport is proven by NexusFrames/mod-fury and mod-multibot-bridge
  (`OnPlayerCanUseChat`). MultiBot was moved to `client-resources/example-addons/MultiBot-Chatless/`.
- Reference addons live in `client-resources/example-addons/`: **ProjectEbonhold** (checkpoint map
  pins + teleport — the model we copied), **Astrolabe** (in HandyNotesSuite; world-map coordinate
  data), **GatherMate/Carbonite/Questie** (map rendering, GetMapInfo()).
- **`*_dbc` override tables are signed.** They mirror the DBC field order but the columns are MySQL
  `int`, while the DBC stores `uint32`. A raw `0xFFFFFFFF` (the usual "no faction" marker, e.g.
  `LFGDungeons.Faction`) is out of range and **aborts the entire update file** at that statement, so
  the revision never gets recorded. Convert with `v - 0x100000000 if v > 0x7FFFFFFF`.
- **World-SQL generators must anchor on the ORIGINAL data, never on their own output.** A generator
  that reads a table it also writes will, on a second run, read its own rows back and emit an empty
  `VALUES` list (a syntax error that blows up on next startup). Scope the read to the pre-existing
  range (e.g. `WHERE level < 80`). This bit us on a partially-applied update.

### 9.7 Deployment & current state
- **Server:** `wow-build` + restart worldserver. Module SQL auto-applies: `mod_qol_pins`
  (001), dungeon pins (002 — generated by `client-resources/generate_qol_dungeon_pins.py` from the
  client AreaTrigger.dbc + areatrigger_teleport), `mod_qol_points` (003), auth `account_taxi`.
- **Client:** repack `QoLFlightPaths/` into patch-4.MPQ — four files: `QoLFlightPaths.toc`,
  `QoLFlightPaths.lua`, `ZoneData.lua` (regenerate via `generate_qol_zone_data.py`), and
  `assets/wo_icon_raid.blp`. **Manual step**: the operator packs the MPQ, not an agent. Regenerate
  the DBC patches (`Item.dbc`, `Spell.dbc`) when items/spells change; players must wipe `Cache\WDB`.
- **Tested working:** pins on continent/zone/world views, faction filtering, junk-node removal,
  custom points, teleport, account-wide taxis, pet/autoattack/reagents, and the **cosmic-view button
  clearing** (verified in-game — zooming to the universe map clears pins, zooming back re-shows them).
- **Discovery fix (verified):** discovering a flight path now flips the pin live — icon, tooltip
  ("Flight path — click to travel") and click-to-teleport all work immediately, no `/reload` needed.
  Root cause of the earlier bug: button closures captured a stale `pin` table (pins are re-stored on
  every DATA load); they now read `btn.pin` (`self.pin`) which is kept in sync by HandleData/
  HandleDisc/PINADD.
- The worldserver/authserver are currently running.
- **State as of this handoff:** the §9.8 (pet scaling) and §9.9 (81-85) world SQL are applied, the
  core patches are built (Auto Shot while moving, pet scaling, level-penalty + top-rank spell clamp),
  and the client patch MPQ has been **repackaged with the patched `LFGDungeons.dbc`**, so the Dungeon
  Finder lists the 80-tier dungeons at 85. The Volley / talent-aura investigation was **abandoned at
  the user's request** — findings retained in §9.10 so they are not re-derived.

### 9.8 Pet & guardian stat scaling (+50%, custom — added alongside the Auto Shot patch)

A deliberate balance change: **every pet and temporary guardian** gets ~50% more HP, armor and
pet damage, at *any* gear level. It takes three layers, because the pet stat formula is linear —
scaling every one of its terms by 1.5 is what makes the result land on exactly 1.5x:

1. **Base pools — SQL.** `data/sql/updates/pending_db_world/rev_1789249925241422855.sql` scales
   `pet_levelstats` (all 35 entries x 80 levels): `hp`, `mana`, `armor`, `min_dmg`, `max_dmg` x1.5.
   `Guardian::InitStatsForLevel()` reads that table per creature entry — **all hunter pets share
   entry 1**, summon pets use their own creature entry — so this covers every pet/guardian that has
   a row (those without one fall back to `creature_classlevelstats` and are unaffected).
   `str/agi/sta/inte/spi` are intentionally NOT scaled: `Guardian::UpdateMaxHealth()`/`UpdateMaxPower()`
   compute `(GetStat - GetCreateStat)`, so base stats are subtracted out and scaling them is a no-op
   on HP/mana (it would only change the pet sheet).
   **This update is RELATIVE** — it multiplies whatever values are present when it runs; apply once
   (the DB updater records the revision), never re-run it by hand or the buff compounds to 2.25x.
2. **Owner inheritance — script literals.** How much a pet takes from its master is hardcoded in the
   per-class scaling aura scripts, recomputed every 2-3 s via `DoEffectCalcAmount`. The `spell_dbc`
   rows for those spells (34902-34958, 67557/67561) are placeholders with 0 amounts, so **this half
   cannot be tuned from the DB** — it is a rebuild. Scaled x1.5 here:
   - `spell_hunter.cpp` — stamina 45→67.5, RAP 22→33, SP 12.87→19.305, resist 35/40→52.5/60
   - `spell_warlock.cpp` — stamina 75→112.5, int 30→45, AP 57→85.5 (twice: generic + infernal),
     resist/armor 35/40→52.5/60 (twice)
   - `spell_generic.cpp` — 67557 int 30→45 and spirit 30→45 (applies to every pet and guardian)
   - `spell_dk.cpp` — str 70→105 / others 30→45, gargoyle stamina 30→45, AP 75→112.5
   - `spell_mage.cpp` — resist 35/40→52.5/60, stats 30→45, frost SP 33→49.5
   - `spell_druid.cpp` — resist 35/40→52.5/60, stats 30→45, nature→AP 105→157.5, nature SP 15→22.5
   - `spell_shaman.cpp` — feral spirit resist/stat/AP/SP x1.5; fire+earth elemental resist/stat,
     AP `300:150 → 450:225`, SP `100 → 150`
   - `spell_priest.cpp` — shadowfiend resist 35/40→52.5/60, int 30→45 / stamina 65→97.5,
     SP-as-AP 300→450, SP 30→45
   Where the original declared `int32 modifier`, it is now `float`: `CalculatePct`/`AddPct` are
   templates, and integer truncation would otherwise give +49% instead of +50%.
3. **Hardcoded pipeline values — core.** `src/server/game/Entities/Pet/Pet.cpp`
   (`Guardian::InitStatsForLevel`): flat armor `petlevel * 50 → * 75`, hunter pet base weapon damage
   `petlevel ± petlevel/4 → x1.5`, and the summon-pet fallback damage x1.5. Without this the flat
   armor term stays unscaled and total armor only lands at ~+35%.

Deliberately **not** changed: threat/aggro (tank pets still hold via Growl / Torment / Suffering),
and hit/expertise/spell-pen inheritance (61013/61017/67561 — those are derived from the owner's hit
chance, not a stat percentage). `mod-autobalance` rescales creature HP/damage and runs alongside
this, so sanity-check one level-80 elite fight after applying rather than trusting the arithmetic.

Verification note: `python apps/codestyle/codestyle-sql.py` shells out to `git fetch origin master`,
so it could not be run in the no-git session — the SQL was validated by hand against
`.agents/docs/sql-guidelines.md`. The C++ was compile-checked with `clang++ -fsyntax-only` using
`var/build/obj/compile_commands.json` (all 8 files clean; `spell_generic.cpp` needed the stale
`scripts` precompiled header excluded, which a normal rebuild regenerates).

### 9.9 Level cap 81-85 (custom realm cap) — what was un-frozen

The realm runs `MaxPlayerLevel = 85` against WotLK data that stops at 80. All of the following was
verified in-tree and fixed in one change set. Re-run the two generators instead of editing by hand.

**Why things froze:**
- `player_class_stats` has no rows past 80, so `ObjectMgr::LoadPlayerInfo` gap-fills levels 81-85 with
  the level-80 row (logging `does not have stats data. Using stats data of level 80.` per level) — a
  level-85 character had level-80 base stats, HP and mana.
- `player_xp_for_level` stops at level 79, so `GetXPForLevel()` returns 0 above it → every level past
  80 was free.
- `Unit::CalculateLevelPenalty` divided by the caster's *current* level, so any spell whose rank was
  learned before ~79 kept losing bonus damage as the player levelled — the actual "spells fall off
  past 80" bug.
- `SpellEffectInfo::CalcValue` clamps per-level spell growth at the spell's own `MaxLevel`; WotLK top
  ranks carry 84-90, so a handful froze a level or two early.
- `LFGMgr::GetRandomAndSeasonalDungeons()` requires `minlevel <= level <= maxlevel`, and every
  `LFGDungeons.dbc` entry stops at MaxLevel 80/83 → the Dungeon Finder list is empty at 85.

**Fix, by layer:**
- `src/server/game/Entities/Unit/Unit.cpp` (`CalculateLevelPenalty`): the reference level is now
  `min(caster level, spell MaxLevel)` — a spell can never be penalised below its own design level.
- `src/server/game/Spells/SpellInfo.cpp` (`SpellEffectInfo::CalcValue`): the `MaxLevel` clamp is
  lifted to `CONFIG_MAX_PLAYER_LEVEL` **for top-rank chain spells only** (`GetNextSpellInChain() == 0`),
  so low ranks keep their small caps and nothing can be exploited.
- `client-resources/generate_85cap_sql.py` → one pending world SQL containing: `player_class_stats`
  rows for 81-85 (per class, extrapolated from its own 76-80 trend — hunter is +1 STR/+3 AGI/+2 STA
  per level and HP ×1.0746/level), `player_xp_for_level` rows 80-84 (+16.6k/level), `lfgdungeons_dbc`
  overrides for the 63 WotLK entries (MaxLevel / Target_Level / Target_Level_Max → 85) and
  `lfg_dungeon_rewards` rows so the random-dungeon reward resolves at 85.
- `client-resources/generate_lfg_dungeon_dbc_patch.py` → patched **client** `LFGDungeons.dbc` (same 63
  entries) to ship at `DBFilesClient\LFGDungeons.dbc`. The Dungeon Finder needs **both** halves: the
  UI list is built from the client's own DBC, the queue/lock checks run on the server.

**Known, accepted gaps:** weapon-damage abilities (Mortal Strike, Devastate, Shield Slam) scale with
  the equipped weapon and there is no 81-85 itemization, so they stay at level-80 numbers; flat
  stat-buff spells do not scale (blizzlike); client tooltips keep showing client-DBC numbers unless
  `Spell.dbc` is patched for the client too. **Do not go looking at Volley's `spell_bonus_data` for its
  low damage — that hypothesis was tested and disproved; see §9.10.**

### 9.10 CLOSED (abandoned) — talent auras that gutted Volley damage; findings retained

**Status: abandoned at the user's request — no further work planned.** The accepted workaround is a
talent reset, which restored correct Volley damage. The findings below are kept because they were
expensive to derive, they name what NOT to chase, and one of them (stale granted auras) is a real
defect independent of Volley. Don't reopen the hunt without a decision to actually fix it.

**Symptom.** A level-85 hunter's Volley ticked for ~5 damage, ~10 after the §9.9 change, against a
client tooltip implying ~377/tick. **Resetting the character's talents restored correct damage** — so
the cause is a *talent-granted aura*, not spell data, not the level cap, not the client.

**Verified (do not re-derive):**
- Volley's chain is data-correct: aura `58434` (rank 8, SpellLevel 80) → persistent area →
  `PERIODIC_TRIGGER_SPELL` (amplitude 1000 ms) → trigger `58433` = `SPELL_EFFECT_SCHOOL_DAMAGE`,
  `BasePoints 352`, `DieSides 1`, `RealPointsPerLevel 0`, `EffectBonusMultiplier 0`, **arcane** school.
  Per-rank trigger mapping is also correct (rank1→`42243` base **5** … rank8→352).
- No `spell_dbc` or `spelldifficulty_dbc` row exists for any Volley id. `spell_bonus_data` for
  `58433`/`58432`/`42243` is `direct_bonus 0, dot_bonus 0, ap_bonus 0.0837, ap_dot_bonus 0`.
- `Spell::EffectSchoolDMG` passes `SPELL_DIRECT_DAMAGE`, so the `ap_bonus` term *is* applied — the
  231 other `spell_bonus_data` rows shaped `ap_bonus>0, ap_dot_bonus=0` are direct abilities and
  **not** a bug class.
- The §9.9 edits **cannot** touch a max-rank Volley: `RealPointsPerLevel = 0` skips the `CalcValue`
  clamp block entirely and `SpellLevel (80) >= MaxLevel (0)` early-outs `CalculateLevelPenalty` at
  1.0. They can only scale the *bonus* of older-rank spells (consistent with 5 → 10).
- `mod-autobalance` can modify damage but only on instanced maps, and its own comment notes player
  abilities are not caught by `ModifySpellDamageTaken`.
- **Enumerated every negative-valued effect across all 812 nodes' spells**: only defensive auras
  exist — `87 MOD_DAMAGE_PERCENT_TAKEN` (-1…-5), `114` projectile resilience (-1), `229` splashguard
  (-5) — plus **31 `SPELL_AURA_DUMMY` nodes** whose amount is a *script parameter* (e.g. `Light on
  Your Feet` = -1000). There is **no damage-*done* reducer in the data**, so the suspect is one of
  those DUMMY nodes, whose behaviour lives in a spell script — check `src/server/scripts/Custom/`
  (gitignored) as well as the Spells scripts.
- The damage pipeline ends in exactly two multiplicative stages: `Unit::SpellPctDamageModsDone`
  (`MOD_DAMAGE_PERCENT_DONE` multipliers → `DoneTotalMod`) and
  `Player::ApplySpellMod(SPELLMOD_DAMAGE | SPELLMOD_DOT, tmpDamage)`.

**Why a talent reset was needed at all (the underlying defect, if this is ever revisited).**
`mod-talent` applies a node with
`player->CastSpell(player, node.spells[rank-1], true)` (`talent.cpp:178-182`), removes it with
`RemoveAura(...)` (189), and **re-applies every owned node on every login**
(`ApplyAccountTalentOnLogin` ← `TalentPlayerScript::OnPlayerLogin`, 227/615-620). So applier-side data
changes already take effect at next login — but **nothing ever removes an aura the system granted
earlier**, and those auras persist on the character. Change a node's spell ids, or delete a node, and
every owner keeps the old aura forever, immune to logins. Only a talent reset clears it.

**Recommended fix (designed, not implemented):**
1. Track what was granted — `account_talent_aura(account_id, spell_id)` (or a column on
   `account_talent`), written in `ApplyTalentToPlayer`, cleaned in `RemoveTalentFromPlayer`.
2. A **resync routine** run on login *before* `ApplyAccountTalentOnLogin`, plus a GM command
   (`.nxserver resync` / `.talent resync <player>`): remove every tracked aura → re-apply currently
   owned nodes from live data → rewrite the tracked set. That makes future data changes
   reset-free and strips auras belonging to nodes that no longer exist.
3. A load-time guard in the module: log loudly / refuse if a node spell carries a damage-reducing
   effect, so a bad node cannot ship silently again.

If it is ever resumed, the two cheapest routes were: re-purchase talents in batches on an affected
character and re-measure Volley against the same target (the batch that drops it to ~10 contains the
node; talents are account-wide, so this is minutes), or add three temporary `LOG_INFO` lines in
`Unit::SpellDamageBonusDone` printing `pdamage`, `DoneTotal`, `DoneTotalMod` and the
post-`ApplySpellMod` value for id `58433`.

One expectation to keep: Volley's `spell_bonus_data` coefficient is 0, so its ceiling is
`353 + 8.37% × AP` per tick; the client's ~3014 figure is the channel total computed from client-side
data, not a per-tick number.
