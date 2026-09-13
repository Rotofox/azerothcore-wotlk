# Design Spec — Item Quality + Scaled Random-Enchant System

AzerothCore WotLK (Playerbot fork) — module `modules/mod-random-enchants`
> **STATUS: implemented — built and shipped.** This spec is retained as the design record. For
> current state see `documentation/modules.md` and `documentation/data-layer.md`.

Status: **implemented**. Every decision below is final and carried verbatim from the engineer. Do not re-litigate; implement as specified. Open items (Section 5) each carry a recommended default — use it unless you have a strong reason and document the deviation in the code.

---

## 1. System overview

### 1.1 What the system does

On every awarded item (loot drop, profession/craft create, quest reward, group-roll reward) the module performs two independent rolls:

1. **Quality roll → visible variant swap (or STAY).** A rates-driven roll picks a quality tier or a STAY outcome. On a tier, the awarded item is **swapped** to a real `item_template` variant row of that tier (scaled stats, own quality color/name/item level). On STAY, the item keeps its base quality (no swap) — the enchant roll still runs on the base item. Loot tables are **never** modified — the swap happens in the module at award time.
2. **Scaled random enchants.** The existing chained per-slot enchant roll (70 % → 65 % → 60 %) is retained but re-sourced: enchant ids now come from a custom, ilvl-scaled `spellitemenchantment_dbc` mirror matrix, and the enchant slots move from `{0, 1, 5}` to the PROP slots `{7, 8, 9}` so random enchants never collide with the TEMP slot used by rogue poisons / shaman weapon buffs (a latent bug in the current module).

The two systems compose: when the quality roll upgrades, swap first (variant is a real row with its own scaled stats); when it STAYs, the enchant roll runs on the base item. Enchant magnitude has **no total cap**.

### 1.2 Scope

In scope:

- Modify `modules/mod-random-enchants` in place (never commit / push / pull).
- All data changes: rates tables, pool tables, enchant matrix rows, variant `item_template` rows (delivered as generated SQL files inside the module).
- Documenting the client DBC patch requirement.

Out of scope (do not do):

