# NexusServer Transfer Design — talents, Primeris, collections, transmog, Fury (v1)

> Authoritative design for transferring selected client-side systems from `client-resources/Work/`
> (the "Ashendor / Project Ebonhold" server dump) into this server, per the 20/08/2026 planning
> session. All decisions below are LOCKED unless marked "confirm". Reuse-first: anything in
> `client-resources/Work/` that implements a needed feature is copied, not reinvented.
> Last updated: 21/08/2026.
>
> **STATUS: implemented — built and shipped.** `mod-talent`, `mod-collections`, and `mod-transmog`
> are installed, and the `NexusServer` addon is packed into `patch-4.MPQ`. This is the design record;
> for current state see `documentation/modules.md` and `client-resources/latest-mpq-patch/README.md`.

---

## 0. Locked decisions (summary)

| # | Decision |
|---|---|
| D1 | **Universal talent tree** — Ebonhold's single "Default Soul Tree" (816 nodes), copied as-is (trimmed: see §8.1). |
| D2 | **Account-wide, always-on** — talents unlock per-account (like Fury) and apply to every character automatically; no loadouts in v1. |
| D3 | **100% refund, everything** — no `permanent` nodes; right-click refunds the node and cascades to all dependents (parents-maxed rule). |
| D4 | **Primeris drops scale with mob level**: `(random(5,10) + 5) × mobLevel` per eligible kill, uncapped; **×3 for elites/rares/bosses**; every party member eligible. |
| D5 | **Price scale A (÷100)** of Ebonhold's raw ladder — total tree ≈ **4.28M** Primeris. |
| D6 | **Adopt Work's Spell.dbc** (55,625 rows) as the server DBC + client patch (regen the QoL reagent cleanup on it). |
| D7 | **Primeris is per-character**, Fury-style: a server-side value in `acore_characters`, displayed in the talent UI bottom bar (and optionally NexusFrames) — NOT the stock Currency tab (the 3.3.5 client has no currency-count packet; showing a value there would require an item-backed hack, which we deliberately rejected for simplicity — see §8.3). |
| D8 | **Transmog**: reuse **mod-transmog** engine (already built, collection mode); new **mod-collections** module owns the addon protocol and bridges into mod-transmog's public tables/API. **No edits to mod-transmog.** |
| D9 | **Collections auto-unlock on loot/equip/quest** (mod-transmog already does this for appearances; mounts/pets via `PLAYERHOOK_ON_LEARN_SPELL`). |
| D10 | **One client addon: `NexusServer`** — ProjectEbonhold core + skillTree + collections + options + assets, with **NexusFrames folded in as a module** (Fury tab + compact bar + micro button). QoLFlightPaths stays a separate addon. |
| D11 | **DUMMY-aura talents deferred to v2** (gathering/crafting yield etc. — nodes ship in the tree but are inert until their server handlers exist). |
| D12 | **Client patch**: user packages the MPQ from `client-resources/latest-mpq-patch/` (no MPQ tooling on this box). Icons + instance maps already staged there. |
| D13 | Instance maps are **data-only** (WDM-patch pattern; **no FrameXML needed** — corrects an earlier assumption). |

---

## 1. Architecture overview

```
Game client (3.3.5a, patch MPQ)
├── NexusServer addon            (Interface\AddOns\NexusServer\)  — Fury module, skillTree UI,
│                                 collections UI, transport core
├── Interface\Icons\*.blp        (30,630)  — icon library
├── Interface\WorldMap\*.blp     (1,548)  — instance maps
├── DBFilesClient\Spell.dbc      (55,625 rows — Work's, + reagent cleanup)
├── DBFilesClient\DungeonMap.dbc / DungeonMapChunk.dbc / WorldMapArea.dbc / WorldMapTransforms.dbc
└── DBFilesClient\Item.dbc       (variant items, existing)

Worldserver
├── mod-talent        (NEW, gitignored dir)   — Primeris drops, purchase/refund, apply auras
├── mod-collections   (NEW, gitignored dir)   — mounts/pets account-wide + collection protocol +
│                                              transmog bridge (calls into mod-transmog)
├── mod-transmog      (existing clone)        — appearance collection + transmog engine (SQL to import)
├── mod-fury / mod-qol / mod-random-enchants  — unchanged
└── env/dist/bin/dbc/Spell.dbc    ← replaced with Work's (D6)
```

Wire transport: one addon channel, prefix **`NXSRV`**, self-whisper `SendAddonMessage`, numeric
opcodes in a CS/SS table, generic chunking (`@mid idx/total`, 180 chars) — the ProjectEbonhold
pattern (see §10).

---

## 2. Reuse map (from `client-resources/Work/`)

