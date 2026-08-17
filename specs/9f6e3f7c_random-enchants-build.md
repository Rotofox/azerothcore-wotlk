# Build Plan — Item Quality + Scaled Random-Enchant System (`modules/mod-random-enchants`)

Authoritative design: `specs/db8e1683_item-quality-random-enchants.md` (status: **ready to build**).
This plan translates that spec into concrete work. **Do not re-design or re-litigate the spec.**
Where this plan states a value the spec already states, the spec wins; where this plan resolves an
implicit point, the resolution is marked **[RESOLVED]** and must be implemented as stated (with a
comment in code if you deviate, per spec §1 preamble).

---

## 0. Hard constraints (violating any of these fails the run)

1. **NO GIT OPERATIONS, PERIOD.** This run is `--no-commit`: never run `git add`, `git commit`,
   `git push`, `git pull`, `git checkout`, `git reset`, `git clean`, `git stash`, or anything that
   mutates repository state. Note there are **two** git repos: the repo root
   (`/home/nexus-user/azerothcore-wotlk`) and the module's own repo (`modules/mod-random-enchants/.git`).
   Do not run git in either. All work products stay in the working tree, uncommitted.
2. **No changes to core** `src/server/game/`, `src/server/shared/` — hook signatures, DBC loader,
   item/enchant application all stay as-is.
3. **No loot-table surgery** (`creature_loot_template` / `reference_loot_template` untouched).
4. **No client DBC patch artifact** — document the requirement only (spec §5 12d).
5. **No full worldserver build.** Verification of the C++ is a **targeted object compile** (Step 7).
6. **Do not touch** `data/sql/db-world/item_enchatment_random_tiers.sql` (legacy pool; retained).
7. **Do not touch** `src/RE_loader.cpp` (spec §2.1: unchanged).
8. **Do not touch** any existing file outside `modules/mod-random-enchants/` and this plan's copy
   under `specs/`. Read-only inputs may be read, never written.

---

## 1. Environment facts (verified this session — trust these)

- Repo root: `/home/nexus-user/azerothcore-wotlk`; module at `modules/mod-random-enchants/`
  (its own git repo, `.git/` inside; also its own `.github/`, `.editorconfig`, `.gitattributes`).
- `item_template` is a **139-column** monolithic table (spec says 144; actual count in this dump is
  139 — the generator must read the column list from the schema, not hardcode 144).
  `data/sql/base/db_world/item_template.sql` is a mysqldump with `INSERT INTO item_template VALUES`
  blocks; each row is one line starting with `(`; **46 096** row lines in the file, **36 351** parse
  cleanly with exactly 139 columns (the generator must parse robustly, log skipped/malformed rows,
  and assert the per-row column count). Max `entry` = **56806** (matches spec §3.5).
- `spellitemenchantment_dbc` schema (43 columns) at `data/sql/base/db_world/spellitemenchantment_dbc.sql`;
  its dump section contains **no data rows** (schema only) — same for `itemrandomproperties_dbc`,
  `itemrandomsuffix_dbc`, `randproppoints_dbc`.
- Core facts confirmed in this fork:
  - `EnchantmentSlot` (Item.h:170-183): `TEMP=1, SOCK=2..4, BONUS=5, PRISMATIC=6,
    PROP_ENCHANTMENT_SLOT_0..4 = 7..11, MAX_ENCHANTMENT_SLOT = 12`.
  - `Object::SetEntry(uint32)` sets `OBJECT_FIELD_ENTRY`; `Item::SetState(ItemUpdateState, Player*)` exists.
  - `ItemQualities` (SharedDefines.h:338): `POOR=0, NORMAL=1, UNCOMMON=2, RARE=3, EPIC=4,
    LEGENDARY=5, ARTIFACT=6, HEIRLOOM=7`.
  - `ItemModType` (ItemTemplate.h:25): `MANA=0, HEALTH=1, AGILITY=3, STRENGTH=4, INTELLECT=5,
    SPIRIT=6, STAMINA=7, DEFENSE_SKILL_RATING=12, DODGE_RATING=13, PARRY_RATING=14,
    HIT_RATING=31, CRIT_RATING=32, HASTE_RATING=36, EXPERTISE_RATING=37, ATTACK_POWER=38,
    MANA_REGENERATION=43, SPELL_POWER=45`.
  - `DBCStorage<T>::LoadFromDB` (DBCStores.cpp `LoadDBC`, line 226+): file `.dbc` loads first,
    DB mirror rows then **override/append**; if neither yields rows the server fails to boot.
    `sSpellItemEnchantmentStore` exists (`DBCStores.h`), declared in this module's include chain already.
- **Build tree exists**: `var/build/obj` is a configured CMake tree (`MODULES=static`, Release).
  The module TU is compiled as
  `modules/CMakeFiles/modules.dir/mod-random-enchants/src/random_enchants.cpp.o`
  — targeted incremental compile is possible (Step 7.1) without a full build.
