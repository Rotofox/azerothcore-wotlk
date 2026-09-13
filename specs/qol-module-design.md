# QoL Module — Design (mod-qol)

> **STATUS: implemented — built and shipped.** This spec is retained as the design record. For
> current state see `documentation/modules.md` and `documentation/wow-handoff.md` §9.

Status: **implemented** (built and shipped).
Scope: new module `modules/mod-qol/` + client-resources DBC patches + one core patch.
Context: `documentation/wow-handoff.md` (fork state), `specs/fury-nexusframes-v2-design.md` (repo conventions).
Feasibility marks used below: ✅ module-able · ⚠️ module + extras · ❌ NOT module-able (core patch / client DBC / data).

---

## 0. Verdict summary (the five requested items)

| # | Request | Feasibility | Where it lives |
|---|---|---|---|
| F1 | Crate item 9000001 has no icon → fresh `client-resources/Item.dbc` | ❌ **not module** | client-resources (Item.dbc generator + repack) |
| F2 | Auto Shot castable while moving | ❌ **core patch** (3 lines, Spell.cpp) | core |
| F3 | Auto Shot no minimum range (melee-usable) | ⚠️ mostly **already true in the data** (range 114 = min 0 / max 35) + core patch for the per-shot check; verify in-game | core patch (CheckRange) |
| F4 | Hunter pets never need food / always well-fed | ✅ module | mod-qol |
| F5 | All offensive player spells auto-trigger autoattack (Bestial Wrath incl.) | ✅ module | mod-qol |
| F6 | No reagent requirements for any spell | ✅ module | mod-qol |
| F7 | World-map flight-path pins: all nodes visible, discovered = click-to-travel (instant teleport) | ✅ module + ✅ client addon (**no core patch**) | mod-qol + client-resources addon |
| F8 | Flight-path discovery is **account-wide** (one char discovers → all chars of the account have it) | ✅ module (**no core patch**) | mod-qol (auth DB table) |

Only **F1–F3** are marked. F4–F8 are fully implementable without touching the core — F7/F8 verified hook-by-hook below (F8 rides the existing `OnPlayerLearnTaxiNode` core hook; F7 needs a small client addon, which is normal for this fork — NexusFrames already ships in `patch-4.MPQ`).

---

## 1. Findings that drive the marks (verified in the live tree)

### F1 — Crate icon is client-side, full stop
The client renders bag/tooltip icons from **its own Item.dbc**, keyed by item entry. Entry 9000001 has no row there → "?" icon. The server already sends the correct displayid from `item_template` (see `modules/mod-random-enchants/data/sql/db-world/006_mod_re_crate.sql`).
**Fix:** extend `client-resources/generate_item_dbc_patch.py` to also emit a row for entry **9000001** cloned from a suitable crate/chest base item (pick the displayid whose icon reads as a "mystery crate" — e.g. the classic chest/crate displayid used by Mystery Crates), regenerate the full `Item.dbc`, repack into `patch-4.MPQ`, players wipe `Cache\WDB`. Keep `item_template.displayid` == the displayid we add. This is entirely outside the server module.