| Feature | Reused from Work/ | Destination |
|---|---|---|
| Icons | `Interface/Icons/` (30,630 BLP2 64×64 DXT1/DXT5) | `latest-mpq-patch/Interface/Icons/` ✅ staged |
| Instance maps | `DBFilesClient/{DungeonMap,DungeonMapChunk,WorldMapArea,WorldMapTransforms}.dbc` + `Interface/WorldMap/` (1,548 files, 56 instances) | `latest-mpq-patch/` ✅ staged |
| Spell set | `DBFilesClient/Spell.dbc` (55,625 rows; stock 49,839 + ~5,800 custom incl. all talent spells) | server `env/dist/bin/dbc/` + client patch (needs reagent cleanup) |
| Talent UI | `AddOns/ProjectEbonhold/modules/skillTree/` (TalentDatabase.lua, skillTree.lua, skillTree_service.lua, skillTreeMicroButton.lua, skillTreeDebug.lua) + `GlowBoxTemplate/` + `assets/` (TalentFrame-Parts, 9-slice buttons, backgrounds) | NexusServer addon |
| Collections UI | `AddOns/ProjectEbonhold/modules/collections/` (visual shell + stub seams + Data catalogs + PROTOCOL.md) + `progression/` + vendor/ (Ace3) | NexusServer addon |
| Transport | `projectebonhold.lua` (PREFIX, sendToServer, onEventReceived, chunking, CS/SS tables) | NexusServer core |
| Fury styling | `assets/128redbutton9sliced*.blp`, TalentFrame-Parts glows | Fury module restyle |
| Spell decode | The 940 talent spell ids decode to real auras (AP/SP/stats/haste/resists/XP/procs/milestones) — usable with zero extra server code | mod-talent apply |

---

## 3. Client patch pipeline — `client-resources/latest-mpq-patch/`

**State: staged ✅** — `Interface/Icons/` (30,630), `Interface/WorldMap/` (1,548), `DBFilesClient/` (4 map DBCs). 270 MB.

**Pending (built during implementation, then dropped in):**

| File | Source | Notes |
|---|---|---|
| `Interface/AddOns/NexusServer/` | §4 | full addon folder |
| `DBFilesClient/Spell.dbc` | Work's 55,625-row file → run `client-resources/generate_spell_dbc_patch.py --dbc <workfile>` (reagent cleanup) | server DBC must be the same file (D6) |
| `DBFilesClient/Item.dbc` | existing (variant items) — unchanged unless variant icons land (v2) | |