- **DBC files** live at `env/dist/bin/dbc/` (worldserver `DataDir = "."` relative to `env/dist/bin`):
  `SpellItemEnchantment.dbc`, `ItemRandomProperties.dbc`, `ItemRandomSuffix.dbc`, `RandPropPoints.dbc`
  all present.
- **MySQL** listens on 127.0.0.1:3306; `env/dist/etc/worldserver.conf` declares
  `WorldDatabaseInfo = "127.0.0.1;3306;acore;acore;acore_world"`. Access is **not guaranteed** —
  try `mysql -uacore -pacore acore_world -e "SELECT 1"` once; if it fails, do all verification
  offline (Step 0 has an offline path). Never spend time hunting for DB credentials.
- **Python 3.12** and `mysql` client are available.

---

## 2. Deliverables (file map)

| File | Kind | Source |
| --- | --- | --- |
| `modules/mod-random-enchants/src/random_enchants.h` | modify | spec §2.3 |
| `modules/mod-random-enchants/src/random_enchants.cpp` | modify | spec §2.4 |
| `modules/mod-random-enchants/src/RE_loader.cpp` | **unchanged** | spec §2.1 |
| `modules/mod-random-enchants/conf/random_enchants.conf.dist` | modify | spec §4.8 |
| `modules/mod-random-enchants/data/sql/db-world/001_mod_re_rates.sql` | new, hand-written | spec §3.1/3.2, §4.3/4.4/4.5 |
| `modules/mod-random-enchants/data/sql/db-world/002_mod_re_enchant_matrix.sql` | new, generated | spec §3.4 |
| `modules/mod-random-enchants/data/sql/db-world/003_mod_re_variants.sql` | new, generated | spec §3.3/3.5 |
| `modules/mod-random-enchants/tools/generate_enchant_matrix.py` | new | spec §3.4 |
| `modules/mod-random-enchants/tools/generate_variants.py` | new | spec §3.5 |
| `modules/mod-random-enchants/README.md` | new | spec §2.1 (does not exist today) |
| `modules/mod-random-enchants/data/sql/db-world/item_enchatment_random_tiers.sql` | **untouched** | spec §2.1 |
| `specs/<adw_id>_random-enchants-build.md` | copy of this plan | — |

The core's SQL updater auto-applies `modules/<mod>/data/sql/db-world/*.sql` in filename order
(verified in `src/server/database/Updater/UpdateFetcher.cpp:159-165`), so the `001/002/003` prefix
guarantees table-create order. Do not rename the files.

---

## 3. Build steps

### Step 0 — DBC source verification (spec §3.0; gate for everything below)

Purpose: prove the live enchant store's max ID is below `EnchantMatrixIdBase = 100000` before
populating the matrix.

1. Try the live DB once: `mysql -uacore -pacore acore_world -e "SELECT 'spellitemenchantment_dbc' t, COUNT(*) FROM spellitemenchantment_dbc UNION ALL SELECT 'itemrandomproperties_dbc', COUNT(*) FROM itemrandomproperties_dbc UNION ALL SELECT 'itemrandomsuffix_dbc', COUNT(*) FROM itemrandomsuffix_dbc UNION ALL SELECT 'randproppoints_dbc', COUNT(*) FROM randproppoints_dbc;"` — expect 0 rows in all four (schema-only dump).
2. **Offline fallback (always run this — it is the authoritative gate):** parse
   `env/dist/bin/dbc/SpellItemEnchantment.dbc` with a small Python `struct` reader
   (DBC header: 4×uint32 magic `'WDBC'`, recordCount, fieldCount, recordSize, stringSize; then
   recordCount records of recordSize bytes; first field of each record is the uint32 ID). Print
   `recordCount` and `max(ID)`. **Gate: proceed only if max live ID < 100000.** Vanilla 3.3.5 has
   < 5000 enchant rows; expect the same here.
3. Record the result in a short comment at the top of `002_mod_re_enchant_matrix.sql`:
   "Gate verified: max live SpellItemEnchantment ID = <N> (< recordCount> rows) < 100000; matrix
   base 100000 is safe. Mirror tables empty (schema-only dump); .dbc files are the live source."
   If the DBC file is unreadable or max ID ≥ 100000, **stop and report** — do not generate.

Do not spend time booting the server; the file parse plus the empty mirror schema is sufficient
evidence per spec §3.0 (the reasoning to record is in the comment above).

### Step 1 — `001_mod_re_rates.sql` (hand-written)

Create `modules/mod-random-enchants/data/sql/db-world/001_mod_re_rates.sql` containing exactly
three `CREATE TABLE IF NOT EXISTS` blocks plus seed `INSERT`/`REPLACE` data, in this order:

1. **`mod_re_rates`** — spec §3.1 DDL verbatim (columns `band, base_quality, stay, tier1..tier5`,
   PK `(band, base_quality)`). Seed **28 rows** = the exact starting table in spec §4.3
   (7 bands × 4 base qualities, columns as printed: `band, base_quality, stay, tier1, tier2,
   tier3, tier4, tier5`). Copy every number verbatim from §4.3. The `—` cells are **0**.
   Keep the §4.3 flags: rows sum to 100 per row; no cross-base normalization.