### F2 — "Cast while moving" cannot be done in a module
Mechanism (Spell.cpp): pressing Auto Shot (spell 75) builds a `Spell` whose `m_autoRepeat` is true (`Spell.cpp:665`, from DBC attr `SPELL_ATTR2_AUTO_REPEAT`). `Spell::CheckCast` then early-returns `SPELL_FAILED_MOVING` at **`Spell.cpp:5824`** when the caster moves. That check sits **after** `sScriptMgr->OnSpellCheckCast` (Spell.cpp:5675, the only global pre-check hook, veto-only) and **before** `CallScriptCheckCastHandlers` (Spell.cpp:6078), so no module hook can un-fail it.
Tried alternative — clear `SPELL_ATTR2_AUTO_REPEAT` via `spell_dbc` — is **unsafe**: `SpellInfo::CalcCastTime` (SpellInfo.cpp:2759) would add +500 ms cast time to Auto Shot (it carries `SPELL_ATTR0_USES_RANGED_SLOT`), and ATTR2 is load-bearing for wand/autoattack logic (Unit.cpp:12745/12759, Spell.cpp:3531).
**Fix:** tiny core patch at Spell.cpp:5824 — skip the auto-repeat branch for `m_spellInfo->Id == 75`:
```cpp
if ((!m_caster->HasUnitMovementFlag(MOVEMENTFLAG_FALLING_FAR) || m_spellInfo->Effects[0].Effect != SPELL_EFFECT_STUCK) &&
    ((IsAutoRepeat() && m_spellInfo->Id != 75) || (m_spellInfo->AuraInterruptFlags & AURA_INTERRUPT_FLAG_NOT_SEATED) != 0))
    return SPELL_FAILED_MOVING;
```
Verify in-game that (a) Auto Shot starts while running, (b) the auto-shot repeat still fires per weapon speed, (c) movement doesn't cancel an already-running auto-shot (retail WotLK allows move-and-shoot). The fork already carries local patches, so a documented 3-line diff is acceptable; keep it isolated and commented.

### F3 — Melee-range Auto Shot: the data already says min 0
Verified in the v16 Spell.dbc/SpellRange.dbc: spell 75's `RangeIndex` = **114**, and SpellRange 114 = `RangeMin[0]=0 / RangeMax[0]=35` (hostile and friendly). So **neither the server nor the client data has a minimum range for Auto Shot** — no client `Spell.dbc` range patch is needed at all. The only real blocker is the server's **per-shot** check: the auto-repeat fires `CheckCast(true)` per shot (Unit.cpp:4091), and `CheckRange` (Spell.cpp:7144) computes `minRangeCombined = min_range + meleeRange` — with min 0 that still rejects targets inside melee reach (~1.5 yd).
**Fix:** the F2 core patch also exempts spell 75 from that min-range branch (Spell.cpp:7144). If an in-game test still shows "You are too close" at true point-blank, the remaining block would be a hardcoded client-side constant (weapon min range) and would require a **client executable patch** — out of scope for a module/DBC change; note it and stop there.

### F4 — Pet happiness is trivially pin-able
Decay: `Pet::Update` (Pet.cpp:843–847) drops `m_happinessTimer` → `LoseHappiness()` (−670 happiness per 7.5 s, ×1.5 in combat). `GetHappinessState()` thresholds on `POWER_HAPPINESS` (=4, SharedDefines.h:261); < `HAPPINESS_LEVEL_SIZE` = Unhappy (−25% damage).
**Module fix:** `WorldScript::OnUpdate(diff)` throttled (~1–2 s) → for each online player with a pet: `pet->SetPower(POWER_HAPPINESS, pet->GetMaxPower(POWER_HAPPINESS))`; plus `PetScript::OnPetAddToWorld` to snap to max on spawn/res. Keeps pets permanently Happy/fed without touching core.

### F5 — Offensive-spell autoattack via the global AllSpellScript hook
`AllSpellScript::OnSpellCast(Spell*, Unit*, SpellInfo const*, bool)` fires for **every** spell in `Spell::cast()` (Spell.cpp:4086). Module logic:
- only when `caster->IsPlayer()`, the player is the real caster, not a pure proc (`IsTriggered()`), and the spell has a unit target that is a valid attack target (`IsValidAttackTarget`);
- **offensive** = any damage-ish effect (SCHOOL_DAMAGE, WEAPON_DAMAGE_NOSCHOOL, WEAPON_PERCENT_DAMAGE, WEAPON_DAMAGE, HEALTH_LEECH, POWER_DRAIN, periodic-damage auras, …) **or** `IsNegativeSpell()` — this exempts buffs/heals/utility by construction;
- `player->Attack(victim, melee)` where `melee = player->GetWeaponForAttack(BASE_ATTACK) != nullptr` (ranged/wand auto-attack when no melee weapon — configurable);
- **forced-include whitelist** (`QoL.AutoAttack.ForceSpells`, default `19574` = Bestial Wrath): attack the player's **selected target** (`GetSelectedUnit()`), since the spell's own target is the pet;
- **exclusion list** (`QoL.AutoAttack.ExcludeSpells`) for anything the predicate catches but shouldn't;
- `Attack()` is idempotent — no conflict with spells that already start autoattack.
Edge cases to test: channeled spells (Drain Soul) shouldn't interrupt the channel; don't fire on AoE-with-no-target or on friendly-target spells; avoid proc chains from pet-cast spells (filter non-player casters).

