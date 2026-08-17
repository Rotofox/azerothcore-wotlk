# Fury/NexusFrames v2 — Implementation Plan

Authoritative design: `specs/fury-nexusframes-v2-design.md` (approved, do NOT re-design).
Supporting docs read: `specs/fury-nexusframes-design.md` (v1), `specs/db8e1683_item-quality-random-enchants.md`,
`documentation/fury-nexusframes-handoff.md`, `client-resources/README.md`.

## 0. Mode & hard constraints (reaffirmed)

- **NO git operations** (`--no-commit`): no add/commit/push/pull/checkout/reset/clean. Modules are gitignored clones.
- **NO build**: no cmake/make/ninja, no compile or syntax-check via any toolchain, no worldserver/authserver start, no MPQ packing, no DBC patching. `adws/adw_modules/quality.py` is a placeholder — "done" = coherent code + reviewer approval.
- **Live DBs/worldserver are READ-ONLY**: query for verification only; never apply SQL. The factory MAY run the two Python generators (file output only). The engineer applies SQL + recompiles + repacks + smoke-tests manually.
- Every line number below was re-verified against the live tree this session (see §7.6).

---

## 1. Re-verified facts (live tree, this session)

| Fact | Verification |
|---|---|
| `Item::GetItemRandomPropertyId()` returns `int32` (sign: + = RandomProperty, − = RandomSuffix) | `Item.h:295` |
| `Item::SetItemRandomProperties(int32)` — **ONE arg, no Player\*** in this fork; writes PROP slots 7..11; calls `SetState(ITEM_CHANGED, GetOwner())` when the id changes; suffixes also call `UpdateItemSuffixFactor()` | `Item.h:297`, `Item.cpp:668-720` |
| `GenerateEnchSuffixFactor(item_id)` — from the item template's `ItemLevel` via `RandPropPoints`; `RandomSuffix=0` ⇒ returns 0; variant copies base ItemLevel ⇒ factor unchanged by rank swap | `ItemEnchantmentMgr.cpp:125+` |
| `Player::GetSpec(int8 spec = -1)` → `uint32` tree id (default −1 = active spec; computes from talent points); `GetActiveSpec()` → `uint8` | `Player.h:1746/1733`, `Player.cpp:16047` |
| `Unit::GetShapeshiftForm()` → `ShapeshiftForm`; `FORM_CAT=0x01`, `FORM_BEAR=0x05`, `FORM_DIREBEAR=0x08` | `Unit.h:1874`, `UnitDefines.h:70-78` |
| `Archetype` enum (4 values) + `ArchetypeFromString` (no AGILITY) + pool arrays `ARMOR_POOLS[4]`/`JEWELRY_POOLS[4]`/`RELIC_POOLS[4]` indexed by `uint32(archetype)`; `WEAPON_POOLS[3]` indexed by weapon pool | `random_enchants.h:43-50`, `random_enchants.cpp:58-64, 170-192` |
| `swapToVariant` destructive block (to remove): `random_enchants.cpp:477-484` | zeroes `ITEM_FIELD_RANDOM_PROPERTIES_ID`, `ITEM_FIELD_PROPERTY_SEED`, clears slots 7..11 |
| Enchant slots: `PROP_ENCHANTMENT_SLOT_0..4 = 7..11`; module matrix rolls `slotEnch[3] = {7,8,9}` | `random_enchants.cpp:331` |
| TalentTab.dbc exists (33 recs); ALL 30 canonical tree ids verified present with correct spec names (§7.1) | `env/dist/bin/dbc/TalentTab.dbc` |
| `ItemRandomProperties.dbc` (2012 recs, max id 2164), `ItemRandomSuffix.dbc` (95 recs, max id 99), `SpellItemEnchantment.dbc` (2656 recs) all exist at `env/dist/bin/dbc/` | parsed this session |
| `mod_re_class_archetype`: `class_id`, `archetype varchar(16)`, PK class_id — seeds in `001_mod_re_rates.sql:149-163` | v1 fallback table |
| `item_template` dump: 139 cols; `BuyPrice` idx 10, `SellPrice` idx 11, `RandomProperty` idx 110, `RandomSuffix` idx 111 | `data/sql/base/db_world/item_template.sql` |
| Addon transport: `CHAT_MSG_ADDON` primary + `CHAT_MSG_WHISPER` fallback + dedup + filtered seterrorhandler — DO NOT TOUCH | `NexusFrames.lua:88-105, 291-362` |
| LibDBIcon minimap pattern: 31×31 button parented to `Minimap`, `RegisterForDrag("LeftButton")`, bg `Interface\Minimap\UI-Minimap-Background`, ring `Interface\Minimap\MiniMap-TrackingBorder`, icon `SetTexCoord(0.05,0.95,0.05,0.95)` | `example-addons/.../LibDBIcon-1.0/LibDBIcon-1.0.lua:170-226` |