2. **`mod_re_pool_rates`** — spec §3.1 DDL verbatim (`rate_key varchar(64) PK, rate_value float`).
   Seed rows = every key in the spec §3.1 key namespace, with the weights from spec §4.4:
   - `pool_weight:<ARCH>` for each archetype and each stat in §4.4.1's resolved rows —
     **resolve Str/Agi per class exactly as §4.4.1 says**:
     - `CAST ER`: `INT 35, SP 30, CRIT 15, HASTE 12, SPI 8`
     - `HEALER`: `INT 30, SPI 25, MP5 20, SP 15, HASTE 10`
     - `PHYSICAL`: `STR 35, AGI 35, AP 20, CRIT 15, HASTE 12, HIT 10, EXP 8`
       (both STR and AGI keys, weight 35 each; §4.4.1 "Str/Agi 35")
     - `TANK`: `STA 40, STR 20, DEF 15, DODGE 10, PARRY 10, HIT 8, EXP 7`
       (§4.4.1 resolved TANK plate: Parry 10, Hit 8, Expertise 7; bear overrides are v2 — do not add)
   - `weapon_pool_weight:<POOL>` per §4.4.2: `WEAPON_CASTER`: `INT 40, SP 30, HASTE 15, CRIT 15`;
     `WEAPON_MELEE`: `STR 40, AGI 40, AP 25, CRIT 15, HASTE 10, EXP 10`;
     `WEAPON_HUNTER`: `AGI 40, AP 30, CRIT 15, HIT 15`
   - `jewelry_weight:<ARCH>` per §4.4.3 (primary 50 / secondary 30 / utility 20):
     `CAST ER`: `INT 50, CRIT 30, HASTE 20`; `HEALER`: `INT 50, SPI 30, MP5 20`;
     `PHYSICAL`: `STR 50, AGI 50, AP 30, CRIT 20`; `TANK`: `STA 50, DEF 30, DODGE 20`
   - `relic_weight:<ARCH>` per §4.4.4 (single stat, 100):
     `CAST ER`: `INT 100`; `HEALER`: `INT 100`; `PHYSICAL`: `STR 100, AGI 100`; `TANK`: `STA 100`
   - Use the exact STAT tokens from §3.1: `INT, SPI, STA, STR, AGI, SP, AP, MP5, CRIT, HASTE,
     HIT, EXP, DEF, DODGE, PARRY`.
3. **`mod_re_class_archetype`** — spec §3.2 DDL verbatim. Seed **10 rows** = the fixed v1 map in
   §4.5 (class → archetype, note column optional): `1 PHYSICAL, 2 HEALER, 3 PHYSICAL, 4 PHYSICAL,
   5 HEALER, 6 PHYSICAL, 7 HEALER, 8 CASTER, 9 CASTER, 11 HEALER`.

Use `INSERT INTO ... VALUES ... ON DUPLICATE KEY UPDATE` or `REPLACE INTO` so the file is
idempotent (updater re-apply safe). No `DROP TABLE` — the tables are new; `CREATE TABLE IF NOT EXISTS`.

### Step 2 — matrix generator + `002_mod_re_enchant_matrix.sql`

Write `modules/mod-random-enchants/tools/generate_enchant_matrix.py` — **pure Python 3 stdlib,
no DB access** (spec §3.4). Embedded constants:

- Band table (spec §4.2), `band → (ilvlMin, ilvlMax, magMin, magMax)`:
  1:(1,20,10,30) 2:(21,40,30,60) 3:(41,70,60,100) 4:(71,120,100,180) 5:(121,180,180,280)
  6:(181,240,280,400) 7:(241,277,400,600)
- Stats in fixed order with `ITEM_MOD_*` values (spec §3.4 statIndex order + §2.5 list):
  `INT(0)→5, SPI(1)→6, STA(2)→7, STR(3)→4, AGI(4)→3, SP(5)→45, AP(6)→38, MP5(7)→43,
  CRIT(8)→32, HASTE(9)→36, HIT(10)→31, EXP(11)→37, DEF(12)→12, DODGE(13)→13, PARRY(14)→14`
- Tier multipliers (spec §4.1): `T1 1.0, T2 1.15, T3 1.35, T4 1.6, T5 1.9`
- `Rungs = 5` (default; CLI `--rungs`), `MatrixIdBase = 100000` (CLI `--base`)
- ID formula (spec §3.4): `ID = MatrixIdBase + (band-1)*375 + statIndex*25 + (tier-1)*5 + rung`
  (rung 0..4; tier 1..5). Expected range 100000..102624 → **2625 rows**.