### F6 — Reagents: zero the SpellInfo data at startup
Reagent check (`Spell::CheckCast`, Spell.cpp:7329) and consumption (`Spell::TakeReagents`, Spell.cpp:5534) both read `m_spellInfo->Reagent[i]` / `ReagentCount[i]`. `spell_dbc` also exposes `Reagent_1..8`/`ReagentCount_1..8` (full-row override only).
**Module fix (recommended):** `WorldScript::OnStartup` (fires from `Main.cpp:390`, after `sSpellMgr->LoadSpellInfoStore` at World.cpp:406) → iterate `sSpellStore` rows → `const_cast<SpellInfo*>(sSpellMgr->GetSpellInfo(id))` → zero `Reagent[]` and `ReagentCount[]`. One-time startup, single-threaded, covers every current and future spell, no SQL maintenance. (`SpellMgr::_GetSpellInfo` exists but is private; `GetSpellInfo` returns const — the const_cast is the pragmatic, widely-used pattern here.)
**Alternative (no const_cast):** generated `spell_dbc` full-row INSERTs for every reagent spell with the reagent fields zeroed (python over `env/dist/bin/dbc/Spell.dbc`). Only choose this if we want zero C++ — it costs a generator + a giant SQL file.
**Client caveat:** tooltips still display "Requires: <reagent>" because that text comes from the client's own `Spell.dbc`. If we build `generate_spell_dbc_patch.py` for F3 anyway, zeroing reagent fields in the client copy is a ~10-line extension and hides the mismatch — decide in review.

---

## 2. Module architecture (F4–F6, F7–F8 server half)

```
modules/mod-qol/
├── CMakeLists.txt              (skeleton-module pattern; register in modules/CMakeLists.txt)
├── conf/qol.conf.dist
├── data/sql/db-auth/001_mod_qol_account_taxi.sql   (F8: acore_auth.account_taxi, mod-fury convention)
├── data/sql/db-world/001_mod_qol_autoshot_spell_dbc.sql   (F3 server consistency row, optional)
├── src/
│   ├── QoL_loader.cpp          (Addmod_qolScripts() → AddQoLScripts())
│   ├── qol.h
│   ├── qol.cpp                 (F4 pet happiness, F5 autoattack, F6 reagents)
│   └── qol_flightpath.cpp      (F7/F8: node cache, addon-message protocol, account-wide)
└── README.md
client-resources/QoLFlightPaths/   (F7 client addon — toc + lua; packs into patch-4.MPQ)
```
Script classes (one .cpp per concern, following `mod-no-hearthstone-cooldown` style):
- `QoLWorld : WorldScript` — `OnStartup` (F6 reagent zero, F7 node cache), `OnUpdate` (F4 pet happiness, throttled).
- `QoLPet : PetScript` — `OnPetAddToWorld` (F4 snap on spawn).
- `QoLAllSpell : AllSpellScript` — `OnSpellCast` (F5 autoattack). Constructor: `AllSpellScript("QoLAllSpell")` (empty hooks vector = all enabled).
- `QoLFlightPathPlayerScript : PlayerScript` — `OnPlayerCanUseChat` ×5 (F7 addon-message intake, consume pattern from mod-multibot-bridge), `OnPlayerLearnTaxiNode` (F8 account-wide), `OnPlayerLogin` (F8 apply account mask).
Config keys (all under `[worldserver]`, `qol.conf.dist`):
```
QoL.Enable = 1
QoL.AnnounceOnLogin = 1
QoL.Pet.AlwaysWellFed = 1
QoL.Pet.WellFedIntervalMs = 1500
QoL.Reagents.DisableAll = 1
QoL.AutoAttack.Enable = 1
QoL.AutoAttack.MeleeOnly = 1          # 0 = ranged/wand autoattack when no melee weapon
QoL.AutoAttack.ForceSpells = 19574    # comma list; Bestial Wrath
QoL.AutoAttack.ExcludeSpells =        # comma list
```