---

## 2. Deliverable 1 — NexusFrames addon (client-only)

File: `client-resources/NexusFrames/NexusFrames.lua` (toc unchanged). **Targeted edits only — no wholesale rewrite.**
Do NOT touch: transport (lines 88-105 + 291-362), compact bar (712-767), reward list (456-629), tier colors, scroll, `NexusFramesDB.barPos`/SavedVariables keys, `ToggleWindow` body (397-405).

### 2.1 Minimap button (primary window toggle)
Insert a new block **after the micro button section (ends line 799) and before the slow-poll `window:SetScript("OnUpdate", ...)` at line 802** (ToggleWindow is defined at 397, so order is safe). There are currently ZERO other `Minimap` references in the file — this is the first.)

Pattern = LibDBIcon look + the compact-bar drag/persist (v2 spec §6.1 verbatim: reuse the existing single toggle path):

```lua
-- Minimap button (v2 D1) — circular ring look, drag to move, position persisted.
local minimapButton = CreateFrame("Button", "NexusFramesMinimapButton", Minimap)
minimapButton:SetSize(32, 32)
minimapButton:SetFrameStrata("MEDIUM")
minimapButton:SetFrameLevel(8)
minimapButton:SetClampedToScreen(true)
minimapButton:SetMovable(true)
minimapButton:EnableMouse(true)
minimapButton:RegisterForDrag("LeftButton")

local ring = minimapButton:CreateTexture(nil, "BACKGROUND")
ring:SetSize(32, 32)
ring:SetTexture("Interface\\Minimap\\UI-Minimap-Background")   -- circular minimap-bg look
ring:SetPoint("CENTER")

local border = minimapButton:CreateTexture(nil, "OVERLAY")
border:SetSize(42, 42)
border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder") -- LibDBIcon ring
border:SetPoint("CENTER")

minimapButton:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
minimapButton:SetScript("OnClick", function() ToggleWindow() end)
minimapButton:SetScript("OnDragStart", function(self) self:StartMoving() end)
minimapButton:SetScript("OnDragStop", function(self)
    self:StopMovingOrSizing()
    local point, _, relativePoint, x, y = self:GetPoint()
    NexusFramesDB.minimapPos = { point = point, relativePoint = relativePoint, x = x, y = y }
end)
minimapButton:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:AddLine("NexusFrames")
    GameTooltip:Show()
end)
minimapButton:SetScript("OnLeave", function() GameTooltip:Hide() end)

-- Guarded restore — same pattern as barPos (compactBar, lines 764-767), anchored to Minimap.
if NexusFramesDB.minimapPos and NexusFramesDB.minimapPos.point and NexusFramesDB.minimapPos.relativePoint then
    minimapButton:SetPoint(NexusFramesDB.minimapPos.point, Minimap, NexusFramesDB.minimapPos.relativePoint,
        NexusFramesDB.minimapPos.x or 0, NexusFramesDB.minimapPos.y or 0)
else
    minimapButton:SetPoint("TOPLEFT", Minimap, "TOPLEFT", 55, -5)
end
```

Notes:
- The drag saves `GetPoint()` (relative frame will be `Minimap` since the button is its child); the guarded restore re-anchors to `Minimap` — same nil-guard shape as `barPos`.
- `SetClampedToScreen(true)` + `StartMoving`/`StopMovingOrSizing` are the drag contract (v2 spec §6.1; matches WeakAuras `SetMovable` patterns).
- Keep the existing micro-bar button (`microButton`, lines 776-800) **unchanged** (harmless bonus toggle).
- `NexusFramesDB.minimapPos` is a NEW SavedVariables key — allowed (only `barPos` is "already in use"; the key namespace `NexusFramesDB` is shared by design).

### 2.2 Double-%% fix (bug)
`FormatPct` (line 97) already appends `%`. Fix both sites from `"+%s%% Haste"` to `"+%s Haste"`:
1. Line 262 (level-up popup): `string.format("+%s%% Haste", FormatPct(FURY_HASTE_PER_LEVEL))` → `string.format("+%s Haste", FormatPct(FURY_HASTE_PER_LEVEL))`
2. Line 564 (reward-list haste line): `hasteText:SetText(string.format("+%s%% Haste", FormatPct(FuryHasteAt(level))))` → `hasteText:SetText(string.format("+%s Haste", FormatPct(FuryHasteAt(level))))`