Row contents (spec §3.4): `Charges=0`; `Effect_1=5` (`ITEM_ENCHANTMENT_TYPE_STAT`), `Effect_2=0`,
`Effect_3=0`; `EffectPointsMin_1 = EffectPointsMax_1 = round(rungValue × tierMult)` where
`rungValue = magMin + (magMax - magMin) * rung / (Rungs - 1)`; Min/Max_2/3 = 0; `EffectArg_1 =
ITEM_MOD_*`, Arg_2/3 = 0; `Name_Lang_enUS = "Scaled <display>"` (display names: `Intellect`,
`Spirit`, `Stamina`, `Strength`, `Agility`, `Spell Power`, `Attack Power`, `Mana/5`, `Crit Rating`,
`Haste Rating`, `Hit Rating`, `Expertise Rating`, `Defense Rating`, `Dodge Rating`, `Parry Rating`);
all other `Name_Lang_*` NULL; `Name_Lang_Mask=0`; `ItemVisual=0, Flags=0, Src_ItemID=0,
Condition_Id=0, RequiredSkillID=0, RequiredSkillRank=0, MinLevel=0`.

Output: emit `modules/mod-random-enchants/data/sql/db-world/002_mod_re_enchant_matrix.sql` as
`REPLACE INTO spellitemenchantment_dbc (\`ID\`,\`Charges\`,\`Effect_1\`,\`Effect_2\`,\`Effect_3\`,
\`EffectPointsMin_1\`,\`EffectPointsMin_2\`,\`EffectPointsMin_3\`,\`EffectPointsMax_1\`,\`EffectPointsMax_2\`,\`EffectPointsMax_3\`,
\`EffectArg_1\`,\`EffectArg_2\`,\`EffectArg_3\`,\`Name_Lang_enUS\`,\`Name_Lang_Mask\`,\`ItemVisual\`,\`Flags\`,\`Src_ItemID\`,\`Condition_Id\`,\`RequiredSkillID\`,\`RequiredSkillRank\`,\`MinLevel\`) VALUES ...`
with one row per line, followed by a trailing `;`. Only `Name_Lang_enUS` among the name columns is
populated (client falls back to enUS; spec §3.4). Idempotent via `REPLACE`. Also print
`Generated <n> rows, ID range <first>..<last>` to stdout — the builder must **run the generator**
and commit the resulting file to the working tree (the generated file is a deliverable).

Deterministic sanity checks to assert in the script (fail loudly):
- row count == 7×15×5×5 == 2625
- first ID 100000 (band1/stat0/tier1/rung0), last ID 102624
- example (spec §3.4): band 1 (10..30), rung 2 (20), T3 (×1.35) → amount 27

### Step 3 — variant generator + `003_mod_re_variants.sql`

Write `modules/mod-random-enchants/tools/generate_variants.py` — **pure Python 3 stdlib, no DB
access** (spec §3.5). It reads a base `item_template` export; the default input is
`data/sql/base/db_world/item_template.sql` (repo path, CLI `--input`).