- Implementing the module (this is the design spec; the builder implements).
- Changing anything in core `src/server/game/`.
- Loot-table surgery (variants are delivered by the module's item swap; `creature_loot_template` / `reference_loot_template` stay untouched).
- Creating the client DBC patch (was out of scope for the original design; it has since been **built** — see `client-resources/README.md`).
- Committing or pushing anything.

### 1.3 Quality tiers

Five roll tiers. T4 and T5 are both _Legendary_ visible quality; T5 is the top-end legendary roll (highest enchant multiplier). T5 stays rare everywhere (Section 4.3).

| Roll tier | Variant quality      | Quality enum | Color  | Enchant multiplier | Name prefix (12a default) |
| --------- | -------------------- | ------------ | ------ | ------------------ | ------------------------- |
| T1        | Uncommon             | 2            | Green  | ×1.0               | Superior                  |
| T2        | Rare                 | 3            | Blue   | ×1.15              | Exquisite                 |
| T3        | Epic                 | 4            | Purple | ×1.35              | Regal                     |
| T4        | Legendary            | 5            | Orange | ×1.6               | Legendary                 |
| T5        | Legendary (top roll) | 5            | Orange | ×1.9               | Mythic                    |

### 1.4 Eligible items

| Base quality       | Quality enum | Quality roll? | Variants available                                          | Enchant roll?                      |
| ------------------ | ------------ | ------------- | ----------------------------------------------------------- | ---------------------------------- |
| Poor (grey)        | 0            | No            | —                                                           | No (unchanged from current module) |
| Common (white)     | 1            | Yes           | STAY or T1–T5 (uncommon/rare/epic/legendary/legendary)      | Yes                                |
| Uncommon (green)   | 2            | Yes           | STAY or T2–T5 (rare/epic/legendary/legendary)               | Yes                                |
| Rare (blue)        | 3            | Yes           | STAY or T3–T5 (epic/legendary/legendary)                    | Yes                                |
| Epic (purple)      | 4            | Yes           | STAY or T4–T5 (legendary/legendary)                         | Yes                                |
| Legendary (orange) | 5            | No (legendary items get no variants) | —                                    | Yes (unchanged)                    |
| Artifact           | 6            | No (excluded) | —                                                           | No (unchanged)                     |
| Heirloom           | 7            | No (excluded) | —                                                           | No (unchanged)                     |

Item-class filter (kept from the current module): only `ITEM_CLASS_WEAPON (2)` and `ITEM_CLASS_ARMOR (4)`. This already covers jewelry (class 4, subclass 0) and relics (class 4, inventory type 28).

**No backward variants**: an item only gets variants of _higher_ quality. Common → uncommon/rare/epic/legendary; uncommon → rare/epic/legendary; rare → epic/legendary; epic → legendary only.

**STAY outcome**: every eligible base quality (1–4) also has an explicit STAY outcome — a STAY roll leaves the item at its base quality (no variant swap); the enchant roll still runs on the base item. Rate rows are keyed by (ilvl band, base quality) and carry a STAY weight plus weights for the tiers available above that base; there is **no cross-base normalization** (Section 4.3). Legendary bases (quality 5) get **no variants** and roll enchants only (unchanged from the current module).

### 1.5 Award flow (the four award events)

The four award events all funnel through the module's existing PlayerScript hooks. The hooks carry the `Player`, so per-player decisions (stat pools) are possible.

```
Award event fires
  └─ OnPlayerLootItem(player, item, count, lootguid)          — loot pickup (post-pickup; item already in inventory)
  └─ OnPlayerCreateItem(player, item, count)                  — profession / create-spell item
  └─ OnPlayerQuestRewardItem(player, item, count)             — quest reward item
  └─ OnPlayerGroupRollRewardItem(player, item, count, vote, roll) — group-roll reward
        │
        ▼
rollQualityAndEnchant(player, item)
  1. Guards (Section 2.3): module enabled, event enabled, item valid/in-world,
     class 2|4, base quality 1–4 for the quality roll, item is NOT already a variant.
  2. Capture BASE template: baseEntry, baseIlvl, baseQuality, baseClass,
     baseInventoryType, baseSubClass. (Must be captured BEFORE the swap.)
  3. Quality roll:
       band = f(baseIlvl)  (Section 4.2)
       row  = mod_re_rates[band, baseQuality]   — per-base-quality row (Section 4.3)
       outcome = weighted pick over { STAY } ∪ availableTiers
                 (availableTiers = tiers with weight > 0 in the row; no-backward rule)
       STAY  ⇒ no variant swap; continue at step 6 (enchant roll runs on the BASE item)
       tier  ⇒ steps 4–5 (variant swap)
  4. Variant lookup: mod_re_item_variants[baseEntry, tier] → variantEntry
  5. Swap: item->SetEntry(variantEntry); item->SetState(ITEM_CHANGED, player)
       (post-pickup swap ⇒ loot window showed the base name — accepted v1 nuance, 12b)
  6. Enchant roll (Section 2.5), using the BASE ilvl for band selection — runs on the
     base item when the quality roll STAYed, on the variant otherwise:
       slot 1: 70 % → pick enchant; if hit, slot 2: 65 % → pick; if hit, slot 3: 60 % → pick
       pool selection (Section 4.4) from the LOOTING player's class/archetype
       stat pick (weighted) → matrix row (band, stat, tier, rung) → enchant id
       SetEnchantment on PROP slots 7/8/9; ApplyEnchantment around it
  7. Chat message (existing behavior): “Newly Acquired <name> has received N random enchantments!”
```

Quality roll and enchant roll both use the **base** ilvl (captured pre-swap), so a variant does not re-bucket its own enchant band. The enchant roll is independent of the quality roll: it runs for every eligible item, STAY or upgraded.

---

## 2. Module architecture

### 2.1 Files in `modules/mod-random-enchants/`

Existing (kept, modified):

- `src/random_enchants.h` — reworked (new enums, new function decls, hook declarations unchanged).
- `src/random_enchants.cpp` — reworked (roll flow, quality system, matrix lookup, slot move).
- `src/RE_loader.cpp` — unchanged.
- `conf/random_enchants.conf.dist` — extended with new options (Section 4.8).
- `data/sql/db-world/item_enchatment_random_tiers.sql` — **kept untouched** (legacy enchant pool “stays alongside”). New code no longer queries it by default (`RandomEnchants.UseLegacyEnchantPool = 0`); the flag restores legacy behavior for rollback.

New:

- `data/sql/db-world/001_mod_re_rates.sql` — quality rates (`mod_re_rates`) + pool rates (`mod_re_pool_rates`) + class→archetype tables + seed rows (hand-written).
- `data/sql/db-world/002_mod_re_enchant_matrix.sql` — enchant matrix rows in `spellitemenchantment_dbc` (generated).
- `data/sql/db-world/003_mod_re_variants.sql` — variant `item_template` rows + variant mapping table (generated).
- `tools/generate_enchant_matrix.py` — matrix generator (Python 3, stdlib only; reads band/stat/tier/rung config, emits `002_…sql`).
- `tools/generate_variants.py` — variant generator (Python 3, stdlib only; reads a base `item_template` export, emits `003_…sql`).
- `README.md` — short note: what changed, how to regenerate SQL, client DBC patch requirement.

### 2.2 PlayerScript hooks (reused, unchanged signatures)

From `src/server/game/Scripting/ScriptDefines/PlayerScript.h` — all four already registered by `RandomEnchantsPlayer`:

| Hook                          | Signature (this fork)                                 | Fires at                                                                |
| ----------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------- |
| `OnPlayerLootItem`            | `(Player*, Item*, uint32 count, ObjectGuid lootguid)` | Player.cpp:13644, after item is created and `SendNewItem` — post-pickup |
| `OnPlayerCreateItem`          | `(Player*, Item*, uint32 count)`                      | SpellEffects.cpp:1768, profession/create spells                         |
| `OnPlayerQuestRewardItem`     | `(Player*, Item*, uint32 count)`                      | PlayerQuest.cpp:702/723                                                 |
| `OnPlayerGroupRollRewardItem` | `(Player*, Item*, uint32 count, RollVote, Roll*)`     | Group.cpp:1485/1555                                                     |

The hook set is **not** changed; only the body of the roll function is reworked. `OnPlayerLogin` stays as-is (announcement).

### 2.3 Exact changes in `src/random_enchants.h`

- Keep `enum ItemQuality { GREY=0 … ORANGE=5 }` (or replace with core `ItemQualities`; either is fine — do not change behavior).
- Add:
  - `enum QualityTier : uint8 { TIER_1 = 1, TIER_2, TIER_3, TIER_4, TIER_5 };`
  - `enum Archetype : uint8 { ARCH_CASTER, ARCH_HEALER, ARCH_PHYSICAL, ARCH_TANK };`
  - `enum WeaponPool : uint8 { WEAPON_POOL_CASTER, WEAPON_POOL_MELEE, WEAPON_POOL_HUNTER };`
  - `struct EnchantRollResult { uint32 enchantId; uint8 slot; };`
- Declare the new free functions:
  - `bool rollQualityAndEnchant(Player* player, Item* item);` — replaces `rollPossibleEnchant` as the entry point called by the four hooks.
  - `uint8 getIlvlBand(uint32 itemLevel);` — 1..7 per Section 4.2.
  - `std::optional<QualityTier> rollQualityTier(Player* player, const ItemTemplate* baseTemplate);` — weighted roll over `{ STAY } ∪ availableTiers` from the (ilvl band, base quality) rates row; returns `std::nullopt` for STAY (no variant swap), otherwise the rolled tier 1..5. No normalization.
  - `uint32 getVariantEntry(uint32 baseEntry, QualityTier tier);` — query `mod_re_item_variants`.
  - `void swapToVariant(Player* player, Item* item, uint32 variantEntry);`
  - `Archetype getArchetype(Player* player);` — class→archetype table lookup (Section 4.5).
  - `std::vector<std::pair<uint32,float>> getStatPool(Item* item, Archetype archetype);` — armor / weapon / jewelry / relic pool (Section 4.4).
  - `uint32 getMatrixEnchantId(uint8 band, uint32 statType, QualityTier tier, uint8 rung);` — deterministic ID from the matrix formula (Section 3.4).
  - `bool rollOneEnchant(Player* player, Item* item, EnchantmentSlot slot);` — single chained roll; returns true if applied.
  - Keep `getRandEnchantment` only for the legacy-pool fallback path.
- `random_enchants.h` gains `#include <optional>` (C++17) for the STAY return value.

### 2.4 Exact changes in `src/random_enchants.cpp`

- `rollPossibleEnchant` is **replaced** by `rollQualityAndEnchant` implementing Section 1.5 exactly:
    1. Guards (all config-gated):
        - `RandomEnchants.Enable` (existing), event flag `RandomEnchants.OnLoot/OnCreate/OnQuestReward/OnGroupRoll` (existing).
        - `item && item->IsInWorld()`.
        - `class == ITEM_CLASS_WEAPON (2) || class == ITEM_CLASS_ARMOR (4)`.
        - Quality roll only when `baseQuality ∈ {1,2,3,4}` (Section 1.4). Enchant roll only when `baseQuality ∈ {1,2,3,4,5}` (matches current module’s `NORMAL..LEGENDARY` guard).
        - Re-roll protection: `SELECT 1 FROM mod_re_item_variants WHERE variant_entry = <item entry>` — if the item is already a variant, **skip entirely** (it already carries its roll).
    2. Capture `const ItemTemplate* base = item->GetTemplate();` (baseEntry, ItemLevel, Quality, Class, SubClass, InventoryType) **before** any swap.
    3. Quality roll per Section 4.3 (skip if `RandomEnchants.QualitySystem.Enable = 0`): read the `mod_re_rates` row for `(band, baseQuality)` and weighted-pick over `{ STAY } ∪ availableTiers`. STAY ⇒ skip steps 4–5 (no swap; enchant roll runs on the base item). tier ⇒ steps 4–5.
    4. Variant lookup + swap:

        ```cpp
        item->SetEntry(variantEntry);            // Object::SetEntry → OBJECT_FIELD_ENTRY
        item->SetState(ITEM_CHANGED, player);    // persists to DB on next save
        ```

        The client re-queries the new entry (real row ⇒ cache hit with variant name/color/ilvl). Item-level fields baked at creation (durability, sockets, etc.) are equal to the variant’s because variants copy those columns from the base (Section 3.5).
    5. Enchant roll (runs on the swapped item when the quality roll upgraded, on the base item when it STAYed; band from **base** ilvl).
- `rollOneEnchant`:
    1. `band = getIlvlBand(baseItemLevel)`.
    2. `pool = getStatPool(item, archetype)` — armor/weapon/jewelry/relic per Section 4.4 (weights read from `mod_re_pool_rates`, Section 3.1).
    3. `statType` = weighted pick from pool.
    4. `rung = urand(0, Rungs-1)` (uniform).
    5. `enchantId = getMatrixEnchantId(band, statType, tier, rung)`.
    6. Validate `sSpellItemEnchantmentStore.LookupEntry(enchantId)`; then

        ```cpp
        player->ApplyEnchantment(item, slot, false);
        item->SetEnchantment(slot, enchantId, 0, 0);
        player->ApplyEnchantment(item, slot, true);
        ```

- **Slot move (decision 7)**: replace `uint32 slotEnch[3] = { 0, 1, 5 };` with the PROP slots:

    ```cpp
    uint32 slotEnch[3] = { PROP_ENCHANTMENT_SLOT_0, PROP_ENCHANTMENT_SLOT_1, PROP_ENCHANTMENT_SLOT_2 }; // 7, 8, 9
    ```

    Keep the chained logic exactly: `slot 1: 70 %`, `slot 2: 65 %` (only if slot 1 hit), `slot 3: 60 %` (only if slot 2 hit). No total cap.
- `getStatPool` (Section 4.4):
  - class 2 (weapon) → weapon pool from the **weapon’s own template stats**: any `Int` or `Spell Power` stat → `WEAPON_POOL_CASTER`; else any `Agi` → `WEAPON_POOL_HUNTER`; else any `Str` → `WEAPON_POOL_MELEE`; none → `WEAPON_POOL_MELEE` (default).
  - inventory type ∈ {NECK(2), FINGER(11), TRINKET(12)} → JEWELRY pool of the looting player’s archetype.
  - inventory type == RELIC(28) → RELIC pool (class primary only).
  - otherwise (armor incl. shields) → armor pool of the looting player’s archetype.
- `getArchetype`: query `mod_re_class_archetype` for the player’s class; fall back to the hard-coded default map (Section 4.5) if no row.
- Rates are read **per roll** (recommended default 12c): each quality roll issues one weighted query against `mod_re_rates` (single row keyed by `(band, base_quality)`); each pool selection one weighted query against `mod_re_pool_rates`. No caching in v1.
- Chat message: unchanged text, but the name now resolves from the variant template (item was already swapped when it upgraded; on STAY it resolves from the base template).

### 2.5 Core facts the implementation must respect (verified in this fork)

- **Enchant slots 7–11 are safe and client-visible.** `UpdateFields.h` defines `ITEM_FIELD_ENCHANTMENT_1_1 … _12_3`; `EnchantmentSlot` in `Item.h` maps `PROP_ENCHANTMENT_SLOT_0..4 = 7..11` (used by RandomSuffix/RandomProperty). `Player::ApplyEnchantment(item, slot, apply)` accepts any slot `< MAX_ENCHANTMENT_SLOT (12)` (PlayerStorage.cpp:4293 loops 0..11; `ApplyEnchantment(item, bool)` at 4272 too). Stats from enchant rows are applied on equip via `_ApplyItemMods` over all slots.
- **PROP slots are free for our items.** `Item::GenerateItemRandomPropertyId` returns 0 when template `RandomProperty == 0 && RandomSuffix == 0`; `Item::CreateItem` then never writes slots 7–11. Variants keep `RandomProperty = 0`, `RandomSuffix = 0` (copied), so nothing fights us over the slots.
- **The server only reads `EffectPointsMin`.** The `SpellItemEnchantmentfmt` = `"niiiiiiixxxiiissssssssssssssssxiiiiiii"`; the `x` tokens skip `EffectPointsMax_1..3` and `Name_Lang_Mask`. `SpellItemEnchantmentEntry` has no max field (DBCStructure.h:1877). `DBCDatabaseLoader` walks the fmt and consumes one DB column per token, so `amount[] = EffectPointsMin[]` is the applied value; `EffectPointsMax_*` exist in the DB mirror only for the client DBC patch tooltip. **Consequence: “each roll draws rand(min, max)” is realized by a pre-rolled magnitude ladder in the matrix (Section 3.4), not by the core reading max.**
- **Enchant effect types** (DBCEnums.h): `ITEM_ENCHANTMENT_TYPE_STAT = 5` (EffectArg = `ITEM_MOD_*` stat, amount = value), `ITEM_ENCHANTMENT_TYPE_DAMAGE = 2`, `ITEM_ENCHANTMENT_TYPE_RESISTANCE = 4`. Matrix rows use STAT with `Effect_2/3 = 0`.
- **All pool stats are supported** by `Player::ApplyEnchantment`’s STAT switch (PlayerStorage.cpp:4411+): MANA, HEALTH, AGILITY(3), STRENGTH(4), INTELLECT(5), SPIRIT(6), STAMINA(7), DEFENSE_SKILL_RATING(12), DODGE_RATING(13), PARRY_RATING(14), HIT_RATING(31), CRIT_RATING(32), HASTE_RATING(36), EXPERTISE_RATING(37), ATTACK_POWER(38), MANA_REGENERATION(43) → `ApplyManaRegenBonus`, SPELL_POWER(45) → `ApplySpellPowerBonus`.
- **DBC loading** (DBCStores.cpp `LoadDBC`): file rows load first, then `LoadFromDB(mirror)`. DB rows with an ID already in the file **override** the file row; new IDs are appended. Because `spellitemenchantment_dbc` / `itemrandomproperties_dbc` / `itemrandomsuffix_dbc` / `randproppoints_dbc` mirrors are **empty in this dump**, the server’s live source is the `.dbc` files under the data path — and the server cannot boot without one source or the other. Custom rows must use an ID range above all file IDs (Section 3.4) so nothing is overridden.

---

## 3. Data changes

### 3.0 Runtime DBC source verification (do this FIRST, before any DBC data is populated)

Decision 11 requires proving which source the server actually loads before we populate `spellitemenchantment_dbc`.

1. Check the DB mirrors in the live world DB:

    ```sql
    SELECT 'spellitemenchantment_dbc' t, COUNT(*) FROM spellitemenchantment_dbc
    UNION ALL SELECT 'itemrandomproperties_dbc', COUNT(*) FROM itemrandomproperties_dbc
    UNION ALL SELECT 'itemrandomsuffix_dbc', COUNT(*) FROM itemrandomsuffix_dbc
    UNION ALL SELECT 'randproppoints_dbc', COUNT(*) FROM randproppoints_dbc;
    ```

    In this dump all four are **0 rows** (schemas only).
2. Confirm the `.dbc` files exist under the server data path (`DataDir` in `worldserver.conf`, path `<DataDir>/dbc/`):
   `SpellItemEnchantment.dbc`, `ItemRandomProperties.dbc`, `ItemRandomSuffix.dbc`, `RandPropPoints.dbc`.
3. **Reasoning to record**: if the mirrors are empty and the server boots, the `.dbc` files are the live source (the loader errors out if neither source yields rows). Our matrix rows are then **appended** from the DB mirror — safe as long as IDs do not collide with file IDs.
4. Record the max enchant ID in the live store before choosing the matrix base: inspect the `.dbc` file (e.g., `strings SpellItemEnchantment.dbc | grep` won’t give IDs — use a small Python struct parse or the module’s startup log) and/or add a temporary startup `LOG_INFO` in the module printing `sSpellItemEnchantmentStore.GetNumRows()` and the max ID. Vanilla 3.3.5 has < 5000 enchant rows; matrix base 100000 (Section 3.4) is far above. **Gate: proceed with matrix population only after this check confirms base 100000 > max live ID.**
5. After matrix SQL is applied: restart (or `.reload` if available) and verify `SELECT COUNT(*) FROM spellitemenchantment_dbc;` == 2625 and that `sSpellItemEnchantmentStore.LookupEntry(100000)` is non-null (log line or a test roll).

### 3.1 Rates tables — `mod_re_rates` (quality) + `mod_re_pool_rates` (stat pools) (new, hand-written SQL)

Both tunable via `SQL UPDATE` + reload (read-per-roll, no rebuild).

**`mod_re_rates` — quality tier weights, keyed by (ilvl band, base quality).** 4 base qualities × 7 ilvl bands = 28 rows. Each row carries a **STAY** weight plus weights for the tiers available ABOVE that base (no-backward rule); tiers not available above a base are 0 and ignored. Weights are relative within the row (the roll weighted-picks over STAY + available tiers); there is **no cross-base normalization**.

```sql
CREATE TABLE IF NOT EXISTS `mod_re_rates` (
  `band`         tinyint unsigned NOT NULL,   -- 1..7 (Section 4.2)
  `base_quality` tinyint unsigned NOT NULL,   -- 1..4 (common..epic; legendary bases never roll, Section 1.4)
  `stay`         float NOT NULL DEFAULT '0',  -- STAY weight (no variant swap; enchant roll still runs)
  `tier1`        float NOT NULL DEFAULT '0',  -- 0 unless base_quality = 1 (no-backward rule)
  `tier2`        float NOT NULL DEFAULT '0',  -- 0 unless base_quality <= 2
  `tier3`        float NOT NULL DEFAULT '0',  -- 0 unless base_quality <= 3
  `tier4`        float NOT NULL DEFAULT '0',  -- 0 unless base_quality <= 4
  `tier5`        float NOT NULL DEFAULT '0',  -- 0 unless base_quality <= 4
  PRIMARY KEY (`band`, `base_quality`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Seed rows: the starting table in Section 4.3 (28 rows, all weights relative).

**`mod_re_pool_rates` — stat pool weights.** Separated from the quality table by the ratified table-shape change; keys and values are exactly the pool design already specified in Section 4.4 (unchanged).

```sql
CREATE TABLE IF NOT EXISTS `mod_re_pool_rates` (
  `rate_key`   varchar(64)  NOT NULL,
  `rate_value` float        NOT NULL DEFAULT '0',
  PRIMARY KEY (`rate_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Key namespace (all values are **relative weights**; Section 4.4 carries the tables):

- Armor pool weights: `pool_weight:<ARCHETYPE>:<STAT>` (Section 4.4.1).
- Weapon pool weights: `weapon_pool_weight:<WEAPONPOOL>:<STAT>` (Section 4.4.2).
- Jewelry weights: `jewelry_weight:<ARCHETYPE>:<STAT>` — exactly three stats per archetype with weights 50/30/20 (Section 4.4.3).
- Relic weights: `relic_weight:<ARCHETYPE>:<STAT>` — one stat, weight 100 (Section 4.4.4).

STAT tokens: `INT, SPI, STA, STR, AGI, SP, AP, MP5, CRIT, HASTE, HIT, EXP, DEF, DODGE, PARRY`.

### 3.2 Class → archetype table — `mod_re_class_archetype` (new, hand-written SQL)

```sql
CREATE TABLE IF NOT EXISTS `mod_re_class_archetype` (
  `class_id`  tinyint unsigned NOT NULL,
  `archetype` varchar(16) NOT NULL,   -- CASTER | HEALER | PHYSICAL | TANK
  `note`      varchar(64) DEFAULT NULL,
  PRIMARY KEY (`class_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Seed rows: the fixed v1 map in Section 4.5 (one row per class). Per-class overrides (ret/feral/protection/tank specs) are **config/table-level v2 refinements**; v1 is spec-blind (Section 4.5).

### 3.3 Variant mapping table — `mod_re_item_variants` (new, generated)

```sql
CREATE TABLE IF NOT EXISTS `mod_re_item_variants` (
  `base_entry`     int unsigned NOT NULL,
  `tier`           tinyint unsigned NOT NULL,   -- 1..5
  `variant_entry`  int unsigned NOT NULL,
  PRIMARY KEY (`base_entry`, `tier`),
  KEY `idx_variant_entry` (`variant_entry`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Generated alongside the variant rows. The `idx_variant_entry` index serves the re-roll protection query (Section 2.4).

### 3.4 Enchant matrix — rows in `spellitemenchantment_dbc` (generated)

Schema (from `data/sql/base/db_world/spellitemenchantment_dbc.sql`): `ID, Charges, Effect_1..3, EffectPointsMin_1..3, EffectPointsMax_1..3, EffectArg_1..3, Name_Lang_enUS…Unk, Name_Lang_Mask, ItemVisual, Flags, Src_ItemID, Condition_Id, RequiredSkillID, RequiredSkillRank, MinLevel`.

**Dimensions**: `band (7) × stat (15) × tier (5) × rung (5) = 2625 rows`. This is the “ilvl-band × stat × magnitude” matrix; the tier and rung dimensions exist because the server applies the row’s fixed `EffectPointsMin` (Section 2.5) — so every discrete magnitude the roll can produce must be its own row.

**ID allocation**: `ID = MatrixIdBase + (band-1)*375 + statIndex*25 + (tier-1)*5 + rung`

- `MatrixIdBase = 100000` (config `RandomEnchants.EnchantMatrixIdBase`; gate on Section 3.0 step 4).
- statIndex: fixed order of the 15 stats: `INT(0) SPI(1) STA(2) STR(3) AGI(4) SP(5) AP(6) MP5(7) CRIT(8) HASTE(9) HIT(10) EXP(11) DEF(12) DODGE(13) PARRY(14)`.
- ID range used: 100000..102624. (Reserve 100000..109999 for future 3-effect rows.)

**Row contents** (single-effect STAT enchants):

- `Charges = 0`
- `Effect_1 = 5` (`ITEM_ENCHANTMENT_TYPE_STAT`), `Effect_2 = 0`, `Effect_3 = 0`
- `EffectPointsMin_1 = EffectPointsMax_1 = round(rungValue × tierMultiplier)` where `rungValue = min + (max − min) × rung / (Rungs − 1)` and `min/max` come from the band table (Section 4.2) and tierMultiplier from Section 4.1.
- `EffectPointsMin_2/3 = EffectPointsMax_2/3 = 0`
- `EffectArg_1 = ITEM_MOD_*` of the stat (Section 2.5 list), `EffectArg_2/3 = 0`
- `Name_Lang_enUS = <stat display name>` (e.g. `Scaled Intellect`, `Scaled Spell Power`, `Scaled Mana/5`); copy to the other `Name_Lang_*` columns or leave NULL (client falls back to enUS). All rows of a stat share the name — the per-row value shown in the tooltip comes from the row’s own effect amounts, which the client DBC patch will carry.
- `ItemVisual = 0`, `Flags = 0`, `Src_ItemID = 0`, `Condition_Id = 0`, `RequiredSkillID = 0`, `RequiredSkillRank = 0`, `MinLevel = 0`, `Name_Lang_Mask = 0`.

**Rung ladder (recommended default)**: `Rungs = 5` (config `RandomEnchants.EnchantMatrixRungs`). Rung values for band 1-20 (10..30): 10, 15, 20, 25, 30; for band 241-277 (400..600): 400, 450, 500, 550, 600. A uniform rung pick approximates `urand(min, max)` at resolution `(max−min)/4`.

**Tier multiplier application**: amount = `round(rungValue × tierMultiplier)` per Section 4.1. Example: band 1-20 (10..30), rung 2 (20), T3 (×1.35) → `round(27) = 27`.

**Generator** (`tools/generate_enchant_matrix.py`): pure Python; inputs = band table, stat list with `ITEM_MOD_*` values, tier multipliers, Rungs, MatrixIdBase; emits `002_mod_re_enchant_matrix.sql` with `REPLACE INTO spellitemenchantment_dbc (...) VALUES ...` (idempotent). No DB access required.

### 3.5 Variant rows — `item_template` (generated)

**Entry range**: `VariantEntryBase = 1000000` (config `RandomEnchants.VariantEntryBase`). This dump’s base `item_template` max entry is 56806 (46 096 rows) — 1 000 000 gives ample headroom for the full-scale estimate of ~50 000–78 000 variant rows (→ up to ~1 078 000). The generator must assert `max(entry) < VariantEntryBase` against the live DB before generating.

**Generator** (`tools/generate_variants.py`): reads a base `item_template` export (full positional rows, 144-column monolithic table in this fork — copy every column verbatim), and for each eligible base item (Section 1.4) and each tier whose quality > base quality, emits:

1. `entry` = next allocated id (sequential from `VariantEntryBase`).
2. `name` = `<Prefix> <BaseName>` (prefix map Section 4.1; enUS; `item_template_locale` rows for variants are out of scope in v1 — note in README).
3. `Quality` = tier quality (2/3/4/5/5 for T1..T5).
4. `ItemLevel` = base ItemLevel (**unchanged** — recommended default; see 12f; keeps enchant band tied to base ilvl).
5. Scaled stats (decision 4 — ×1.75 compound per tier **above the base quality**):
    - multiplier `m = 1.75^(variantQuality − baseQuality)`:
      base common: T1 ×1.75, T2 ×3.06, T3 ×5.36, T4/T5 ×9.38
      base uncommon: T2 ×1.75, T3 ×3.06, T4/T5 ×5.36
      base rare: T3 ×1.75, T4/T5 ×3.06
      base epic: T4/T5 ×1.75
    - `armor = round(base.armor × m)`
    - `dmg_min1/dmg_max1/dmg_min2/dmg_max2 = round(base × m)` (each damage type)
    - every `stat_value_i` where `stat_type_i != 0`, `i = 1..StatsCount`: `round(stat_value_i × m)` (stat types unchanged; `StatsCount` unchanged).
6. All other columns copied verbatim from the base row (`RandomProperty = 0`, `RandomSuffix = 0` preserved — required for free PROP slots).
7. **Statless items** (decision 5): base has no stats (`StatsCount = 0` or all `stat_type = 0`), no damage (`dmg_min1 = 0`), no spells (`spellid_1..5 = 0` or `-1`) — e.g. armor-only items like Flax Vest. The variant template gets:
    - `StatsCount = 1`, `stat_type1 = <seed stat>`, `stat_value1 = round(seedValue × tierMultiplier)` where `seedValue = urand(bandMin, bandMax)` using the SAME ×10 band table (Section 4.2) — pinned top band 400–600 at ilvl 241–277 (reconciliation: the earlier “300–600 at ilvl 260+” sketch is superseded by the pinned table; min raised to 400 to keep the progression smooth).
    - `seed stat` from the **item-appropriate pool** (interpretation of “class-appropriate” for a static template row; the dynamic per-player class pools still drive the enchant rolls): cloth → CASTER pool, leather → PHYSICAL, mail → PHYSICAL, plate → TANK, shield → TANK, jewelry/relic → no template seed in v1 (these are rarely statless; the enchant roll still applies). Config `RandomEnchants.StatlessSeed.Enable = 1`.
    - seedValue drawn once per row **at generation time** (static row, fixed value).
8. Emit one `INSERT` batch into `003_mod_re_variants.sql` plus the mapping rows into `mod_re_item_variants` (Section 3.3). Re-running the generator is idempotent within the managed entry range (it only manages rows whose `entry ≥ VariantEntryBase`).

---

## 4. Tuning values (all tables)

### 4.1 Tier multipliers and prefixes

| Tier | Enchant multiplier | Variant stat multiplier (×1.75^tiers above base) | Name prefix |
| ---- | ------------------ | ------------------------------------------------ | ----------- |
| T1   | ×1.0               | ×1.75 (one tier above base)                      | Superior    |
| T2   | ×1.15              | ×3.06                                            | Exquisite   |
| T3   | ×1.35              | ×5.36                                            | Regal       |
| T4   | ×1.6               | ×9.38                                            | Legendary   |
| T5   | ×1.9               | ×9.38                                            | Mythic      |

Compound check: 1.75¹ = 1.75; 1.75² = 3.0625 → 3.06; 1.75³ = 5.3594 → 5.36; 1.75⁴ = 9.3789 → 9.38. The **variant** multiplier is relative to the base item’s quality (Section 3.5.5); the **enchant** multiplier is absolute per tier.

### 4.2 Enchant magnitude bands (×10, pinned)

| Band id | ilvl range | min | max |
| ------- | ---------- | --- | --- |
| 1       | 1–20       | 10  | 30  |
| 2       | 21–40      | 30  | 60  |
| 3       | 41–70      | 60  | 100 |
| 4       | 71–120     | 100 | 180 |
| 5       | 121–180    | 180 | 280 |
| 6       | 181–240    | 280 | 400 |
| 7       | 241–277    | 400 | 600 |

Reconciliation (decision 6): the earlier sketch “300–600 at ilvl 260+” is **superseded** by this table. The pinned top band is 400–600 for ilvl 241–277 (which covers 260+); the min was raised from 300 to 400 so the ×10 progression stays linear. These same bands seed statless-item template stats (Section 3.5.7). The same band table feeds the quality-rate table and the matrix generator.

### 4.3 Quality tier weights per (ilvl band, base quality) — starting table (exact numbers are TBD by tuning; these are the proposed start)

`mod_re_rates` is keyed by (ilvl band, base quality): one row per band × base quality = 4 × 7 = 28 rows. Each row carries a **STAY** weight plus weights for the tiers available ABOVE that base (no-backward rule); unavailable tiers are 0 and ignored. Weights are relative within the row — the roll weighted-picks over STAY + available tiers. No cross-base normalization.

| band        | base quality | STAY | T1  | T2  | T3  | T4  | T5  |
| ----------- | ------------ | ---- | --- | --- | --- | --- | --- |
| 1 (1–20)    | Common (1)   | 50   | 17  | 13  | 10  | 6   | 4   |
| 1 (1–20)    | Uncommon (2) | 55   | —   | 20  | 14  | 7   | 4   |
| 1 (1–20)    | Rare (3)     | 55   | —   | —   | 35  | 7   | 3   |
| 1 (1–20)    | Epic (4)     | 80   | —   | —   | —   | 13  | 7   |
| 2 (21–40)   | Common (1)   | 53   | 16  | 12  | 9   | 6   | 4   |
| 2 (21–40)   | Uncommon (2) | 55   | —   | 19  | 13  | 8   | 5   |
| 2 (21–40)   | Rare (3)     | 57   | —   | —   | 33  | 7   | 3   |
| 2 (21–40)   | Epic (4)     | 80   | —   | —   | —   | 13  | 7   |
| 3 (41–70)   | Common (1)   | 55   | 15  | 12  | 8   | 6   | 4   |
| 3 (41–70)   | Uncommon (2) | 58   | —   | 18  | 12  | 8   | 4   |
| 3 (41–70)   | Rare (3)     | 59   | —   | —   | 32  | 6   | 3   |
| 3 (41–70)   | Epic (4)     | 82   | —   | —   | —   | 12  | 6   |
| 4 (71–120)  | Common (1)   | 62   | 13  | 10  | 7   | 5   | 3   |
| 4 (71–120)  | Uncommon (2) | 64   | —   | 16  | 10  | 6   | 4   |
| 4 (71–120)  | Rare (3)     | 65   | —   | —   | 27  | 5   | 3   |
| 4 (71–120)  | Epic (4)     | 87   | —   | —   | —   | 9   | 4   |
| 5 (121–180) | Common (1)   | 65   | 12  | 9   | 6   | 5   | 3   |
| 5 (121–180) | Uncommon (2) | 66   | —   | 15  | 9   | 6   | 4   |
| 5 (121–180) | Rare (3)     | 67   | —   | —   | 26  | 5   | 2   |
| 5 (121–180) | Epic (4)     | 90   | —   | —   | —   | 7   | 3   |
| 6 (181–240) | Common (1)   | 73   | 10  | 7   | 5   | 3   | 2   |
| 6 (181–240) | Uncommon (2) | 74   | —   | 12  | 7   | 4   | 3   |
| 6 (181–240) | Rare (3)     | 75   | —   | —   | 19  | 4   | 2   |
| 6 (181–240) | Epic (4)     | 93   | —   | —   | —   | 5   | 2   |
| 7 (241–277) | Common (1)   | 75   | 10  | 6   | 4   | 3   | 2   |
| 7 (241–277) | Uncommon (2) | 76   | —   | 11  | 6   | 4   | 3   |
| 7 (241–277) | Rare (3)     | 77   | —   | —   | 18  | 3   | 2   |
| 7 (241–277) | Epic (4)     | 93   | —   | —   | —   | 5   | 2   |

Every row sums to 100, so the weights read directly as outcome percentages (relative weighting makes the exact sum irrelevant to the roll).

**Target check (decision 3 — STAY; applies to common/uncommon/rare bases):**

| ilvl range   | Common STAY % | Uncommon STAY % | Rare STAY % | Target        |
| ------------ | ------------- | --------------- | ----------- | ------------- |
| Low (1–70)   | 50–55         | 55–58           | 55–59       | ≈ 50–60 %     |
| Mid (71–180) | 62–65         | 64–66           | 65–67       | ≈ 60–70 %     |
| Endgame (181+) | 73–75       | 74–76           | 75–77       | ≈ 72–78 %     |

**Target check (decision 4 — legendary tail, T4 + T5 combined; generous):**

| ilvl range   | Common | Uncommon | Rare | Epic  | Blended target               |
| ------------ | ------ | -------- | ---- | ----- | ---------------------------- |
| Low (1–70)   | 10 %   | 11–13 %  | 9–10 % | 18–20 % | ≈ 1 in 10                  |
| Mid (71–180) | 8 %    | 10 %     | 7–8 % | 10–13 % | between                     |
| Endgame (181+) | 5 %  | 7 %      | 5–6 % | 7 %    | ≈ 1 in 20 (~5 %, “5 %+ (generous)”) |

⚑ **Epic-base STAY is deliberately high (decision 5).** For epic bases the only variants are legendary (T4/T5), so an epic that upgrades IS a legendary. The epic rows therefore carry STAY ≈ 93 % at endgame tapering to ≈ 80 % at low ilvl — this keeps the BLENDED legendary rate near the 1-in-20 target rather than every ~4th epic drop becoming legendary. Tune this number deliberately; it is the single biggest lever on the endgame legendary rate.

### 4.4 Stat pools (weights; decision 8, verbatim)

#### 4.4.1 Armor pools (keyed by the LOOTING player’s archetype)

| Archetype | Stat : weight                                                    |
| --------- | ---------------------------------------------------------------- |
| CASTER    | Int 35, Spell Power 30, Crit 15, Haste 12, Spirit 8              |
| HEALER    | Int 30, Spirit 25, MP5 20, Spell Power 15, Haste 10              |
| PHYSICAL  | Str/Agi 35, AP 20, Crit 15, Haste 12, Hit 10, Expertise 8        |
| TANK      | Stamina 40, Str 20, Defense 15, Dodge/Parry 10, Hit/Expertise 15 |

Resolved per class (config-tunable):

- PHYSICAL: Str for warrior / DK / ret-paladin / enhancement-shaman / feral-druid; **Agi** for rogue / hunter / kitty-druid.
- TANK plate (warrior/paladin/DK): Parry 10, Hit 8 + Expertise 7 (from “Hit/Expertise 15”).
- TANK bear (feral druid): Dodge 10, Hit 8 + Expertise 7.
  All resolved rows sum to 100.

#### 4.4.2 Weapon pools (chosen from the weapon’s own stat profile)

| Pool          | Stat : weight                                      | Trigger                                                                  |
| ------------- | -------------------------------------------------- | ------------------------------------------------------------------------ |
| WEAPON-caster | Int 40, SP 30, Haste 15, Crit 15                   | template has Int or Spell Power                                          |
| WEAPON-melee  | Str/Agi 40, AP 25, Crit 15, Haste 10, Expertise 10 | template has Str (Agi for agi-melee weapons; Str/Agi resolved per class) |
| WEAPON-hunter | Agi 40, AP 30, Crit 15, Hit 15                     | template has Agi                                                         |

Selection order: Int/SP → caster; else Agi → hunter; else Str → melee; else → melee (default).

#### 4.4.3 JEWELRY pool (class primary 50 / secondary 30 / utility 20)

| Archetype | Primary (50) | Secondary (30) | Utility (20) |
| --------- | ------------ | -------------- | ------------ |
| CASTER    | Int          | Crit           | Haste        |
| HEALER    | Int          | Spirit         | MP5          |
| PHYSICAL  | Str/Agi      | AP             | Crit         |
| TANK      | Stamina      | Defense        | Dodge        |

#### 4.4.4 RELIC pool (class primary only)

| Archetype | Stat (100) |
| --------- | ---------- |
| CASTER    | Int        |
| HEALER    | Int        |
| PHYSICAL  | Str/Agi    |
| TANK      | Stamina    |

### 4.5 Class → archetype mapping (fixed v1 default; config/table-tunable; spec-aware talent-tree selection is a v2 refinement)

| Class            | Default archetype | Config overrides (v2 spec-aware)          |
| ---------------- | ----------------- | ----------------------------------------- |
| Warrior (1)      | PHYSICAL          | PROTECTION → TANK                         |
| Paladin (2)      | HEALER            | RETRIBUTION → PHYSICAL; PROTECTION → TANK |
| Hunter (3)       | PHYSICAL          | —                                         |
| Rogue (4)        | PHYSICAL          | —                                         |
| Priest (5)       | HEALER            | —                                         |
| Death Knight (6) | PHYSICAL          | TANK (blood/frost) → TANK                 |
| Shaman (7)       | HEALER            | ENHANCEMENT → PHYSICAL                    |
| Mage (8)         | CASTER            | —                                         |
| Warlock (9)      | CASTER            | —                                         |
| Druid (11)       | HEALER            | FERAL → PHYSICAL; BEAR → TANK             |

Hybrid classes default to the pool named above; per-class overrides live in `mod_re_class_archetype` / config.

### 4.6 Enchant chances (kept from current module)

`RandomEnchants.EnchantChance1 = 70.0`, `EnchantChance2 = 65.0`, `EnchantChance3 = 60.0`. Chained per-slot (slot 2 only if slot 1 hit; slot 3 only if slot 2 hit). No total cap on enchant contribution.

### 4.7 ID bases

| Item               | Base                                 | Config key                           |
| ------------------ | ------------------------------------ | ------------------------------------ |
| Enchant matrix IDs | 100000 (rows 100000–102624)          | `RandomEnchants.EnchantMatrixIdBase` |
| Variant entries    | 1000000 (≈50–78k rows at full scale) | `RandomEnchants.VariantEntryBase`    |

### 4.8 Config additions (`conf/random_enchants.conf.dist`)

```
# Quality System
RandomEnchants.QualitySystem.Enable = 1
RandomEnchants.QualityRatesTable = "mod_re_rates"
RandomEnchants.PoolRatesTable = "mod_re_pool_rates"
RandomEnchants.ClassArchetypeTable = "mod_re_class_archetype"
RandomEnchants.VariantMappingTable = "mod_re_item_variants"
RandomEnchants.VariantEntryBase = 1000000
RandomEnchants.EnchantMatrixIdBase = 100000
RandomEnchants.EnchantMatrixRungs = 5
RandomEnchants.StatlessSeed.Enable = 1
RandomEnchants.UseLegacyEnchantPool = 0
RandomEnchants.VariantPrefixes = "Superior,Exquisite,Regal,Legendary,Mythic"
```

Existing options unchanged: `Enable`, `AnnounceOnLogin`, `OnLoginMessage`, `OnLoot`, `OnCreate`, `OnQuestReward`, `OnGroupRoll`, `EnchantChance1/2/3`.

---

## 5. Open implementation items (recommended defaults)

| #   | Item                                                                             | Recommended default                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 12a | Variant name generation                                                          | **Prefix map** (`Superior/Exquisite/Regal/Legendary/Mythic` + base name), not “(Epic)” suffix. Prefixes configurable via `RandomEnchants.VariantPrefixes`.                                                                                                                                                                                                                                                                                                                                                                                  |
| 12b | Swap timing                                                                      | **Post-pickup** for v1 (hook `OnPlayerLootItem` fires after `SendNewItem`). Nuance: the loot window shows the base name because the swap happens after pickup; the bag/equip view shows the variant once the client refreshes (real variant row ⇒ cache query succeeds). A loot-roll-time swap (variant visible in the loot window) would require hooking the loot roll before item creation — no such hook exists in the four-event set; defer.                                                                                            |
| 12c | Rates-table reload                                                               | **Read-per-roll** for v1 (each quality roll issues one indexed query against `mod_re_rates` keyed by (band, base_quality); each pool pick one against `mod_re_pool_rates`; plus `mod_re_class_archetype` / `mod_re_item_variants`). Cache-with-`.reload` is a later optimization.                                                                                                                                                                                                                                                          |
| 12d | Client DBC patch for matrix enchant names                                        | **Built** — the patch exists at `client-resources/SpellItemEnchantment.dbc` (generator `generate_enchant_dbc_patch.py`), shipped in `patch-4.MPQ`. Process (for reference): custom enchant IDs ≥ 100000 have no name strings in the client’s `SpellItemEnchantment.dbc`, so tooltips show nothing until the client DBC is patched — extract the DBC from the client MPQs (e.g., `common-2.mpq` / `patch-*.mpq` via MPQEditor/CASCExplorer), append the 2625 rows (or a name-only compact set), repack as a custom patch MPQ (`patch-4.mpq` or similar), ship to players. Server-side behavior is unaffected — enchants apply and display amounts regardless. |
| 12e | Matrix realization of `rand(min, max)` (discovered core constraint, Section 2.5) | **Pre-rolled magnitude ladder**: 5 evenly-spaced rungs per (band × stat × tier), uniform rung pick = discrete `urand(min,max)`; the row’s `EffectPointsMin` is the applied amount (core ignores `EffectPointsMax`). Rungs configurable via `RandomEnchants.EnchantMatrixRungs`.                                                                                                                                                                                                                                                             |
| 12f | Variant ItemLevel                                                                | **Unchanged** (copied from base). Decision 4’s mutation list is “Quality + scaled stats (+ name)” only; keeping ilvl equal keeps the enchant band tied to the base item. Scaling ilvl per tier would re-bucket bands and is a later tuning lever.                                                                                                                                                                                                                                                                                           |
| 12g | Statless-seed tier scaling                                                       | **Apply the tier multiplier** to the seeded `stat_value` (`round(urand(bandMin,bandMax) × tierMult)`), consistent with decision 4 (“each stat value”) — higher variants are strictly stronger. Note: at T5 the top band can reach ~1140; acceptable for a fun server, tunable via bands/pool.                                                                                                                                                                                                                                               |

---

## 6. Build order

1. **DBC source verification (Section 3.0)** — confirm `.dbc` files are the live source and max live enchant ID < 100000. Gate for everything below.
2. **Hand-written SQL** — `001_mod_re_rates.sql` (quality rates `mod_re_rates` + pool rates `mod_re_pool_rates` + class→archetype seeds, Section 3.1/3.2) with the starting tables (4.3, 4.4, 4.5).
3. **Matrix generator** — `tools/generate_enchant_matrix.py` (Section 3.4) → `002_mod_re_enchant_matrix.sql` (2625 rows). Apply to the world DB.
4. **Variant generator** — `tools/generate_variants.py` (Section 3.5) → `003_mod_re_variants.sql` (variant rows + mapping). Apply to the world DB.
5. **C++ rework** — `random_enchants.h/.cpp` per Section 2.3/2.4 (quality roll incl. STAY, swap, pools, matrix lookup, PROP slots 7/8/9, re-roll protection, legacy flag).
6. **Config** — extend `random_enchants.conf.dist` (Section 4.8).
7. **Build & restart** — rebuild the module (module builds in place; `RE_loader.cpp` untouched), restart worldserver, confirm startup log and DBC store row counts.
8. **Runtime verification**:
    - Loot a low-level white item → observe variant swap (bag shows prefixed name/color), 1–3 enchants on PROP slots, no TEMP-slot collision (rogue poison / shaman imbue still works on the same weapon).
    - Craft / quest-reward / group-roll paths → same behavior.
    - STAY outcome: most drops keep their base item (no swap) and still receive enchants; endgame epic bases STAY ~93 % of the time; low-ilvl common bases STAY ~50 %.
    - No-backward rule: epic base → only legendary variant; legendary base → no swap (enchants only).
    - Statless item (Flax Vest-type) → variant has a seeded stat.
    - Tuning knobs: `UPDATE mod_re_rates …` (quality weights, incl. STAY) and `UPDATE mod_re_pool_rates …` (pool weights) — confirm the next roll reflects them (read-per-roll).
    - Client tooltip: enchant names empty until the DBC patch ships (expected, documented).

## 7. Non-goals checklist (do not do)

- No changes to core `src/server/game/` (hook signatures, DBC loader, item/enchant application all stay as-is).
- No `creature_loot_template` / `reference_loot_template` edits — variants come from the module swap only.
- Client DBC patch artifact: **built** (`client-resources/SpellItemEnchantment.dbc`, generator `generate_enchant_dbc_patch.py`); shipped in `patch-4.MPQ`.
- No commits/pushes/pulls from `modules/mod-random-enchants`.
- `item_enchatment_random_tiers.sql` (legacy pool) is retained, not deleted; only no longer queried by default.