### 2.3 Popup border removal (lines 225-232)
Replace the popup backdrop with a flat translucent background, **no border**:
- `popup:SetBackdrop({...})` (225-230): drop `edgeFile`, `edgeSize`, `insets`; keep `bgFile = "Interface\\Tooltips\\UI-Tooltip-Background"` + `tile = true, tileSize = 16`.
- Keep `popup:SetBackdropColor(0, 0, 0, 0.92)` (231) — dark translucent bg keeps the gold text readable.
- Remove `popup:SetBackdropBorderColor(COLOR_GOLD[...], 1)` (232) — no border color, no new border elements.

Verify: read the diff — only the three targeted changes (§2.1-2.3) in the lua; transport/bar/reward-list/scroll untouched.

---

## 3. Deliverable 2 — mod-fury spec-aware primary stat

File: `modules/mod-fury/src/fury.cpp` (header `fury.h` already includes `Player.h` — no include changes needed).

### 3.1 Replace `PrimaryStatForClass(uint8 classId)` (fury.cpp:136-156) with `PrimaryStatForSpec(Player*)`
```cpp
// Spec -> primary stat (v2 design §2). Tree ids verified against this fork's
// TalentTab.dbc (§7.1). Unknown tree -> class fallback (old map).
Stats PrimaryStatForSpec(Player* player)
{
    if (!player)
        return STAT_INTELLECT;

    switch (player->GetSpec(player->GetActiveSpec()))
    {
        // Holy paladin -> INT
        case 381: return STAT_INTELLECT;
        // Enhancement shaman -> AGI
        case 263: return STAT_AGILITY;
        // Feral druid (cat AND bear — Fury primary stays AGI regardless of form) -> AGI
        case 281: return STAT_AGILITY;
        // Warriors (Arms 161 / Prot 163 / Fury 164) -> STR
        case 161: case 163: case 164:
        // Paladin Prot 383 / Ret 381 -> STR (Holy 382 handled above)
        case 381: case 383:
        // Death Knight (Blood 398 / Frost 399 / Unholy 400) -> STR
        case 398: case 399: case 400:
            return STAT_STRENGTH;
        // Hunters (361/363/362) + Rogues (182/181/183) -> AGI
        case 361: case 362: case 363:
        case 181: case 182: case 183:
            return STAT_AGILITY;
        // Priests (201/202/203), Mages (81/41/61), Warlocks (302/303/301),
        // Elemental/Resto Shaman (261/262), Balance/Resto Druid (283/282) -> INT
        case 201: case 202: case 203:
        case 81: case 41: case 61:
        case 302: case 303: case 301:
        case 261: case 262:
        case 283: case 282:
            return STAT_INTELLECT;
        default:
            break;
    }

    // Class fallback for unknown/unspecced trees (v1 map, design §2).
    switch (player->getClass())
    {
        case CLASS_WARRIOR:
        case CLASS_PALADIN:
        case CLASS_DEATH_KNIGHT:
            return STAT_STRENGTH;
        case CLASS_HUNTER:
        case CLASS_ROGUE:
            return STAT_AGILITY;
        default:
            return STAT_INTELLECT;  // priest/shaman/mage/warlock/druid + unknown
    }
}
```
**Watch the duplicate `case 381`** (paladin appears in both the Holy→INT branch and the STR branch above — the sketch is illustrative; the builder must emit each id exactly ONCE; suggested clean layout: a single switch with STR ids {161,163,164,381,383,398,399,400}, AGI ids {361,362,363,181,182,183,263,281}, INT ids {382,201,202,203,81,41,61,302,303,301,261,262,283,282}).

### 3.2 Update the two call sites (already per-character)
- Line 197 (`ApplyFullRewards`): `player->ApplyStatBuffMod(PrimaryStatForClass(player->getClass()), float(primary), true);` → `PrimaryStatForSpec(player)`.
- Line 233 (`ApplyRewardDelta`): same swap.
- Spec is read fresh at login/level-up/gain — no spec-change hook needed (v2 §2). No config key this pass.

Verify: both call sites compile-shaped; no other references to `PrimaryStatForClass` remain (`grep`).

---

## 4. Deliverable 3 — spec-aware archetype + form-aware feral + 5-role pools

Files: `modules/mod-random-enchants/src/random_enchants.h`, `.../random_enchants.cpp`,
`modules/mod-random-enchants/data/sql/db-world/004_mod_re_spec_archetype.sql` (new),
`modules/mod-random-enchants/conf/random_enchants.conf.dist`.