Parser requirements (important — verified against the real dump):
- Extract the CREATE TABLE column order from the same file to build a `name → position` map
  (**139 columns** in this dump; assert every parsed row has this many fields; log and skip rows
  that don't). Handle MySQL string escaping: values are single-quoted, embedded quotes doubled
  (`''`), backslash-escapes possible; implement a small quote-aware splitter.
- Count parsed rows and print them; assert `max(entry) < VariantEntryBase` (spec §3.5 gate:
  max is 56806 < 1000000).

Eligibility (spec §1.4): `class ∈ {2,4}` and `Quality ∈ {1,2,3,4}`. For each eligible base item,
for each tier `T ∈ {1..5}` where `tierQuality[T] > baseQuality` (no-backward rule):
`T1→q2, T2→q3, T3→q4, T4→q5, T5→q5`.

Variant row (spec §3.5): sequential `entry` from `VariantEntryBase = 1000000` (CLI `--entry-base`).
- `name` = `<Prefix> <base name>`; prefixes from §4.1: `Superior, Exquisite, Regal, Legendary, Mythic`
  (CLI `--prefixes`, default the §4.8 config string).
- `Quality` = tier quality; `ItemLevel` = base ItemLevel **unchanged** (spec §5 12f).
- Stat multiplier `m` = `round(pow(1.75, variantQuality - baseQuality), 2)` → 1.75 / 3.06 / 5.36 / 9.38
  (spec §4.1; verify against the compound check: 1.75, 3.0625→3.06, 5.3594→5.36, 9.3789→9.38).
- Scaled columns: `armor = round(base.armor × m)`; `dmg_min1, dmg_max1, dmg_min2, dmg_max2 =
  round(base × m)`; every `stat_value_i` (i=1..10) where `stat_type_i != 0` → `round(value × m)`
  (stat types and `StatsCount` unchanged).
- **All other columns copied verbatim** from the base row, including `RandomProperty=0`,
  `RandomSuffix=0` (required for free PROP slots, spec §2.5).
- **Statless items** (spec §3.5.7): base has `StatsCount == 0` **or** all `stat_type_i == 0`,
  **and** `dmg_min1 == 0`, **and** all `spellid_1..5 ∈ {0,-1}`. Then:
  - `StatsCount = 1`, `stat_type1 = <seed stat>`, `stat_value1 = round(seedValue × tierMult)`
    where `tierMult` is the tier's enchant multiplier from §4.1 (spec §5 12g).
  - `seedValue` = uniform draw in `[bandMin, bandMax]` from the §4.2 band of the base ItemLevel;
    **drawn once per row at generation time** — use `random.Random(entry)` seeded by the variant
    entry so regeneration is deterministic.
  - `[RESOLVED]` seed stat by armor subclass (spec §3.5.7 says "cloth → CASTER pool, leather →
    PHYSICAL, mail → PHYSICAL, plate → TANK, shield → TANK"): cloth(1)→`INT`, leather(2)→`AGI`,
    mail(3)→`STR`, plate(4)→`STA`, shield(6)→`STA`. Document this resolution in a code comment.
    (Jewelry/relic get no template seed in v1.)
- Skip tiers whose `tierQuality <= baseQuality` — never emit a same-or-lower-quality variant.

Output `modules/mod-random-enchants/data/sql/db-world/003_mod_re_variants.sql`:
1. `CREATE TABLE IF NOT EXISTS \`mod_re_item_variants\`` — DDL from spec §3.3 verbatim (PK
   `(base_entry, tier)`, `KEY idx_variant_entry (variant_entry)`).
2. One `INSERT INTO \`item_template\` (<all 139 columns>) VALUES` multi-row block with one
   variant row per line (same style as the dump).
3. `INSERT INTO \`mod_re_item_variants\` (\`base_entry\`,\`tier\`,\`variant_entry\`) VALUES ...`.

Run modes (CLI):
- `--seed-entries 25,35,36,60,3270,727,753,821,892,754,776,720,862,888,647,809,833,867,940,5522,13602`
  → **default seed run** (also a `--seed-file` alternative). This list was verified against the
  dump and covers: common/uncommon/rare/epic bases, weapons + armor, jewelry (862 finger ring,
  833 trinket), relic (5522, inventory type 28), statless items (60, 3270 Flax Vest), low/mid ilvl.
  Add 1-2 endgame (ilvl ≥ 181, band 6-7) eligible items of your choice found in the dump so the
  top band is exercised; note them in the README.
- `--all` → full-scale generation (all eligible base items; ~50-78k variant rows per spec). This
  is supported but **not the default deliverable**; the seed run is what ships in the tree.
  Document both modes in README.
- Regeneration is idempotent (file is rewritten from scratch; deterministic seed via `Random(entry)`).

Assert in the script: every `variant_entry` unique; `(base_entry, tier)` unique; every variant's
`Quality` > base `Quality`; no `entry` < 1000000 appears in the variant block.

### Step 4 — C++ rework (`src/random_enchants.h`, `src/random_enchants.cpp`)

Implement spec §2.3 / §2.4 exactly. **RE_loader.cpp untouched.**

#### 4.1 `random_enchants.h`
- Keep `enum ItemQuality { GREY=0 … ORANGE=5 }` (or use core `ItemQualities`; do not change behavior).
- Add `#include <optional>` (C++17) plus `<vector>`, `<utility>` as needed.
- Add (spec §2.3, verbatim shapes):
  - `enum QualityTier : uint8 { TIER_1 = 1, TIER_2, TIER_3, TIER_4, TIER_5 };`
  - `enum Archetype : uint8 { ARCH_CASTER, ARCH_HEALER, ARCH_PHYSICAL, ARCH_TANK };`
  - `enum WeaponPool : uint8 { WEAPON_POOL_CASTER, WEAPON_POOL_MELEE, WEAPON_POOL_HUNTER };`
  - `struct EnchantRollResult { uint32 enchantId; uint8 slot; };`
  - Declarations:
    - `bool rollQualityAndEnchant(Player* player, Item* item);` (replaces `rollPossibleEnchant`)
    - `uint8 getIlvlBand(uint32 itemLevel);`
    - `std::optional<QualityTier> rollQualityTier(Player* player, const ItemTemplate* baseTemplate);`
    - `uint32 getVariantEntry(uint32 baseEntry, QualityTier tier);`
    - `void swapToVariant(Player* player, Item* item, uint32 variantEntry);`
    - `Archetype getArchetype(Player* player);`
    - `std::vector<std::pair<uint32,float>> getStatPool(Item* item, Archetype archetype);`
    - `uint32 getMatrixEnchantId(uint8 band, uint32 statType, QualityTier tier, uint8 rung);`
    - `bool rollOneEnchant(Player* player, Item* item, EnchantmentSlot slot);`
    - `uint32 getRandEnchantment(Item* item);` — kept for the legacy-pool fallback path.
  - Remove the `rollPossibleEnchant` declaration.
  - `RandomEnchantsPlayer` class and its five hook overrides stay as-is (spec §2.2).

#### 4.2 `random_enchants.cpp` — `rollQualityAndEnchant` (spec §1.5, §2.4)

```
1. Guards (each gated by config):
   - if (!sConfigMgr->GetOption<bool>("RandomEnchants.Enable", true)) return false;
   - if (!item || !item->IsInWorld()) return false;
   - const ItemTemplate* tpl = item->GetTemplate(); if (!tpl) return false;
   - class guard: tpl->Class != ITEM_CLASS_WEAPON && tpl->Class != ITEM_CLASS_ARMOR → return false;
   - re-roll protection: SELECT 1 FROM <VariantMappingTable> WHERE variant_entry = tpl->ItemId LIMIT 1
     → if a row exists, the item is already a variant → return false (spec §2.4.1).
2. Capture BASE template BEFORE any swap:
   baseEntry = tpl->ItemId; baseIlvl = tpl->ItemLevel; baseQuality = tpl->Quality;
   baseClass = tpl->Class; baseSubClass = tpl->SubClass; baseInventoryType = tpl->InventoryType.
3. Quality roll (only if baseQuality ∈ {1,2,3,4} AND RandomEnchants.QualitySystem.Enable = 1):
   band = getIlvlBand(baseIlvl);
   auto tier = rollQualityTier(player, tpl);
   if (tier) { variantEntry = getVariantEntry(baseEntry, *tier); if (variantEntry) swapToVariant(...); }
   (tier == nullopt ⇒ STAY: no swap; enchant roll runs on the base item.)
4. Enchant roll (only if baseQuality ∈ {1,2,3,4,5} — matches current module's NORMAL..LEGENDARY guard):
   baseItemLevel = baseIlvl (band from BASE ilvl — spec §1.5 step 6);
   tier for magnitude = [RESOLVED] the item's CURRENT tier after the quality roll:
     upgraded ⇒ the rolled QualityTier; STAY ⇒ tierForQuality(baseQuality) with 1→T1,2→T2,3→T3,4→T4,5→T5;
   chained slots (spec §4.6): rollOneEnchant(player, item, PROP_ENCHANTMENT_SLOT_0) at 70%;
     if hit, rollOneEnchant(..., PROP_ENCHANTMENT_SLOT_1) at 65%; if hit, rollOneEnchant(..., PROP_ENCHANTMENT_SLOT_2) at 60%.
     No total cap.
   (If RandomEnchants.UseLegacyEnchantPool = 1: instead run the OLD path — getRandEnchantment + slots
   {0,1,5} — restoring legacy behavior; default 0 per §4.8.)
5. Chat message (unchanged text, spec §1.5 step 7): name resolves from the CURRENT (possibly
   swapped) template with locale lookup exactly like the existing code; count = number of enchants applied.
```

#### 4.3 `rollQualityTier` (spec §2.3)
- `band = getIlvlBand(baseTemplate->ItemLevel)`.
- One indexed query (read-per-roll, spec §5 12c):
  `SELECT stay, tier1, tier2, tier3, tier4, tier5 FROM <QualityRatesTable> WHERE band = {} AND base_quality = {}`
  (config `RandomEnchants.QualityRatesTable`, default `mod_re_rates`). If no row → return `std::nullopt`.
- Outcomes = STAY + tiers with weight > 0 **and** tierQuality > baseQuality (data already encodes
  the no-backward rule; guard anyway). Weighted pick over those outcomes (sum weights, uniform
  draw). STAY → `std::nullopt`; else the `QualityTier`. **No normalization** — weights used as-is.

#### 4.4 `getVariantEntry` / `swapToVariant`
- `getVariantEntry`: `SELECT variant_entry FROM <VariantMappingTable> WHERE base_entry = {} AND tier = {} LIMIT 1`; return 0 if none.
- `swapToVariant` (spec §2.4 step 4, verbatim):
  ```cpp
  item->SetEntry(variantEntry);          // Object::SetEntry → OBJECT_FIELD_ENTRY
  item->SetState(ITEM_CHANGED, player);  // persists to DB on next save
  ```

#### 4.5 `getIlvlBand` (spec §4.2)
Return 1..7 from the band table; clamp ilvl > 277 → 7, ilvl < 1 → 1. Bands:
`1:1-20, 2:21-40, 3:41-70, 4:71-120, 5:121-180, 6:181-240, 7:241-277`.

#### 4.6 `getArchetype` (spec §2.4, §4.5)
- Query `SELECT archetype FROM <ClassArchetypeTable> WHERE class_id = {} LIMIT 1`
  (config `RandomEnchants.ClassArchetypeTable`, default `mod_re_class_archetype`).
- Fall back to the hard-coded §4.5 map if no row: 1→PHYSICAL, 2→HEALER, 3→PHYSICAL, 4→PHYSICAL,
  5→HEALER, 6→PHYSICAL, 7→HEALER, 8→CASTER, 9→CASTER, 11→HEALER. Unknown class → PHYSICAL.

#### 4.7 `getStatPool` (spec §2.4, §4.4; returns `vector<pair<uint32 stat, float weight>>`)
- class 2 (weapon): inspect the weapon template's `stat_type1..10`:
  any `ITEM_MOD_INTELLECT(5)` or `ITEM_MOD_SPELL_POWER(45)` → `WEAPON_POOL_CASTER`;
  else any `ITEM_MOD_AGILITY(3)` → `WEAPON_POOL_HUNTER`;
  else any `ITEM_MOD_STRENGTH(4)` → `WEAPON_POOL_MELEE`;
  else → `WEAPON_POOL_MELEE` (default).
  Weights from `<PoolRatesTable>` keys `weapon_pool_weight:<POOL>:<STAT>`.
  `[RESOLVED]` melee Str-vs-Agi: pool rows contain both `STR` and `AGI` keys (weight 40 each);
  return **both** and let the weighted pick decide (spec keeps "Str/Agi resolved per class" as a
  v2 nuance; returning both is the simple, weight-faithful v1).
- inventory type ∈ {2 NECK, 11 FINGER, 12 TRINKET} → jewelry pool of the looting player's
  archetype: keys `jewelry_weight:<ARCH>:<STAT>`.
- inventory type == 28 (RELIC) → relic pool: keys `relic_weight:<ARCH>:<STAT>`.
- otherwise (armor incl. shields) → armor pool of the archetype: keys `pool_weight:<ARCH>:<STAT>`.
- Weights are read per roll (spec §5 12c): for each stat in the pool, one
  `SELECT rate_value FROM <PoolRatesTable> WHERE rate_key = '{}'` query. If a key is missing, use
  the built-in weight from §4.4 tables as fallback (defensive; seed data provides all keys).
- Hold the per-archetype stat lists in code mirroring §4.4.1/4.4.3/4.4.4 (the spec's tables are the
  source of truth; the DB rows make them tunable).

#### 4.8 `getMatrixEnchantId` (spec §3.4)
- Map the stat's `ITEM_MOD_*` value to its index (0..14) via the fixed order in Step 2
  (INT→0, SPI→1, STA→2, STR→3, AGI→4, SP→5, AP→6, MP5→7, CRIT→8, HASTE→9, HIT→10, EXP→11,
  DEF→12, DODGE→13, PARRY→14). Unknown stat → return 0 (caller skips).
- `return MatrixIdBase + (band-1)*375 + statIndex*25 + (tier-1)*5 + rung;`
  with `MatrixIdBase = sConfigMgr->GetOption<uint32>("RandomEnchants.EnchantMatrixIdBase", 100000)`.

#### 4.9 `rollOneEnchant` (spec §2.4; returns true if an enchant was applied)
1. `band = getIlvlBand(baseItemLevel)` (base ilvl passed in / captured pre-swap).
2. `archetype = getArchetype(player)`; `pool = getStatPool(item, archetype)`.
3. `statType` = weighted pick from pool (weights from `mod_re_pool_rates`).
4. `rungs = GetOption<uint32>("RandomEnchants.EnchantMatrixRungs", 5)`; `rung = urand(0, rungs-1)`.
5. `enchantId = getMatrixEnchantId(band, statType, tier, rung)`.
6. Validate `sSpellItemEnchantmentStore.LookupEntry(enchantId)` (skip if null), then:
   ```cpp
   player->ApplyEnchantment(item, slot, false);
   item->SetEnchantment(slot, enchantId, 0, 0);
   player->ApplyEnchantment(item, slot, true);
   ```
   where `slot` is the PROP slot passed in (7/8/9). Return true.
- The declared `EnchantRollResult` struct: `[RESOLVED]` use it as the internal return of a small
  helper `std::optional<EnchantRollResult> pickEnchant(Item*, uint8 band, QualityTier tier,
  Archetype archetype)` that performs steps 1-5; `rollOneEnchant` calls it, applies, returns bool.
  This satisfies the header declaration without changing the spec'd `bool` signature.

#### 4.10 Legacy path
Keep `getRandEnchantment` byte-for-byte functional (unchanged behavior). When
`RandomEnchants.UseLegacyEnchantPool = 1`, `rollQualityAndEnchant` should skip the quality roll and
use the old flow: `getRandEnchantment` + slots `{0,1,5}` with the same 70/65/60 chances and the
same chat message. Default is 0 (new path).

#### 4.11 Config reads (summary — all keys from spec §4.8)
`RandomEnchants.Enable`, `QualitySystem.Enable`, `QualityRatesTable` ("mod_re_rates"),
`PoolRatesTable` ("mod_re_pool_rates"), `ClassArchetypeTable` ("mod_re_class_archetype"),
`VariantMappingTable` ("mod_re_item_variants"), `VariantEntryBase` (1000000),
`EnchantMatrixIdBase` (100000), `EnchantMatrixRungs` (5), `StatlessSeed.Enable` (1) — read for
documentation parity (the seed is baked into generated templates; note this in a comment),
`UseLegacyEnchantPool` (0), `VariantPrefixes` ("Superior,Exquisite,Regal,Legendary,Mythic") — read
and split for name prefix selection (used by the generator's default; in C++ it is not needed at
runtime, but reading it is harmless — the swap uses the variant's baked name), `AnnounceOnLogin`,
`OnLoginMessage`, `OnLoot`, `OnCreate`, `OnQuestReward`, `OnGroupRoll`, `EnchantChance1/2/3`.
The four event flags are checked in the hook bodies exactly as today (they call
`rollQualityAndEnchant` instead of `rollPossibleEnchant`).

#### 4.12 Includes / style
- Header: add `#include <optional>`; keep existing includes.
- cpp: add `<vector>`, `<utility>`, `<cmath>` (for `std::round`), `<algorithm>` if needed.
  `sSpellItemEnchantmentStore`, `WorldDatabase`, `ITEM_*` enums are already reachable via the
  module include chain (current code already uses them); do not add core includes that don't exist.
- Use the module's existing `WorldDatabase.Query("...{}...", args...)` fmt style for all queries.
- All code must be coherent valid C++17. `[[nodiscard]]` where the spec lists it.
- Comment every `[RESOLVED]` decision in code (spec §1 preamble requires documenting deviations).

### Step 5 — config (`conf/random_enchants.conf.dist`)

Keep every existing block verbatim. Append a "Quality System" section (spec §4.8) with the exact
keys and defaults, each with a short comment:
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
Comment each key (2-3 lines each), matching the file's existing style.

### Step 6 — README.md (new)

`modules/mod-random-enchants/README.md` — short note per spec §2.1: what changed (quality roll +
scaled enchant matrix + PROP slots 7-9 + no total cap), how to regenerate the SQL
(`python3 tools/generate_enchant_matrix.py`, `python3 tools/generate_variants.py --seed-entries …`
/ `--all`), the client DBC patch requirement (spec §5 12d: custom enchant IDs ≥ 100000 have no
client names until the client `SpellItemEnchantment.dbc` is patched; server-side behavior
unaffected), the legacy flag (`UseLegacyEnchantPool = 1`), and the v1 notes: variant
`item_template_locale` rows out of scope, post-pickup swap loot-window nuance (spec §5 12b),
read-per-roll rates (12c).

---

## 4. Verification (map to the "Done" criteria)

1. **Targeted C++ compile** (no full build): `cmake --build var/build/obj --target modules -j$(nproc)`
   OR the exact object target `make -C var/build/obj mod-random-enchants/src/random_enchants.cpp.o`.
   Both `random_enchants.cpp` and `random_enchants.h` must compile clean (the header compiles as
   part of the TU). If the tree is stale and reconfigures, that's fine — the point is the module TU
   compiles. Do not build the worldserver binary.
2. **Generator runs**: both scripts executed; stdout shows
   `002: 2625 rows, ID 100000..102624` and `003: <N> variants from <M> base items`.
3. **SQL spot checks** (grep/`python3` counts):
   - `001`: 28 rows in `mod_re_rates` (7 bands × 4 qualities); every §4.3 number present;
     `mod_re_pool_rates` has all keys from Step 1; `mod_re_class_archetype` has 10 rows.
   - `002`: exactly 2625 `(`-leading value rows; first ID 100000, last 102624; spot-check the
     band-1/rung-2/T3 amount == 27 (spec §3.4 example); `Effect_1` always 5; `EffectArg_1` in the
     ITEM_MOD set; `Name_Lang_enUS` starts with "Scaled ".
   - `003`: variant entries all ≥ 1000000 and unique; `(base_entry, tier)` unique; each variant
     `Quality` > base `Quality`; no-backward rule holds (common gets T1..T5, uncommon T2..T5,
     rare T3..T5, epic T4..T5); Flax Vest (3270) variants have `StatsCount=1` with a seeded stat;
     ring (862)/trinket (833)/relic (5522) variants present if in the seed list.
4. **Code review pass** (self-check before finishing): walk `rollQualityAndEnchant` against spec
   §1.5 steps 1-7; confirm slot array is `{PROP_ENCHANTMENT_SLOT_0, _1, _2}` (7/8/9), no total cap,
   re-roll protection query present, base-ilvl band captured pre-swap, STAY path runs enchant on
   the base item, `UseLegacyEnchantPool` gate present, chat message unchanged in shape.
5. **No-mutation audit**: `git -C modules/mod-random-enchants status` and `git status` are NOT to be
   run (no git at all). Instead, verify by file listing that only the allowed paths changed
   (compare against the Deliverables table). All work stays uncommitted.

Optional (only if `mysql -uacore -pacore` connects): apply `001` then `002` then `003` to
`acore_world` and run the §3.0 count checks; if the DB is unreachable, skip — file-level checks
above are the gate.

---

## 5. Out-of-scope reminders (do NOT do)

- No git operations of any kind in either repo.
- No edits to core `src/server/game/` or `src/server/shared/`.
- No edits to `RE_loader.cpp`, `item_enchatment_random_tiers.sql`, loot templates, or any file
  outside the Deliverables table (plus this plan's `specs/` copy).
- No client DBC patch artifact — document only.
- No full worldserver build; no server restart; no DB import required (optional if creds work).
- No `item_template_locale` rows for variants (v1 note only).
- Do not "improve" the design — implement the spec. If something in the spec is ambiguous, use the
  `[RESOLVED]` decisions above; if genuinely broken, stop and report rather than improvise.