## 3. Non-module deliverables (F1–F3)

1. **Core patch** — `src/server/game/Spells/Spell.cpp`, three QoL edits for spell 75 (Auto Shot): (a) cast-completion moving check (~3563), (b) cast-start auto-repeat moving check (~5818), (c) min-range TOO_CLOSE branch (~7144). Rebuild worldserver only (`wow-build`), test.
2. **Client DBC patches** — `generate_item_dbc_patch.py` extended (F1: row 9000001, displayid 7925) + `generate_spell_dbc_patch.py` (F6 tooltip polish: zero reagent fields 52–67 for all spells). **No range patch needed** (F3: min range already 0 in the data). Regenerate full DBCs, repack into `patch-4.MPQ`, players wipe `Cache\WDB`.
3. Keep `item_template.displayid` for 9000001 consistent with the icon chosen in (2) — currently 7925 (Supply Crate icon), already matching in the live DB.

## 4. F7+F8 — Flight-Path World Map + Account-Wide Discovery (NEW, verified feasible)

Goal (user): all flight paths show on the world map even if undiscovered; once a player has **discovered** a flight path (right-clicked its flight master), its map pin can be **clicked to travel there instantly** (teleport — NOT the GM `.tele`); and discovery is **account-wide**. Reference: the Necro-Network feature in `specs/MultiBot-Chatless/` (`Features/MultiBotNecronet.lua` + `Core/MultiBotHandler.lua:2325-2346`) — pins on `WorldMapButton`, shown per continent/zone on `WORLD_MAP_UPDATE`, `GetCurrentMapContinent()`/`GetCurrentMapAreaID()` gating. Necro-Network sends GM chat commands (`.go graveyard`); we replace that with a **dedicated addon-message protocol** so normal players can use it (no `.tele`, no chat command at all).

**Verdict: no core patch needed.** Verified hooks/stores:
- `ScriptMgr::OnPlayerLearnTaxiNode(Player const*, uint32)` — ScriptMgr.h:493 (**PlayerScript** hook; called from `WorldSession::SendLearnNewTaxiNode` TaxiHandler.cpp:139 and `SendDiscoverNewTaxiNode` TaxiHandler.cpp:160, i.e. at every discovery point incl. right-clicking a flight master).
- `ScriptMgr::OnPlayerCanUseChat(Player*, uint32 type, uint32 lang, std::string& msg, ...)` — ScriptMgr.h:470-474 (5 overloads). This is how `mod-multibot-bridge` receives addon messages (`MultiBotBridgePlayerScript`, MultiBotBridge.cpp:7342+): checks `lang == LANG_ADDON`, parses the `"<prefix>\t"` envelope, handles it, **returns false to consume** so it isn't broadcast. Copy this pattern wholesale.
- `PlayerTaxi` (PlayerTaxi.h): `m_taximask` public via `Player::m_taxi`; `IsTaximaskNodeKnown(node)`, `SetTaximaskNode(node)` (returns true when newly set). Mask persisted in the `characters.taximask` column (PlayerStorage.cpp:5447 loads it).
- `sTaxiNodesStore` (TaxiNodesEntry: `ID, map_id, x, y, z, name[16], MountCreatureID[2]`) and `sWorldMapAreaStore` (WorldMapAreaEntry: `map_id, area_id, y1, y2, x1, x2, ...`) — both already loaded (DBCStores.cpp). WorldMapArea rows with `area_id == 0` are **continent bounds** — exactly what we need for world→map-percent math; the client renders the map with the same DBC, so server-computed percentages match the client's map.
- `Player::TeleportTo(mapid, x, y, z, orientation, options, target, newInstance)` — Player.cpp:1399. Faction-usable node masks exist (`sAllianceTaxiNodesMask`/`sHordeTaxiNodesMask`, DBCStores.h:196-197) for optional greying of enemy-faction nodes.
- Account-wide precedent in this fork: `mod-fury` uses `acore_auth.account_fury`; module auth-DB SQL ships at `modules/mod-fury/data/sql/db-auth/001_mod_fury_account_fury.sql` → ours: `data/sql/db-auth/001_mod_qol_account_taxi.sql` (`account_id`, `node_id`, PK(account_id,node_id)).