### 4.1 Enum + ArchetypeFromString (5 roles)
- `random_enchants.h:43-50`: append `ARCH_AGILITY` **at the end** of `enum Archetype` → `{ ARCH_CASTER, ARCH_HEALER, ARCH_PHYSICAL, ARCH_TANK, ARCH_AGILITY }` (index 4; existing indices stay stable).
- `random_enchants.cpp:58-64` `ArchetypeFromString`: add `if (s == "AGILITY") return ARCH_AGILITY;` (before the PHYSICAL default).

### 4.2 Pools — extend to 5 slots (keep weights reasonable; no balance pass)
Add three new pool defs (v2 §1 per-role philosophy):
```cpp
// AGILITY pool (v2 §1): AGI-leaning.
PoolStat const ARMOR_AGILITY[] = {
    { "AGI", ITEM_MOD_AGILITY, 40.0f }, { "AP", ITEM_MOD_ATTACK_POWER, 20.0f },
    { "CRIT", ITEM_MOD_CRIT_RATING, 15.0f }, { "HASTE", ITEM_MOD_HASTE_RATING, 12.0f },
    { "HIT", ITEM_MOD_HIT_RATING, 8.0f }, { "EXP", ITEM_MOD_EXPERTISE_RATING, 5.0f }
};
PoolStat const JEWELRY_AGILITY[] = {
    { "AGI", ITEM_MOD_AGILITY, 50.0f }, { "AP", ITEM_MOD_ATTACK_POWER, 30.0f },
    { "CRIT", ITEM_MOD_CRIT_RATING, 20.0f }
};
PoolStat const RELIC_AGILITY[] = { { "AGI", ITEM_MOD_AGILITY, 100.0f } };
```
- Extend `ARMOR_POOLS` / `JEWELRY_POOLS` / `RELIC_POOLS` from `[4]` to `[5]` (random_enchants.cpp:170-192), appending the AGILITY entry at index 4 with key prefixes `pool_weight:AGILITY` / `jewelry_weight:AGILITY` / `relic_weight:AGILITY`. **Do not reorder the existing 4 entries** (indexing must stay `uint32(archetype)`).
- `WEAPON_POOLS[3]` stays 3-wide (indexed by weapon pool, not archetype — no change).
- **Feral-bear "AGI still present"**: add AGI into the shared `ARMOR_TANK` def (random_enchants.cpp:117) at a modest weight so the bear pool is TANK-flavoured yet keeps AGI (v2 §1, §3). Suggested: `STA 40, STR 15, AGI 10, DEF 12, DODGE 8, PARRY 5, HIT 5, EXP 5` (relative weights; exact values tunable). Document this trade-off in a comment: the light AGI also applies to plate tanks on this fun server (accepted — no balance pass).