**MPQ layout for the user** (Ladik's MPQ Editor; file → `patch-4.MPQ` in `Data/enUS/` — the single consolidated client patch):
```
DBFilesClient\Spell.dbc
DBFilesClient\DungeonMap.dbc
DBFilesClient\DungeonMapChunk.dbc
DBFilesClient\WorldMapArea.dbc
DBFilesClient\WorldMapTransforms.dbc
Interface\AddOns\NexusServer\...            (every file under the addon folder)
Interface\Icons\*.blp
Interface\WorldMap\...\*.blp
```
Add a `README.md` to the folder documenting this layout + the WDB-cache wipe requirement after install.

**Server-side DBC copy:** `env/dist/bin/dbc/Spell.dbc` ← Work's file (before rebuild/restart). No other server DBC changes.

**WDB:** after every DBC/texture patch players delete `Cache\WDB` (game closed).

---

## 4. NexusServer addon (D10)

### 4.1 Structure (`client-resources/NexusServer/`)

```
NexusServer/
├── NexusServer.toc                 (## Interface: 30300; title "NexusServer")
├── core.lua                        (transport: PREFIX "NXSRV", CS/SS tables, sendToServer,
│                                    onEventReceived, chunking — ported from projectebonhold.lua)
├── constants.lua
├── modules/
│   ├── utils.lua
│   ├── fury/                       (fury.lua — NexusFrames module, §5; micro button)
│   ├── skillTree/                  (TalentDatabase.lua, skillTree.lua, skillTree_service.lua,
│   │                                skillTreeMicroButton.lua — copy, rebranded)
│   ├── collections/                (full shell copy: core/, Data/, Interface/, ezCollections.xml)
│   ├── progression/                (character_progression.lua — tabs hub)
│   ├── options/                    (options + cvar_options)
│   └── GlowBoxTemplate/            (xml + assets)
├── assets/                         (TalentFrame-Parts, 128redbutton9sliced*, backgrounds)
└── vendor/                         (Ace3 libs the retained modules reference — trim unused)
```

### 4.2 Modules kept vs stripped (from the Work dump's 60)

**Keep:** skillTree, collections, progression, options, GlowBoxTemplate, utils, fury (new).
**Strip:** checkpoint, torment/hardmode, perks/echo_journal, shop, scrap, extraction, playerRun,
questTracker, instanceReset, instanceFollowup, extBank, voidStorage, overflowHealth, worldChannel,
customTicket, spellUnlearn, spellPlacement, actionBarSaver, levelup, achievementBonus, ptrBanner,
echoTome, itemPurchase, cooldownText, spec, knowledgeBase, itemUtils, objectives, customTicket. Rebuild the toc to only the kept files.

### 4.3 Rebranding

- Addon name/title → NexusServer; SavedVariables → `NexusServerDB`, `NexusServerPerCharDB`.
- Currency strings: "Soul Points"/"Soul Ashes" → **Primeris** (client strings + tooltips).
- PREFIX → `NXSRV`; opcode tables → §10.
- Remove Ebonhold branding in strings/options.

### 4.4 Transport (ported from `projectebonhold.lua`)

- `sendToServer(id, body)`: small payloads `string.format("%s\t%s", id, body)`; large bodies
  chunked `"%s\t@%s\t%03X/%03X\t%s"` (id, mid, idx, total, chunk), `MAX_CHUNK_SIZE = 180`.
- `onEventReceived(id, fn)`: dispatch table on `CHAT_MSG_ADDON` (prefix filter); guard
  `RegisterAddonMessagePrefix` for Cata-only.
- Server side: `PlayerScript::OnPlayerCanUseChat` LANG_ADDON path (same as mod-qol / mod-fury
  addon wire); replies via `ChatHandler::BuildChatPacket(data, CHAT_MSG_WHISPER, LANG_ADDON, player,
  player, wire)` + `SendDirectMessage`. Chunk reassembly on the client keyed by `mid`.

---

## 5. Fury in NexusServer (D10) — layer fix + restyle

### 5.1 The layer bug (user-reported: "floating bar fill is above bar frame and text")

Current code (`NexusFrames.lua`, compact bar): `compactFill` = StatusBar child anchored
TOPLEFT(2,-2)/BOTTOMRIGHT(-2,2); `compactText` = FontString child ("OVERLAY", created after fill);
backdrop `edgeSize = 16`, `insets = 3`.

Two compounding issues:
1. **Fill covers the border/frame**: fill inset (2) is far smaller than the backdrop edge (16), so
   the red fill texture overlaps the border texture.
2. **Fill over text**: the StatusBar fill texture defaults to the ARTWORK draw layer and can render
   above the FontString.

**Fix (apply to both `compactFill`/`compactText` and the window's `bar`/`barText`):**
- `fillTexture = compactFill:GetStatusBarTexture(); fillTexture:SetDrawLayer("BACKGROUND")`
  (fill behind the bar's artwork/border and the text).
- Keep `compactText`/`barText` on "OVERLAY", created after the fill.
- If the border still reads under the fill, draw the border as a **separate texture/frame created
  LAST** (topmost child) instead of relying on the backdrop edge.
- Verify in-game: fill must never cover the border or the "Fury Lv X — a / b" text.

### 5.2 Restyle (Ebonhold assets)

- Compact bar + tab bar backdrops → `128redbutton9sliced.blp` (red — matches Fury) 9-slice,
  variants blue/purple available for accents; keep Fury red as primary.
- Micro button → TalentFrame-Parts glow treatment (GlowBoxTemplate pattern, ADD blend).
- Reward icons in the tab's horizontal reward list → pick from the 30,630-icon library (replaces
  the current stock icons); spell names/icons via GetSpellInfo where the entry is a spell.
- Layout otherwise preserved (draggable compact bar, tabbed window, tier-colored list). Milestone
  tick marks on the compact bar (per talent milestones) = optional v1.5 nicety, not v1.

---

## 6. Instance maps (WS2, D13) — already staged

- Data-only (WDM-patch pattern): 4 DBCs + 1,548 textures. Stock 3.3.5a client renders dungeon
  maps when the data is present — no FrameXML, no addon code.
- Copy `latest-mpq-patch/DBFilesClient/*` + `Interface/WorldMap/*` (done).
- **Regenerate `client-resources/QoLFlightPaths/ZoneData.lua`** with
  `generate_qol_zone_data.py` pointed at the **patched** WorldMapArea.dbc (159 rows vs stock 108)
  so QOLFP pins stay consistent with the extended map set.
- Test in-game: `M` inside instances (big map vs minimap-only instances), plus the new
  continents/battlegrounds the patch adds.
- Server copy of WorldMapArea.dbc stays stock (server never renders maps).

---

## 7. Icons (WS1) — already staged

- 30,630 BLP2 64×64 DXT1/DXT5 in `latest-mpq-patch/Interface/Icons/`. Referenced by path
  (`Interface\Icons\<name>.blp`) — no DBC required to *use* an icon.
- v1 uses: Fury reward icons, skillTree node spell icons (nodes render via GetSpellInfo; the
  custom talent spells carry no SpellIcon.dbc rows in OUR client — the tree UI should fall back
  to a default icon or use the icon from a mapped stock spell; optionally add
  `DBFilesClient/SpellIcon.dbc` (Work's 33,989-row file) to give the custom spells real icons —
  **recommended, staged as pending in §3**).
- v2 idea: distinct modern icons for the 76k variant items (needs ItemDisplayInfo/displayid work).

---

## 8. Talents + Primeris (WS4) — the core feature

### 8.1 Tree data

- **Copy** `TalentDatabase.lua` (816 nodes, tree `[0]` "Default Soul Tree") into the NexusServer
  addon. Node fields: `id, x, y, spells{rank1..n}, soulPointsCosts{rank1..n}`, flags `isStart`,
  `infinite/infiniteGrowth`, `gainsPerRank`, `gainsExclusive`, `permanent` (all stripped for v1),
  `computedDesc`. Topology = `links = { {parent, child}, ... }`; **a node unlocks when ALL its
  parents are maxed** (client `hasPrerequisites`).
- **Trim for v1:** the 4 riding-skill nodes (spells 33391/34090/34091/54197) — they teach
  account-wide skills that a refund cannot cleanly unlearn. Remove from `TalentDatabase.lua` +
  their `links` entries. (Confirm: alternatively keep and document that refund leaves riding learned.)
- **Server seed (single source of truth):** a generator script
  (`client-resources/generate_talent_seed.py`, reads TalentDatabase.lua) emits
  `mod-talent/data/sql/db-world/001_mod_talent_nodes.sql`:
  - `talent_nodes(id, x, y, spells TEXT, costs TEXT, is_start, infinite)` — spells/costs as
    comma-separated rank arrays, costs **already scaled ÷100** (rule §8.2).
  - `talent_links(parent_id, child_id)`.
  Re-run + re-import whenever TalentDatabase.lua changes.

### 8.2 Economy

**Drop formula (D4, config-driven):**
```
primeris = (rand(5, 10) + 5) * mobLevel        -- i.e. rand(10,15) * level, uncapped
if elite|rare|boss:  primeris *= 3
```
- Eligibility + party sharing: copy Fury's `OnPlayerCreatureKill` pattern exactly — non-grey gate
  (`killed->GetLevel() <= Acore::XP::GetGrayLevel(killer->GetLevel())`), group/raid members within
  `IsAtGroupRewardDistance`, **each character** awarded (dedup per character, not per account).
- Elite/rare/boss detection: `killed->IsDungeonBoss()` OR creature rank
  `CREATURE_ELITE_ELITE / CREATURE_ELITE_RARE / CREATURE_ELITE_RARE_ELITE / CREATURE_ELITE_WORLDBOSS`.
- Award: atomic increment on the character's Primeris row (§8.3) + optional chat message (config).
  NOTE: no item is created — drops are pure DB arithmetic (Fury-style).
- Config: `Primeris.Enable`, `Primeris.BaseMin=5`, `Primeris.BaseMax=10`, `Primeris.LevelBonus=5`,
  `Primeris.EliteMultiplier=3`, `Primeris.NotifyGain`.

**Price ladder (D5, ÷100):** `cost = max(1, round(raw / 100))` applied to every `soulPointsCosts`
entry. Reference conversions:

| raw (Ebonhold) | ÷100 | | raw | ÷100 |
|---|---|---|---|---|
| 50 | 1 | | 17,000 | 170 |
| 75 | 1 | | 35,000 | 350 |
| 150 | 2 | | 52,500 | 525 |
| 225 | 2 | | 75,000 | 750 |
| 600 | 6 | | 300,000 | 3,000 |
| 1,000 | 10 | | 1,000,000 | 10,000 |
| 2,500 | 25 | | 5,000,000 | 50,000 |
| 7,000 | 70 | | 10,000,000 | 100,000 |

Full Might branch ≈ 1,214; milestones ≈ 525; Greater-zone nodes ≈ 10k–100k; **tree total ≈ 4.28M**.
At level-80 drops (~1,000/kill): a branch ≈ 1 hour, milestones ≈ 30 min, Greater nodes ≈ 10–100
kills. Prices are data (generated seed) — tuning later = edit the generator + re-import.

### 8.3 Primeris currency (D7) — Fury-style per-character value

**Design (changed 21/08/2026):** Primeris is a **server-side per-character value** (`character_primeris`
in acore_characters), exactly like Fury's account value but keyed by character GUID. It is displayed in
the **talent UI bottom bar** (Ebonhold's `pointsText` — the tree already shows a spendable-points
balance; we rebrand it to Primeris) and optionally in the NexusFrames Fury window. It is **not** shown
in the stock 3.3.5 Currency tab.

**Why not the Currency tab (recorded for future agents):** verified TC 3.3.5 has **no
currency-count packet** (`SMSG_UPDATE_CURRENCY` does not exist; only cheat opcodes for honor/arena).
The 3.3.5 tab renders counts only for **item-backed currencies** (emblems: CurrencyTypes.dbc row's
ItemId = the emblem item; the client counts the item). Showing Primeris there would require an
emblem-style item with a CurrencyTypes.dbc row — bag-space pressure, full-bag refund failures, and
mail/vendor/delete edge cases — for zero gameplay benefit. Rejected for v1; the item-backed route
remains a documented fallback if the tab is ever a hard requirement.

**Storage:**
```sql
-- acore_characters (db-characters)
CREATE TABLE character_primeris (
  guid INT UNSIGNED NOT NULL PRIMARY KEY,
  amount INT UNSIGNED NOT NULL DEFAULT 0
);
```
- Drops: `INSERT ... ON DUPLICATE KEY UPDATE amount = amount + ?` (atomic; Fury's pattern).
- Purchase: validate balance (`amount >= totalCost`) then decrement.
- Refund: increment.
- No client-side currency sync needed — the addon uses the balance sent in `SEND_TALENT_STATE`
  (authoritative), refreshed on login + on open + after purchase/refund replies.

### 8.4 Server module `mod-talent`

Files: `modules/mod-talent/{src/{talent.cpp,talent.h,talent_loader.cpp}, conf/talent.conf.dist,
data/sql/{db-world/001_mod_talent_nodes.sql (generated), db-auth/001_mod_talent_account.sql,
db-characters/001_mod_talent_primeris.sql}}`. Gitignored dir (like mod-fury/mod-qol; **no git**).

**DDL:**
```sql
-- acore_auth (db-auth)
CREATE TABLE account_talent (
  account_id INT UNSIGNED NOT NULL,
  node_id    INT UNSIGNED NOT NULL,
  rank       TINYINT UNSIGNED NOT NULL DEFAULT 1,
  cost_paid  INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (account_id, node_id)
);
-- acore_world (db-world, generated)
CREATE TABLE talent_nodes (
  id INT UNSIGNED PRIMARY KEY,
  x INT NOT NULL, y INT NOT NULL,
  spells TEXT NOT NULL, costs TEXT NOT NULL,
  is_start TINYINT UNSIGNED DEFAULT 0, infinite TINYINT UNSIGNED DEFAULT 0
);
CREATE TABLE talent_links (
  parent_id INT UNSIGNED NOT NULL, child_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (parent_id, child_id)
);
```

**Hooks (PlayerScript / WorldScript):**
- `OnPlayerCreatureKill` → Primeris drop (§8.2).
- `OnLogin` → apply all `account_talent` node spells (highest rank) as permanent passive auras:
  `player->CastSpell(player, spellId, true)` for each node's `spells[rank-1]`; on logout/none
  needed (auras are re-applied on login; also apply on purchase to online chars).
- Addon-message handler (own PREFIX dispatch): `REQUEST_TALENT_STATE`, `REQUEST_PURCHASE_TALENT`,
  `REQUEST_REFUND_TALENT` (§10).

**Purchase flow (full-state commit):**
1. Client sends target rank map `"nodeId:rank nodeId:rank ..."` (the whole build after edits).
2. Server loads current `account_talent`; computes added ranks (target > stored) and their costs
   from `talent_nodes` (scaled); validates **every** target rank against `talent_links` parents
   maxed (parents' target rank ≥ max) and Primeris item count ≥ total cost.
3. Deduct: atomic decrement on `character_primeris` (after validating balance); upsert ranks (store
   `cost_paid`); apply diff spells on all online account characters (cast new-rank spells, remove
downgraded).
4. Reply `SEND_PURCHASE_RESULT` ("ok" or "err:reason").

**Refund flow (cascade, D3):**
1. `REQUEST_REFUND_TALENT nodeId` (right-click).
2. Server computes the removed set = node + **every descendant whose parents are no longer all
   maxed** (transitive closure over `talent_links`).
3. Refund = sum of `cost_paid` for removed nodes (100%); atomic increment on `character_primeris`;
   delete rows; remove auras on all online account chars.
4. Reply `SEND_REFUND_RESULT` ("ok:refunded:nodeId,..." | "err:reason").

**Effect application notes:** most talent spells are passive auras (eff 6, permanent duration —
verify `DurationIndex` on adoption); proc spells (`PROC_TRIGGER_SPELL`) and `LEARN_SPELL` nodes
(riding — trimmed) behave via cast. `DUMMY`-aura nodes (D11) are recorded + cast but have no
server-side effect until v2 handlers.

### 8.5 Client UI flow (copied from skillTree.lua)

- Node button: left-click rank-up (local cost accounting), right-click rank-down/refund
  (`getNodeCost`), "Apply Changes" button (`applyButton`) enabled when `hasUnsavedChanges &&
  affordable` → sends the full target map; `OnApplyChangesResult` handles ok/err + re-enable.
- Revert button → `RevertToValidatedState` (last server-confirmed state).
- Currency names rebranded to Primeris; balance comes from `SEND_TALENT_STATE` (`primerisCount`,
  server-authoritative), refreshed on login/open and after each purchase/refund reply.
- Loadout save/export/import UI: keep dormant or strip in v1 (D2 — no loadouts).
- Micro button opens the tree (Ebonhold `skillTreeMicroButton`), or fold into the Fury window as a
  tab (D10) — **decide during addon assembly**: recommend a Character-Progression-style hub with
  Fury / Talents / Collections tabs (reuse `progression/character_progression.lua`).

---

## 9. Collections + transmog (WS5/WS6, D8/D9)

### 9.1 mod-transmog — import + config (already built, tables missing)

**Import SQL (in order):**
1. `modules/mod-transmog/data/sql/db-characters/trasmorg.sql` → acore_characters
   (`custom_transmogrification`, `custom_transmogrification_sets`, `custom_unlocked_appearances`).
2. `modules/mod-transmog/data/sql/db-world/trasm_world_texts.sql` + `updates/2026_05_09_migrate_strings_to_module_string.sql` + `2026_07_23_transmog_claim_strings.sql` + `data/sql/updates/world/2026_05_09_transmog_set_disclaimer.sql` → acore_world.
3. **Skip** `db-auth/acore_cms_subscriptions.sql` (premium TransmogPlus) and `trasm_world_NPC.sql` /
   `trasm_world_VendorItems.sql` (vendor/NPC route disabled).

**Config (env/dist/etc/modules/transmog.conf):** already collection mode — `UseCollectionSystem=1`,
`UseVendorInterface=0`, `CopperCost=0`, `RequireToken=0`, `RetroActiveAppearances=1`,
`AllowHiddenTransmog=1`, `HiddenTransmogIsFree=1`. Keep.

**Auto-unlock (D9) — already in the module:** `OnPlayerEquip`, `OnPlayerLootItem` (BoP),
`OnPlayerCreateItem`, vendor-buy, `OnPlayerCompleteQuest`, + one-time retroactive backfill
(inventory/bank/rewarded quests, gated by a player setting). Unlocks land in
`custom_unlocked_appearances` (account_id, item_template_id) + in-memory cache.

### 9.2 Server module `mod-collections`

Files: `modules/mod-collections/{src/{collections.cpp,collections.h,collections_loader.cpp},
conf/collections.conf.dist, data/sql/{db-auth/001_mod_collections_account.sql,
db-world/001_mod_collections.sql}}`. Gitignored dir (no git). Includes
`../../mod-transmog/src/Transmogrification.h` for `sTransmogrification` (same binary — modules
compile together).

**DDL (acore_auth):**
```sql
CREATE TABLE account_mount (account_id INT UNSIGNED NOT NULL, spell_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (account_id, spell_id));
CREATE TABLE account_pet (account_id INT UNSIGNED NOT NULL, spell_id INT UNSIGNED NOT NULL,
  PRIMARY KEY (account_id, spell_id));
```

**Mounts/pets account-wide:**
- `PLAYERHOOK_ON_LEARN_SPELL` (exists in this core): if the learned spell is a mount/pet spell
  (detect via SpellInfo: `SPELL_EFFECT_SUMMON` mount / `SPELL_EFFECT_SUMMON_PET` companion, or a
  config allowlist seeded from the client catalog spell ids), upsert `account_mount/pet` for the
  account and **grant to all other online account characters** (`player->learnSpell`).
- `OnLogin`: learn every missing `account_mount/pet` spell on the character.
- Snapshots: `SEND_COLLECTED_MOUNTS/PETS` = the account's spell ids (chunked).

**Transmog bridge (D8):**
- `REQUEST_COLLECTIONS "appearances"` → `SEND_COLLECTED_APPEARANCES`:
  `SELECT ai.item_template_id, it.displayid FROM custom_unlocked_appearances ai JOIN item_template it
  ON it.entry = ai.item_template_id WHERE ai.account_id = ?` → send **displayids** (the shell's
  model: a visual is collected iff its displayID is in the set).
- `REQUEST_COLLECTIONS "transmog"` → `SEND_TRANSMOG_SLOTS`: iterate equipped items
  (`player->GetItemByPos`), look up `custom_transmogrification.FakeEntry` by item guid → `slot:entry`.
  Slot ids (server-side EQUIPMENT_SLOT, per PROTOCOL.md): 1 Head, 3 Shoulder, 4 Shirt, 5 Chest,
  6 Waist, 7 Legs, 8 Feet, 9 Wrist, 10 Hands, 15 Back, 16 Main hand, 17 Off hand, 18 Ranged/Relic,
  19 Tabard.
- `REQUEST_APPLY_TRANSMOG "slot:item ..."`: per entry — validate the source item's displayid is in
  the account's collected set AND `CanTransmogrifyItemWithItem`; then
  `sTransmogrification->Transmogrify(player, itemEntry, slot, true)` (no_cost; CopperCost=0).
  `slot:0` = hidden (`Transmogrify(player, UINT_MAX, slot, true)`), `slot:-1` = clear
  (`sTransmogrification->DeleteFakeEntry(player, slot, equippedItem)`).
- Replies: `SEND_TRANSMOG_SLOT_UPDATE "slot:item"` per applied slot; error reasons as strings.
- Live `SEND_APPEARANCE_LEARNED` delta pushes on loot → **v2** (snapshots on open/login suffice).

**Semantic note:** mod-transmog's fake entry follows the **equipped item**; the shell UI is
**per-slot**. Compatible for v1; replacing an item drops its transmog. v2 polish: re-apply
per-slot preference on `OnPlayerEquip`.

### 9.3 Client collections wiring

- The Work collections module is a **visual shell with stub seams**:
  `modules/collections/core/stub.lua` (`SEAM: OUTBOUND` = `ezCollections:SendAddonCommand`,
  `SEAM: INBOUND` = `ezCollections:RaiseEvent`). Wire OUTBOUND → `core.sendToServer(CS.*)`,
  INBOUND → `core.onEventReceived(SS.*)` handlers that populate `ezCollections.Collections.*` +
  `TransmogSlots` and RaiseEvent the matching UI events.
- `transmog_backing.lua` already implements `C_TransmogCollection` (visual = representative itemID;
  collected iff displayID ∈ `Collections.Appearances`).
- **Regenerate catalogs for OUR item set** (the dump's `appearances_data.lua` is Ashendor's):
  run the §1 query pattern from `collections/server/collections.sql`
  (item_template class IN (2,4), InventoryType filter, Quality 0–6) → emit Lua rows into
  `collections/Data/appearances_data.lua`. Keep the hand-curated `mounts_data.lua` /
  `pets_data.lua` / `item_to_mount.lua` catalogs as-is (they're spell-id-keyed stock data with
  rich tooltips) — review tooltips for Ebonhold branding ("Legacy", etc.) during rebrand.

---

## 10. Protocol reference

**Transport:** prefix `NXSRV`, self-whisper, chunking `@mid idx/total` (180 chars), dispatch by
numeric opcode. Bodies are space/tilde separated ASCII; `:` = record fields.

**Client → Server (`CS`):**

| # | Name | Body |
|---|---|---|
| 1 | REQUEST_TALENT_STATE | `""` |
| 2 | REQUEST_PURCHASE_TALENT | `nodeId:rank nodeId:rank ...` (full target map) |
| 3 | REQUEST_REFUND_TALENT | `nodeId` |
| 10 | REQUEST_COLLECTIONS | `""` \| `mounts` \| `pets` \| `appearances` \| `transmog` |
| 12 | REQUEST_APPLY_TRANSMOG | `slot:item slot:item ...` (item `0`=hidden, `-1`=clear) |
| 13 | REQUEST_CLEAR_TRANSMOG | `slot` \| `""` (all) |

**Server → Client (`SS`):**

| # | Name | Body |
|---|---|---|
| 1 | SEND_TALENT_STATE | `primerisCount~nodeId:rank,nodeId:rank,...` (primerisCount is the server-authoritative balance) |
| 2 | SEND_PURCHASE_RESULT | `ok` \| `err:reason` |
| 3 | SEND_REFUND_RESULT | `ok:refunded:nodeId,nodeId,...` \| `err:reason` |
| 10 | SEND_COLLECTED_MOUNTS | `spellId spellId ...` |
| 11 | SEND_COLLECTED_PETS | `spellId spellId ...` |
| 12 | SEND_COLLECTED_APPEARANCES | `displayId displayId ...` |
| 13 | SEND_TRANSMOG_SLOTS | `slot:item[:illusion] ...` (item `0`=hidden) |
| 15 | SEND_TRANSMOG_SLOT_UPDATE | `slot:item` (reply to apply/clear) |

Snapshots replace the whole set; the client re-pulls on login + on journal/tree open.

---

## 11. Config reference

```
# mod-talent (talent.conf.dist)
Talent.Enable = 1
Talent.Primeris.BaseMin = 5
Talent.Primeris.BaseMax = 10
Talent.Primeris.LevelBonus = 5
Talent.Primeris.EliteMultiplier = 3
Talent.Primeris.NotifyGain = 1

# mod-collections (collections.conf.dist)
Collections.Enable = 1
Collections.EnableMounts = 1
Collections.EnablePets = 1
Collections.EnableTransmog = 1

# mod-transmog — keep current generated config (UseCollectionSystem=1 etc.)
```

---

## 12. Implementation order

1. **Adopt Spell.dbc**: copy Work's into `env/dist/bin/dbc/`; regen client patch (reagent cleanup);
   rebuild + boot smoke test (no module work yet).
2. **Import mod-transmog SQL**; restart; verify `.transmog check` + auto-unlock on a test loot.
3. **mod-talent**: generator → seed SQL; drop handler; purchase/refund/apply; `character_primeris`;
   addon protocol server side.
4. **mod-collections**: mounts/pets account-wide; transmog bridge; collection protocol server side.
5. **NexusServer addon**: transport core → Fury module (layer fix + restyle) → skillTree UI →
   collections shell wiring → progression hub; rebrand.
6. **Client patch**: assemble `latest-mpq-patch/` (addon, Spell.dbc, SpellIcon
   optional) + README; the **operator** (never an agent — agents cannot pack MPQs) packages
   `patch-4.MPQ` manually with an MPQ editor; WDB wipe.
7. **In-game verification** (§13 checklist) + this spec's as-built notes.

## 13. Verification checklist (v1)

- Drops: level-1 mob ≈ 10–15; level-80 ≈ 800–1,200; elite ≈ ×3; party members each get theirs.
- Talent UI shows Primeris balance (bottom bar); spend/refund updates it live; balance persists
  across relog.
- Purchase: prerequisites enforced; balance enforced; auras apply to all online account chars and
  persist across relog.
- Refund: 100% back; cascade refunds dependents; auras removed.
- Transmog: loot BoP item → appearance collected (account-wide) → Collections→Transmog tab shows
  it → apply per slot → visual changes, persists across relog, follows the item.
- Mounts/pets: learn on char A → available on char B (login grant + live grant).
- Instance maps render in-game (`M`); QOLFP pins still align (regen ZoneData).
- Fury bar: fill never covers border/text; restyle visible.

## 14. Deferred to v2 (explicitly out of v1)

- DUMMY-aura talent effects (gathering/crafting yield, Lucky Draw, etc.) — server handlers.
- Per-slot transmog persistence across item replacement (`OnPlayerEquip` re-apply).
- Live appearance delta pushes (`SEND_APPEARANCE_LEARNED`).
- Variant-item icons (ItemDisplayInfo/displayid pipeline).
- Loadouts/echoes/perks/checkpoint/torment/quest-tracker etc. (Ebonhold systems not requested).
- Price bracket scaling (if endgame flat prices ever feel too cheap).

---

## 15. As-built notes (21/08/2026 — implementation round 1)

- **Modules built + smoke-verified** (`wow-build`): mod-talent, mod-collections compile and link;
  worldserver boots clean with the 55,625-row Spell.dbc, loads 812 talent nodes / 805 parent edges,
  tracks 396 mount + 176 pet spells, and starts the transmog appearance cache. No errors.
- **Round 2 fixes (22/08/2026):**
  - `[1054] Unknown column 'fake_entry'` — **fixed**: mod-collections queried `custom_transmogrification`
    with snake_case (`guid`, `fake_entry`, `owner`) but the table (from mod-transmog's trasmorg.sql)
    is CamelCase (`GUID`, `FakeEntry`, `Owner`). Query corrected; rebuild + smoke verified (no error).
  - **Fury minimap button invisible** — the TGA path in fury.lua pointed at the old addon folder
    (`Interface\AddOns\NexusFrames\NexusFramesMinimap`); fixed to `NexusServer` and the TGA copied
    into the addon. Primary entry point is the minimap ring button (LibDBIcon pattern); the micro
    button (stock textures) is a bonus toggle.
  - **Micro-bar button missing** — root cause was the **dual-addon collision**: `patch-4` had shipped
    the old NexusFrames addon alongside NexusServer (same frame names + same `AzerothCore\t` channel).
    Fix applied: `Interface\AddOns\NexusFrames` is no longer packed (keep Item.dbc/SpellItemEnchantment.dbc
    + QoLFlightPaths). Documented in latest-mpq-patch/README.md.
  - **skillTreeMicroButton dropped** from the toc — Ebonhold shipped it hidden (replaced by their
    progression button) and it references missing assets (`inv_soulash`, `ui-microbuttonstreamdl-*`).
    Entry point instead: **`/talents`** slash command (added to skillTree_service.lua + a
    `SkillTree.Toggle` export in skillTree.lua that shows the tree inside CollectionsJournal).
  - **Staging folder nesting fixed** (`AddOns/NexusServer/NexusServer/...` → flat), and the addon is
    re-synced into latest-mpq-patch after every edit.
- **Round 3 (22/08/2026) — single tabbed journal window:**
  - **The green UI root cause was the nested `assets/assets/` folder** (same `cp -r` nesting bug) —
    every `ProjectEbonhold\assets\...` ref failed → default solid green. Flattened; full texture
    audit now shows 0 missing refs across all loaded files.
  - **Tab content binding rewritten** (`modules/journal/journal_binding.lua`, loaded last): overrides
    the retail `CollectionsJournal_UpdateSelectedTab` so the five tabs are
    **1 Fury · 2 Talent Tree · 3 Mounts · 4 Companions · 5 Transmogrify**. Previously the retail
    binding showed MountJournal on tab 1 / PetJournal on tab 2 (why mounts appeared under
    "Echoes") and nothing on the transmog tab. Tabs relabelled in Blizzard_Collections.xml.
  - **Fury absorbed into tab 1**: fury.lua's standalone window replaced by `NexusFuryPanel`
    (child of CollectionsJournal, built on PLAYER_LOGIN); compact bar stays (taller 34px +
    explicit frame levels so fill never covers text/border — the SetDrawLayer alone wasn't
    enough); minimap/micro/compact buttons all open the journal.
  - **Primeris counter**: the tree's bottom-bar `pointsText` now has data — added
    `REQUEST_TALENT_STATE` pulls on PLAYER_LOGIN and on every tab-2 open (the rewritten service
    previously never pulled, so the counter would have stayed empty).
  - **skillTreeMicroButton** dropped (Ebonhold shipped it hidden + missing assets); `/talents`
    opens the tree via the journal.
- **Round 4 (22/08/2026) — the real green bug + the disappearing tabs:**
  - **The green was the addon FOLDER NAME, not missing files**: every shell texture path is
    `Interface\AddOns\ProjectEbonhold\...` but the addon is packaged as `AddOns\NexusServer\` —
    all 515+ path refs pointed at a non-existent folder → default solid green. Rewrote the path
    prefix to `AddOns\NexusServer` across all lua/xml (the `ProjectEbonhold.` namespace refs are
    untouched). Earlier audits missed this because the resolution base was wrong. The nested
    `assets/assets/` fix was real but not the cause.
  - **Tabs 3/5 closed the journal**: the retail tab template's OnClick treats tab id 3 as the
    standalone-wardrobe switch (`HideUIPanel(CollectionsJournal)` + show WardrobeFrame) — with
    our relabel "Mounts" = id 3 that hid the journal; tab 5 embedded WardrobeFrame whose retail
    OnShow also calls `HideUIPanel(CollectionsJournal)`. Fixed in journal_binding.lua: all five
    journal tabs get a direct `CollectionsJournal_SetTab` OnClick, and `WardrobeTransmogFrame`'s
    OnShow is replaced with an embed-safe version (Ebonhold's, minus the journal-hide).
  - Case-variant texture refs (`Interface\ICONS\` etc.) resolve on Windows (case-insensitive);
    the shell's `Sounds/` folder created from the bundled wavs.
- **Module SQL is auto-applied by worldserver's DBUpdater** (observed in the boot log: applied
  `001_mod_talent_primeris.sql`, `001_mod_talent_nodes.sql`, transmog claim strings) — no manual
  import needed beyond what was done; tables confirmed created.
- **Addon**: internal namespace kept as `ProjectEbonhold` (copied UI modules bind to it);
  user-facing brand = NexusServer; display strings rebranded Soul Ashes/Soul Points → Primeris.
  `options/` module ships but is NOT loaded in v1 (strips references to removed Ebonhold modules).
  `progression/` also not loaded (references the stripped Echo Journal).
- **Skill tree service rewritten** for the Primeris protocol; right-click refund now sends
  `REQUEST_REFUND_TALENT` (server cascades + refreshes) instead of local bookkeeping.
- **Slot convention on the transmog wire is 0-based EQUIPMENT_SLOT** (confirmed in the shell's
  `ApplyAllPending` comment: "server wants 0-based EQUIPMENT_SLOT"); server modules already follow it.
- **SpellIcon.dbc (Work's, 33,989 rows) added to the client patch** so custom talent spells render
  real icons.
- **`collections_service.lua` is the server seam** (sends CS.REQUEST_COLLECTIONS, registers all
  SS handlers) — no separate bridge file needed.
- **Outstanding**: regenerate `appearances_data.lua` for our item set; addon only Lua-scanned
  (no interpreter here) — verify in-client; in-game tests per §13; server restart by operator.
- Stock v16 Spell.dbc (49,839 rows) backed up at `/tmp/Spell.dbc.stock-v16.bak`.

## 16. Sources / reference paths

- `client-resources/Work/Interface/AddOns/ProjectEbonhold/modules/skillTree/` — tree UI + data.
- `client-resources/Work/Interface/AddOns/ProjectEbonhold/modules/collections/PROTOCOL.md` —
  the collections wire contract this design implements.
- `client-resources/Work/Interface/AddOns/ProjectEbonhold/modules/collections/server/collections.sql`
  — catalog generation + identifier model.
- `modules/mod-transmog/` — engine (built); `src/Transmogrification.{h,cpp}`, `transmog_scripts.cpp`.
- `modules/mod-fury/src/fury.cpp` — kill/drop/party pattern + account-wide apply pattern.
- `client-resources/NexusFrames/NexusFrames.lua` — Fury UI to fold into NexusServer.
- Facts verified 20–21/08/2026: TC 3.3.5 has no currency-count opcode; stock CurrencyTypes.dbc
  item-backed (bits 1–29 used); `PLAYERHOOK_ON_LEARN_SPELL` exists; Work Spell.dbc format
  identical to ours (234 fields/936 rows).