### 4.1 Server side (mod-qol, all in mod-qol)

1. **Node cache** — `QoLWorld::OnStartup`: iterate `sTaxiNodesStore`; for each node with a continent `WorldMapArea` row (`map_id == node->map_id && area_id == 0`), compute and cache `{nodeId, continent(1-4 from map_id: 0→1, 1→2, 530→3, 571→4), xPct, yPct, name}` where (convention to validate in-game against a known node, e.g. Stormwind):
   - `xPct = 100 * (node.x - x1) / (x2 - x1)` (x1 = west/LocLeft, x2 = east/LocRight)
   - `yPct = 100 * (node.y - y1) / (y2 - y1)` with **y from top**: WoW Y grows south; north bound = smaller Y. `yPct = 100 * (node.y - northY)/(southY - northY)`.
   - Addon placement formula (proven by Necro-Network): `tX = w*xPct/100 - w + 12; tY = h*-yPct/100 + h - 12; btn:SetPoint("BOTTOMRIGHT", tX, tY)` — i.e. xPct from left, yPct from top.
2. **Addon-message handler** — `QoLFlightPathPlayerScript : PlayerScript` overriding all 5 `OnPlayerCanUseChat` overloads (return false = consume):
   - Parse `"QOLFP\t" + opcode (+ '~' + payload)` envelope; ignore everything else (`lang != LANG_ADDON`).
   - **`REQ~<continent>`** (addon asks for one continent's nodes when the map opens) → reply with chunked data: `DATA~<continent>~<chunkIdx>~<chunkCount>~<nodes>` where each node = `id:xPct:yPct:d:name`, `d` = discovered flag from `player->m_taxi.IsTaximaskNodeKnown(id)`, joined by `;`. Chunk to ≤ ~240 bytes wire (≈8 nodes/msg; mirror MultiBotBridge's size discipline).
   - **`TP~<nodeId>`** → validate: node exists in cache; `player->m_taxi.IsTaximaskNodeKnown(nodeId)` (else `TPERR~NOTVISITED`); not in combat / not dead / not in arena-BG / not dueling (else `TPERR~<code>`); cooldown + optional gold cost from config; then `player->TeleportTo(node->map_id, node->x, node->y, node->z, 0.0f)` → reply `TPOK~<nodeId>`. Taxi-node z is a valid ground height; verify at test.