### 4.3 `getArchetype(Player*)` — spec-aware resolution (random_enchants.cpp:487+)
Resolution order (v2 §3):
1. **Spec table**: `SELECT archetype FROM {RandomEnchants.SpecArchetypeTable default "mod_re_spec_archetype"} WHERE spec_id = {} LIMIT 1` with `spec_id = player->GetSpec(player->GetActiveSpec())`. If a row exists → `ArchetypeFromString(row)`.
2. **Class table**: existing `mod_re_class_archetype` query (unchanged).
3. **Hard-coded map** (existing fallback, unchanged).
Then, **feral form-awareness (pools only)**: after resolution, if `player->getClass() == CLASS_DRUID && result == ARCH_AGILITY` and `player->GetShapeshiftForm() == FORM_BEAR || == FORM_DIREBEAR` → return `ARCH_TANK` (TANK-flavoured pool, AGI present via §4.2). `FORM_CAT`/none → stay `ARCH_AGILITY`. Fury primary is NOT affected (that's mod-fury, §3).

Suggested shape:
```cpp
Archetype getArchetype(Player* player)
{
    if (player)
    {
        uint32 specId = player->GetSpec(player->GetActiveSpec());
        std::string specTable = sConfigMgr->GetOption<std::string>("RandomEnchants.SpecArchetypeTable", "mod_re_spec_archetype");
        QueryResult specResult = WorldDatabase.Query("SELECT archetype FROM {} WHERE spec_id = {} LIMIT 1", specTable, specId);
        if (specResult)
        {
            Archetype arch = ArchetypeFromString(specResult->Fetch()[0].Get<std::string>());
            // Feral bear: TANK-flavoured pool with AGI still present (v2 §3).
            if (player->getClass() == CLASS_DRUID && arch == ARCH_AGILITY)
            {
                ShapeshiftForm form = player->GetShapeshiftForm();
                if (form == FORM_BEAR || form == FORM_DIREBEAR)
                    return ARCH_TANK;
            }
            return arch;
        }
        // ... existing class-table query ...
    }
    // ... existing hard-coded fallback ...
}
```

### 4.4 New SQL `data/sql/db-world/004_mod_re_spec_archetype.sql`
Idempotent (CREATE TABLE IF NOT EXISTS + REPLACE INTO), same house style as 001:
```sql
CREATE TABLE IF NOT EXISTS `mod_re_spec_archetype` (
  `spec_id`   int unsigned NOT NULL,      -- TalentTab.dbc tree id
  `archetype` varchar(16) NOT NULL,       -- CASTER | HEALER | PHYSICAL | TANK | AGILITY
  `note`      varchar(64) DEFAULT NULL,
  PRIMARY KEY (`spec_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

REPLACE INTO `mod_re_spec_archetype` (`spec_id`,`archetype`,`note`) VALUES
(161,'PHYSICAL','Warrior Arms'), (163,'TANK','Warrior Protection'), (164,'PHYSICAL','Warrior Fury'),
(381,'PHYSICAL','Paladin Retribution'), (382,'HEALER','Paladin Holy'), (383,'TANK','Paladin Protection'),
(361,'AGILITY','Hunter Beast Mastery'), (363,'AGILITY','Hunter Marksmanship'), (362,'AGILITY','Hunter Survival'),
(182,'AGILITY','Rogue Assassination'), (181,'AGILITY','Rogue Combat'), (183,'AGILITY','Rogue Subtlety'),
(201,'HEALER','Priest Discipline'), (202,'HEALER','Priest Holy'), (203,'CASTER','Priest Shadow'),
(398,'TANK','Death Knight Blood'), (399,'PHYSICAL','Death Knight Frost'), (400,'PHYSICAL','Death Knight Unholy'),
(261,'CASTER','Shaman Elemental'), (263,'AGILITY','Shaman Enhancement'), (262,'HEALER','Shaman Restoration'),
(81,'CASTER','Mage Arcane'), (41,'CASTER','Mage Fire'), (61,'CASTER','Mage Frost'),
(302,'CASTER','Warlock Affliction'), (303,'CASTER','Warlock Demonology'), (301,'CASTER','Warlock Destruction'),
(283,'CASTER','Druid Balance'), (281,'AGILITY','Druid Feral'), (282,'HEALER','Druid Restoration');
```
(30 rows = the full v2 §1 matrix; ids verified §7.1.)

### 4.5 conf
Add to `conf/random_enchants.conf.dist` (comment + key, minimal):
```
#     RandomEnchants.SpecAware
#        Spec-aware archetype resolution (v2). When 0, falls back to the
#        class table (v1 behavior). Default: 1
RandomEnchants.SpecAware = 1
#     RandomEnchants.SpecArchetypeTable
#        Table name for the spec -> archetype matrix. Default: mod_re_spec_archetype
RandomEnchants.SpecArchetypeTable = "mod_re_spec_archetype"
```
Builder: gate the spec-table lookup on `RandomEnchants.SpecAware` (default 1) so the feature is disable-able; the class-table + hard-coded fallbacks remain the default path when the flag is off or the row is missing.

---

## 5. Deliverable 4 — empower-not-rewrite

Files: `.../random_enchants.cpp`, `.../data/sql/db-world/005_mod_re_suffix_boost.sql` (new),
`.../tools/generate_suffix_boost.py` (new), `.../conf/random_enchants.conf.dist`.

### 5.1 `swapToVariant` (random_enchants.cpp:462-485)
- **Remove the destructive block (lines 477-484)** — the `if (item->GetItemRandomPropertyId() != 0) { SetInt32Value(ITEM_FIELD_RANDOM_PROPERTIES_ID, 0); SetUInt32Value(ITEM_FIELD_PROPERTY_SEED, 0); loop slots 7..11 SetEnchantment(0); SetState(ITEM_CHANGED, player); }`.
- Capture the instance's random property id **before** `SetEntry` (SetEntry does not clear instance fields, but capture-first is the safe order):
```cpp
void swapToVariant(Player* player, Item* item, uint32 variantEntry)
{
    int32 randomPropId = item->GetItemRandomPropertyId();   // preserve instance suffix/property

    item->SetEntry(variantEntry);
    item->SetState(ITEM_CHANGED, player);

    // v2 empower-not-rewrite: a RandomProperty/RandomSuffix item keeps its
    // suffix and gets a rank boost instead of being wiped.
    if (randomPropId != 0)
        BoostRandomProperty(player, item, randomPropId);
}
```

### 5.2 New helper `BoostRandomProperty` (module scope, near swapToVariant)
```cpp
// v2 suffix rank boost: from_id = |GetItemRandomPropertyId()| -> to_id via
// mod_re_suffix_boost; re-applies with the same sign. Never touches ilvl /
// RequiredLevel. Capped family (no row) -> skip + log, never error.
void BoostRandomProperty(Player* player, Item* item, int32 randomPropId)
{
    uint32 fromId = uint32(std::abs(randomPropId));
    std::string table = sConfigMgr->GetOption<std::string>("RandomEnchants.SuffixBoostTable", "mod_re_suffix_boost");
    QueryResult result = WorldDatabase.Query("SELECT to_id FROM {} WHERE from_id = {} LIMIT 1", table, fromId);
    if (!result)
    {
        LOG_INFO("module", "RandomEnchants: no suffix-boost ladder row for {} (capped family) — skipping boost", fromId);
        return;
    }
    int32 toId = result->Fetch()[0].Get<int32>();
    if (toId == 0 || uint32(std::abs(toId)) == fromId)
        return;
    int32 sign = randomPropId < 0 ? -1 : 1;
    item->SetItemRandomProperties(sign * toId);   // one-arg in this fork (Item.h:297)
    item->SetState(ITEM_CHANGED, player);         // persist (design §4.2)
    LOG_INFO("module", "RandomEnchants: boosted random property/suffix {} -> {}", fromId, uint32(std::abs(toId)));
}
```
Notes:
- `SetItemRandomProperties` internally re-writes slots 7..11 and (for suffixes) `UpdateItemSuffixFactor()` — which reads `GenerateEnchSuffixFactor(GetEntry())` from the **variant** entry; the variant copies the base `ItemLevel`, so the factor is unchanged (rank swap never touches ilvl/RequiredLevel). `std::abs` needs `<cstdlib>` or use `randomPropId < 0 ? -randomPropId : randomPropId` (avoid overload ambiguity with int32).
- No ladder row ⇒ skip + module-log (capped family), never error, never invent data.
- Add `RandomEnchants.SuffixBoostTable = "mod_re_suffix_boost"` to the conf.dist (same style as §4.5).

### 5.3 `rollQualityAndEnchant` — skip matrix roll on random-property items (random_enchants.cpp:316-363)
After the base-quality guard (line 318) and before/inside the enchant step, when the item carries a random property/suffix the matrix roll on slots 7..9 is skipped (the suffix owns 7..11; empowerment = variant stat upgrade + suffix rank boost, both already handled):
```cpp
    // v2 empower-not-rewrite: a RandomProperty/RandomSuffix item's PROP slots
    // 7..11 are owned by the suffix — skip the matrix chained roll entirely.
    if (item->GetItemRandomPropertyId() != 0)
        return false;   // (or skip only the roll; no chat message for suffix-owned items)
```
Placement decision: put the check right after the quality roll block (after line 314) and before the enchant-roll section — suffix items exit before the `baseQuality` chat path. Suffix-free items keep the exact current chained 70/65/60 roll on 7..9. (If the builder prefers to keep the chat-message path, return `false` after skipping — the message only fires when enchants are applied, so exiting before the roll is behaviorally identical.)

### 5.4 New SQL `data/sql/db-world/005_mod_re_suffix_boost.sql` (DDL only)
```sql
-- DDL only — seed rows are generated by tools/generate_suffix_boost.py (run by
-- the engineer against the client DBCs; do not hand-write ranks).
CREATE TABLE IF NOT EXISTS `mod_re_suffix_boost` (
  `from_id` int NOT NULL,
  `to_id`   int NOT NULL,
  PRIMARY KEY (`from_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 5.5 New tool `modules/mod-random-enchants/tools/generate_suffix_boost.py`
Header must document: purpose, required inputs (DBCs), and that it emits a SQL file + capped-family report — it never touches a database (the engineer applies the SQL).

Inputs (all exist at `env/dist/bin/dbc/` — verified):
- `ItemRandomProperties.dbc` — 2012 recs, max id 2164; fmt `nxiiiiissssssssssssssssx`: ID(0), InternalName(1), Enchantment[5](2-6), Name[16] strings(7-22), mask(23).
- `ItemRandomSuffix.dbc` — 95 recs, max id 99; fmt `nssssssssssssssssxxiiiiiiiiii`: ID(0), Name[16](1-16), 2 unused(17-18), Enchantment[5](19-23), AllocationPct[5](24-28).
- `SpellItemEnchantment.dbc` (third input for amount weighting; 2656 recs; fmt `niiiiiiixxxiiissssssssssssssssxiiiiiii` — effect type at field 2, PointsMin at field 3, EffectArg at field 10). Amount = PointsMin of the first `ITEM_ENCHANTMENT_TYPE_STAT(5)` effect.

CLI (house style follows `client-resources/generate_enchant_dbc_patch.py` / `generate_variants.py`: argparse, stdlib only):
```
python3 tools/generate_suffix_boost.py
    [--input-dbc DIR default env/dist/bin/dbc/]
    [--properties FILE] [--suffixes FILE] [--enchant FILE]   # per-file overrides
    [--out data/sql/db-world/005_mod_re_suffix_boost.sql]
    [--report tools/suffix_boost_capped_families.txt]
```
Algorithm:
1. Read all three DBCs (struct parse, `magic == b"WDBC"` assert, string-block offsets).
2. Group entries into families: **RandomSuffix** families by normalized Name (e.g. "of the Monkey"); **RandomProperty** families by normalized Name (e.g. "of Intellect", "of the Eagle"). Normalize: strip trailing whitespace/ids; if names include a numeric rank suffix, group by the non-numeric stem.
3. Per-entry weight = Σ over the 5 enchant slots of `amount(enchant_id) × allocPct/10000` (suffix) or `amount(enchant_id)` (property); amount resolved from SpellItemEnchantment.dbc (skip entries whose enchants don't resolve; keep them in the capped report).
4. Within each family sort by weight ascending → each rank's `to_id` = next higher rank (property ids positive, suffix ids negative in the table: store the sign per source DBC — the module looks up by `|id|` and re-applies the item's own sign, so the SQL stores plain positive `from_id`/`to_id` matching the DBC IDs).
5. Emit `005_mod_re_suffix_boost.sql` (`REPLACE INTO mod_re_suffix_boost (from_id,to_id) VALUES ...;` — idempotent) — DDL section already shipped in 5.4; the script may emit DDL+seed or seed-only appended after the 005 DDL (prefer: script emits **only** `REPLACE INTO` rows, since 005 ships the CREATE TABLE; note this in the header).
6. Capped families (highest rank of a family with no next) → print to stdout AND write `tools/suffix_boost_capped_families.txt` (one family + top id per line, with a header comment). This file is the handoff for the follow-up DBC-tier task.

House style to match: `read_dbc` like `client-resources/generate_enchant_dbc_patch.py:33-44`; argparse like `generate_variants.py`.

---

## 6. Deliverable 5 — variant vendor prices

File: `modules/mod-random-enchants/tools/generate_variants.py` (already read in full this session).

### 6.1 Add price multipliers
- Constants at the top (near `TIERS`, generate_variants.py L55-65):
```python
# v2 D5 — per-tier vendor price multipliers applied to BuyPrice/SellPrice.
TIER_PRICE_MULT = {1: 1.5, 2: 2.5, 3: 4.0, 4: 6.0, 5: 8.0}
```
- In `build_variant()` (after the verbatim copy `out = list(base.fields)` at L334, after the Quality overwrite at L342): apply to the variant row's `BuyPrice` and `SellPrice`:
```python
mult = TIER_PRICE_MULT[tier]
for col in ("BuyPrice", "SellPrice"):
    raw = base.raw(col)                       # verbatim raw token (may be 0)
    val = int(parse_token(raw)[1]) if parse_token(raw) else 0
    out[base.colidx[col]] = str(int(round(val * mult)))
```
(0-price items stay 0. Use the parsed numeric value, not string concatenation.)

### 6.2 Regenerate the variant SQL (deterministic, file output only)
Run:
```
python3 modules/mod-random-enchants/tools/generate_variants.py --all
```
default out → `modules/mod-random-enchants/data/sql/db-world/003_mod_re_variants.sql` (rewritten from scratch; input = `data/sql/base/db_world/item_template.sql` — exists, 139 cols). Expected: same row count as current (76,498 variant rows from 24,944 base items) with scaled BuyPrice/SellPrice. Sanity-check a couple of rows (e.g. entry 1000000: BuyPrice/SellPrice = base × 1.5).

### 6.3 Build-report note (builder must surface to the engineer)
The engineer must **re-apply `003_mod_re_variants.sql`** to the live world DB (and players must **delete `Cache\WDB` with the game closed** — standing gotcha) for the new prices to take effect. Do NOT apply it in this run.

---

## 7. Build-time verification items — findings (report these in the build report)

### 7.1 TalentTab ids vs `TalentTab.dbc` — **VERIFIED, all 30 canonical ids present**
161 Arms, 163 Protection, 164 Fury · 381 Retribution, 382 Holy, 383 Protection · 361 Beast Mastery, 363 Marksmanship, 362 Survival · 182 Assassination, 181 Combat, 183 Subtlety · 201 Discipline, 202 Holy, 203 Shadow · 398 Blood, 399 Frost, 400 Unholy · 261 Elemental, 263 Enhancement, 262 Restoration · 81 Arcane, 41 Fire, 61 Frost · 302 Affliction, 303 Demonology, 301 Destruction · 283 Balance, 281 Feral Combat, 282 Restoration. (Note the v2 §2 "Warrior 161/163/164" ordering — 163=Protection, 164=Fury; ids match, names confirmed.)
### 7.2 Archetype enum / pool indexing — **VERIFIED**: 4-value enum (no AGILITY), `ArchetypeFromString` maps only CASTER/HEALER/TANK (default PHYSICAL); `ARMOR_POOLS[4]`/`JEWELRY_POOLS[4]`/`RELIC_POOLS[4]` indexed by `uint32(archetype)`; `WEAPON_POOLS[3]` indexed by weapon pool. Extension plan in §4.2.
### 7.3 `Player::GetSpec`/`GetActiveSpec`/`GetShapeshiftForm` — **VERIFIED** signatures in §1.
### 7.4 `GenerateEnchSuffixFactor` + suffix re-apply path — **VERIFIED** (Item.cpp:668-720; one-arg `SetItemRandomProperties`; factor from variant's copied ItemLevel → unchanged by rank swap).
### 7.5 DBC availability for the generator — **VERIFIED**: `ItemRandomProperties.dbc` (2012 recs, max 2164), `ItemRandomSuffix.dbc` (95 recs, max 99), `SpellItemEnchantment.dbc` (2656 recs) all at `env/dist/bin/dbc/`; also `TalentTab.dbc` (33 recs).
### 7.6 Doc line numbers vs live tree — **RE-VERIFIED this session**: all anchors in §1/§2/§4/§5 are live-tree line numbers. The v2 spec's `Item.cpp:668` / `Item.h:178-181` / `Item.cpp:708` claims hold. Where docs drift (e.g. spec §4.2 says `SetItemRandomProperties(sign * to_id)` with a Player arg — this fork's signature is one-arg), the plan implements the verified fork API and flags it (see §5.2).

---

## 8. Out of scope (do NOT do)
Extended suffix DBC tiers (follow-up; capped-family report is the handoff) · client-side spec display · balance tuning · ANY `src/server/game/` change · `client-resources/generate_*.py` DBC-patch generators · MPQ packing · applying SQL to live DBs · running/compiling the server · any git operation.

---

## 9. Done criteria (reviewer gate)
1. `NexusFrames.lua`: minimap button (32×32, Minimap-parented, ring look, clamped, movable, drag-persisted `NexusFramesDB.minimapPos` guarded restore, `ToggleWindow()` click, "NexusFrames" tooltip); both `%%` sites fixed; popup backdrop borderless; transport/compact bar/reward list/scroll untouched (diff review).
2. `fury.cpp`: `PrimaryStatForSpec(Player*)` with the verified spec matrix + class fallback; both call sites updated; no other `PrimaryStatForClass` references.
3. `random_enchants.cpp/.h`: `ARCH_AGILITY` added (index 4); `ArchetypeFromString` handles "AGILITY"; 5-slot ARMOR/JEWELRY/RELIC pools + ARMOR_TANK includes AGI; `getArchetype` = spec table → class table → hard-coded, with feral-bear→TANK form check; `swapToVariant` no longer destroys suffixes/enchants; matrix roll skipped for random-property items; suffix rank boost via `mod_re_suffix_boost` + capped-family LOG, never errors, never touches ilvl/RequiredLevel.
4. New SQL: `004_mod_re_spec_archetype.sql` (30 seeded rows), `005_mod_re_suffix_boost.sql` (DDL, no hand-written seed).
5. New tool `generate_suffix_boost.py` (reads the three DBCs from `env/dist/bin/dbc/` or overrides, emits ladder SQL + `suffix_boost_capped_families.txt`); conf.dist gains the two v2 keys.
6. `generate_variants.py` has `TIER_PRICE_MULT` {1.5,2.5,4,6,8}; `003_mod_re_variants.sql` regenerated via `--all` with scaled prices (same row count); build report tells the engineer to re-apply 003 + clear `Cache\WDB`.
7. Coherent C++17 / Python3 / Lua 5.1; no core changes; no git ops; nothing compiled/built/packed/applied. Reviewer confirms the diff matches this plan + the v2 design.