3. **Account-wide discovery** — `OnPlayerLearnTaxiNode(player, nodeId)`:
   - `LoginDatabase.Execute("INSERT IGNORE INTO account_taxi (account_id, node_id) VALUES ({}, {})", acct, nodeId)` (mirror mod-fury's `LoginDatabase` usage).
   - Iterate `sWorld->GetAllSessions()`: for every online char with the same account id, if `other->m_taxi.SetTaximaskNode(nodeId)` → send empty `SMSG_NEW_TAXI_PATH` (refresh vanilla UI mask) **and** push `DISC~<nodeId>` addon message so the pin flips to clickable. Include the discoverer too (their addon gets the state from the server list).
   - `OnPlayerLogin`: `SELECT node_id FROM account_taxi WHERE account_id = ?` → `SetTaximaskNode` each (in-memory; char DB persists naturally on logout). No char-DB writes needed — account table is authoritative.
4. **Reply/send helper** — copy `mod-fury`'s `ChatHandler::BuildChatPacket(data, CHAT_MSG_WHISPER, LANG_ADDON, player, player, msg)` + `player->SendDirectMessage(&data)` (fury.cpp:372-389).

### 4.2 Client side — new addon `QoLFlightPaths` (client-resources, ships in patch-4.MPQ at `Interface\AddOns\QoLFlightPaths\`)

- `.toc` + lua; register `CHAT_MSG_ADDON`, react to prefix `"QOLFP"` only (3.3.5 event passes the prefix; `RegisterAddonMessagePrefix` is Cata-only — handoff §7).
- On `PLAYER_LOGIN` (delayed briefly) and on `WORLD_MAP_UPDATE`, send `SendAddonMessage("QOLFP", "REQ~<continent>", "WHISPER", UnitName("player"))` (self-whisper trick, NexusFrames.lua:166) for the currently-viewed continent; cache per-continent node tables (id, xPct, yPct, name, discovered).
- Pins: one button per node, parented to `WorldMapButton`, Necro-Network math above; shown/hidden per continent on `WORLD_MAP_UPDATE` (NecroHandler pattern MultiBotHandler.lua:2325-2346). v1 display rule: show on the continent view (validate `GetCurrentMapAreaID()` semantics in-game — Necro-Network keys per-zone with `[continent][areaID]`; continent-level view needs the exact return value confirmed, tune one function `QoLFPMap.IsContinentView()`).
- Styling: discovered = colored pin + tooltip `<name> — click to travel`; undiscovered = greyed pin + tooltip `<name> — undiscovered` (not clickable, or click shows a hint message). Left-click discovered → `SendAddonMessage("QOLFP", "TP~<nodeId>", "WHISPER", UnitName("player"))`.
- Handle `DISC~<nodeId>` (flip to clickable), `TPOK~<nodeId>` / `TPERR~<code>` (print localized-ish message, e.g. "Traveled to Stormwind." / "You must discover this flight path first.").
- Slash toggle `/qolfp` (or fold into a QoL options frame) to hide pins for players who don't want them. Default on.

### 4.3 Config keys (add to `qol.conf.dist` — as built)
```
QoL.FlightPath.Enable = 1
QoL.FlightPath.AccountWide = 1        # F8 master switch
QoL.FlightPath.ShowAll = 1            # show undiscovered pins (0 = only discovered)
QoL.FlightPath.Settlements = 1        # minor settlement pins (innkeepers)
QoL.FlightPath.Dungeons = 1           # dungeon/raid entrance pins
QoL.FlightPath.MaxSettlementPins = 0  # per-continent cap (0 = unlimited)
QoL.FlightPath.TeleportCost = 0       # copper; 0 = free
QoL.FlightPath.TeleportCooldownSec = 10
QoL.FlightPath.Announce = 1
```

### 4.4 Why no core patch
- Addon messages: `OnPlayerCanUseChat` (ScriptMgr.h:470) is a module hook — proven by mod-multibot-bridge.
- Discovery hook: `OnPlayerLearnTaxiNode` (ScriptMgr.h:493) fires at both discovery sites — no core edit needed for account-wide.
- Teleport: plain `Player::TeleportTo`; the "GM only" restriction of `.tele` doesn't apply because we never use the command infrastructure — this is a normal server-side teleport gated on a real gameplay unlock (discovered node), exactly like a scripted teleport.
- Coordinate math: both DBCs are already server-side.

### 4.5 Implementation order & validation
1. Auth SQL table + cache build + REQ/TP protocol + addon skeleton → build (`wow-build`), start worldserver (currently stopped — handoff §6).
2. **Validate map math in-game**: compare pin positions against actual flight masters / the vanilla yellow dots for a handful of known nodes (Stormwind, Goldshire, Undercity, Orgrimmar, Thunder Bluff, Dalaran). Tweak y1/y2 orientation if pins mirror/flip.
3. Click-to-travel on a discovered node (discover via flight master, then click).
4. Account-wide: discover with char A → log char B (same account) → node already known + pin clickable; also live-update while both online.
5. Negative paths: undiscovered pin not teleportable; TPERR messages; in-combat denial; cooldown; gold cost.
6. Repack addon into patch-4.MPQ + WDB cache wipe (existing pipeline; **manual — the operator
   packs the MPQ, an agent cannot**).

### 4.7 Implementation notes — as built (deviations locked during implementation)

- **Pin sources (3 categories):** `Flight` = `sTaxiNodesStore` (all taxi nodes); `Settlement` = innkeeper spawns (`creature` JOIN `creature_template` on `npcflag & 0x10000`, only continent maps), filtered to those ≥ 250 yd from a flight node and ≥ 120 yd from an already-added settlement (name = zone name from `AreaTable.dbc`, fallback NPC name); `Dungeon` = `mod_qol_pins` (category 3), generated by `client-resources/generate_qol_dungeon_pins.py` from the client's `AreaTrigger.dbc` (source position) + `areatrigger_teleport` (name). 125 dungeon pins generated.
- **Coordinates:** the server sends raw world coords (`mapId, x, y, z`) per pin — NO server-side percent math. The client addon converts with hand-verified continent boxes (the same data Questie's HereBeDragons port uses for 3.3.5): `xPct=(left−x)/width, yPct=(top−y)/height`. Verified convention: TaxiNodes field 2 = X, field 3 = Y (matches the DBC struct; containment test 342/344 in-box). In-game validation is still step 1 of §4.5; the addon documents the one-line mirror fixes.
- **Account-wide (F8):** `acore_auth.account_taxi` is authoritative. On startup the module scans `characters.taximask` (space-separated 32-bit words) and seeds each account from the character with the **most** discovered nodes (retroactive normalization); `OnPlayerLearnTaxiNode` grows it live; `OnPlayerLogin` **and `OnPlayerCreate`** (new characters inherit immediately) apply it. Live online account-mates get `SMSG_NEW_TAXI_PATH` + a `DISC~` push.
- **No `spell_dbc` rows shipped:** F3 needs none (min range already 0); F6 is done in C++ at startup. `modules/mod-qol/data/sql/db-world/001_mod_qol_pins.sql` (table) + `002_mod_qol_dungeon_pins.sql` (generated data) + `data/sql/db-auth/001_mod_qol_account_taxi.sql`.
- **Client addon:** `client-resources/QoLFlightPaths/` (`QoLFlightPaths.toc` + `.lua`), packed into `patch-4.MPQ` at `Interface\AddOns\QoLFlightPaths\`. Slash `/qolfp` toggle. Continent-level pins (v1), `GetCurrentMapAreaID()==0` continent-view rule — tune `IsContinentView()` if a live test disagrees.

---

## 5. Suggested implementation order

1. Scaffold `mod-qol` via `create_module.sh` (gitignored clone — never commit/push, per handoff §7).
2. F6 reagents (pure startup code, zero risk) → build, verify warlock `Summon Voidwalker` needs no Soul Shard.
3. F4 pet happiness → verify pet stays Happy through combat + death.
4. F5 autoattack → verify Fireball/Arcane Blast starts melee swing; Bestial Wrath starts auto shot; Arcane Intellect does not.
5. **F7+F8 flight-path map** (auth SQL table, pin cache, REQ/TP addon protocol, account-wide discovery + normalization, addon) → validate pin positions in-game (order in §4.5).
6. F6 client Spell.dbc (reagent tooltip) + F1 Item.dbc (crate icon) → repack → verify point-blank Auto Shot (F3 core patch), `.re crate` icon.
7. F2/F3 core patch → verify move-cast + repeat + point blank.
8. F1 icon row → regenerate Item.dbc → repack → verify `.re crate` shows an icon.
9. Full regression pass + `documentation/` handoff update.

## 6. Risks / gotchas (from handoff + this research)

- `spell_dbc` rows are **full-row overrides** — a partial row silently zeroes every other field (Attributes, etc.). Always generate from the DBC.
- `SpellMgr::GetSpellInfo` is `const` — F6 uses const_cast at startup only (single-threaded; safe, but keep it isolated and commented).
- After any item-template or DBC change players must delete `Cache\WDB` (client caches icons/spells).
- `OnSpellCast` fires before effects resolve — autoattack starts on cast begin; acceptable, but watch channeled spells.
- Line numbers cited here are current (2026-08-17) but drift — re-verify against the live tree before patching.
- Module SQL must live in the module's `data/sql/db-world/` (auto-applied like mod-random-enchants), **never** in `data/sql/updates/pending_db_world/` (AGENTS.md rule).

---

## 7. Web research — bigger QoL candidate list (for a later slice)

Sources: Blizzard Classic+ wishlist thread (us.forums.blizzard.com/t/2318814), TBC Anniversary PTR notes (wowhead), nostalgic.gg private-server roundup. Feasibility marks are for THIS fork and are preliminary (verify before scoping).

| # | Idea | Who asks | Feasibility |
|---|---|---|---|
| Q1 | Instant mail delivery | Classic+ thread #1 | ✅ module (hook mail delivery delay) |
| Q2 | Dual spec free / early / cheaper | Classic+ thread #1 | ⚠️ config + data (verify keys) |
| Q3 | Infinite ammo (no ammo bags/quivers) | long-standing classic gripe | 🔧 **core config already exists** (`CONFIG_ENABLE_INFINITEAMMO`, seen in `Spell::TakeAmmo`) |
| Q4 | No durability loss on death / cheaper repairs | classic gripe | 🔧 config (`DurabilityLossInDeath`; repair rate) |
| Q5 | Remove daze from mobs (esp. mounted) | Classic+ thread | ✅ module (research exact hook) |
| Q6 | Mount at 30 / cheaper mount training | Classic+ thread #9 | 📦 data (spell/item/skill requirements) |
| Q7 | Working summoning stones | Classic+ thread #2 | 📦 data / SmartAI (verify) |
| Q8 | Dungeon Finder / LFG tool | TBC Anniversary notes | ⚠️ core feature (3.3.5 has LFG; verify config) |
| Q9 | More flight points + rested at hubs | Classic+ thread #11 | 📦 data (taxi nodes) |
| Q10 | Cheaper/bigger bags | Classic+ thread | 📦 data (item_template) |
| Q11 | Reduced/no respec fee | Classic+ FB roundup | 🔧 config (verify key) |
| Q12 | Cheaper profession recipes / no dungeon-gated recipes | Classic+ thread #4 | 📦 data |
| Q13 | Transmog | Classic+ thread (controversial) | ✅ module (mod-transmog pattern) |
| Q14 | Faster leveling / XP rate | universal | 🔧 config (`Rate.XP`) |
| Q15 | Reduced PvP honor decay | Classic+ FB roundup | ⚠️ config/verify |
| Q16 | Auto-loot / faster looting | classic gripe | ⚠️ client cvar + server config (verify) |
| Q17 | Instant quest-turn-in text (skip gossip spam) | classic gripe | 🖥️ addon (client-side) |
| Q18 | No weapon-skill grinding | classic gripe | ⚠️ config/data (verify) |
| Q19 | Wand auto-attack on cast (caster QoL) | caster mains | ✅ module (side effect of F5 ranged path) |
| Q20 | Reduced dungeon instance lockouts | classic gripe | 🔧 config (verify keys) |
| Q21 | Pet stable slot increase | pet classes | 🔧 config (verify key) |
| Q22 | Reduced run/fly-to-dungeon friction | Classic+ thread | 📦 data (flight paths) / 🖥️ addon |

Cut line: anything marked ⚠️/🔧/📦 is cheap and data/config-shaped; ✅/🖥️ items are code or addon work. F1–F8 (this slice) already cover the reagent, melee-range shots, pet, autoattack, and flight-path pain points.

**Sources:**
- [Classic plus feature / poll thread — Blizzard Forums](https://us.forums.blizzard.com/en/wow/t/classic-plus-feature-maybe-make-poll-for-features/2318814)
- [TBC Classic Anniversary PTR notes (Dual Spec, Instant Mail, Dungeon Finder) — Wowhead](https://www.wowhead.com/tbc/news/the-burning-crusade-classic-anniversary-ptr-will-open-this-week-379329)
- [Best Classic WoW Private Servers 2026 — Nostalgic.gg](https://nostalgic.gg/en/blog/2026-04-best-classic-wow-private-servers-en)
