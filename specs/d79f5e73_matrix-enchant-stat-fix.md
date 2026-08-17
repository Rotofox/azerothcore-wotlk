# Plan — Fix matrix enchant stats not applying on equip (mod-random-enchants)

## Summary

The enchant-matrix rows in `spellitemenchantment_dbc` (IDs 100000..102624) encode
`Effect_1 = 6`. In this fork (and in the 3.3.5a client) `ITEM_ENCHANTMENT_TYPE_STAT = 5`;
`6` is `ITEM_ENCHANTMENT_TYPE_TOTEM`, whose case in `Player::ApplyEnchantment`
(PlayerStorage.cpp:4626) does nothing for armor and non-shaman weapons. The server
therefore never enters the STAT case, so equipping an item with a matrix enchant raises
no stat. The tooltip still shows the enchant **name** ("Scaled Intellect") because the
row exists and `Name_Lang_enUS` is set; the client also treats type 6 as TOTEM and
renders no stat line.

Fix (direction **a** — smallest, module-side, vanilla-consistent): correct the row
encoding to `Effect_1 = 5` in the generator, regenerate the matrix SQL, re-apply it to
the live DB, restart worldserver. **No C++ changes, no conf changes, no rebuild, no git
operations.**

## Root-cause evidence (all verified in this repo / live DB)

1. **Struct field mapping** — `SpellItemEnchantmentEntry` (src/server/game/DataStores/../shared/DataStores/DBCStructure.h:1877-1894) with format `SpellItemEnchantmentfmt = "niiiiiiixxxiiissssssssssssssssxiiiiiii"` (DBCfmt.h:112):
   - `type[s]`    ← Effect_1..3 (cols 2-4)
   - `amount[s]`  ← EffectPointsMin_1..3 (cols 5-7)
   - `spellid[s]` ← EffectArg_1..3 (cols 11-13)
   - EffectPointsMax (cols 8-10) is skipped (`x`) — server uses EffectPointsMin as the amount.
   The generator already writes EffectArg_1 = ITEM_MOD and EffectPointsMin/Max = amount, so
   those fields are correct. Only the **type** value is wrong.
2. **Fork enum** — `ItemEnchantmentType` (src/server/shared/DataStores/DBCEnums.h:368-374):
   `STAT = 5`, `RESISTANCE = 4`, `TOTEM = 6`. The generator writes 6.
3. **Vanilla DBC cross-check** — parsed `env/dist/bin/dbc/SpellItemEnchantment.dbc` (2656 rows):
   real stat enchants use `type1 = 5`, `arg1 = ITEM_MOD`, `min = max = amount`
   (e.g. ID 79-95 "+1..5 Intellect": type=5, arg=5). So type 5 is correct for BOTH server
   and client.
4. **Server application path** — `Player::_ApplyItemMods` (Player.cpp:6611) →
   `ApplyEnchantment(item, apply)` (PlayerStorage.cpp:4291) loops all 12 slots (incl.
   PROP 7/8/9). Per-slot (PlayerStorage.cpp:4297): gates pass for our rows
   (EnchantmentCondition=0, requiredLevel=0, requiredSkill=0); the module registers no
   `OnPlayerCanApplyEnchantment`. The STAT case (PlayerStorage.cpp:4411) reads
   `enchant_amount = amount` (nonzero → no random-suffix fallback) and switches on
   `enchant_spell_id` = EffectArg_1. All 15 matrix ITEM_MOD values are present as cases
   (3,4,5,6,7,12,13,14,31,32,36,37,38,43,45 — verified in the switch).
5. **Live DB** — `SELECT ... FROM spellitemenchantment_dbc WHERE ID >= 100000`:
   2625 rows, `Effect_1 = 6` on every row (e.g. ID 100000: Effect_1=6, PointsMin=10,
   Arg=5). Character DB has real pre-fix enchanted items (e.g. guid 1036428 item 3213
   carries enchant 100000 in PROP slot 7) — the roll worked; only application was dead.

## Changes (module files only)

### 1. `modules/mod-random-enchants/tools/generate_enchant_matrix.py` (edit)

- Add a named constant near the top (next to the other embedded constants), e.g.:

  ```python
  # ITEM_ENCHANTMENT_TYPE_STAT — src/server/shared/DataStores/DBCEnums.h and the
  # 3.3.5a client agree: STAT = 5, RESISTANCE = 4, TOTEM = 6. Verified against
  # env/dist/bin/dbc/SpellItemEnchantment.dbc rows 79-95 ("+1..5 Intellect" use
  # type=5, arg=5, min=max=amount).
  STAT_EFFECT_TYPE = 5
  ```

- Fix the docstring (currently line ~14): `Effect_1 = 6 (ITEM_ENCHANTMENT_TYPE_STAT; ...)`
  → state that Effect_1 = 5 (STAT), and that the earlier "6 = STAT" claim was wrong
  (6 is TOTEM in this fork and in 3.3.5a).
- In `emit_sql`, replace the hard-coded `"6", "0", "0"` for Effect_1..3 with
  `str(STAT_EFFECT_TYPE), "0", "0"` and fix the inline comment (currently
  `# Effect_1..3 (STAT = 6; 5 is RESISTANCE)` → `# Effect_1..3 (STAT = 5; 4 is RESISTANCE, 6 is TOTEM)`).
- Optionally add an assertion in `main()`'s sanity block, e.g.
  `assert STAT_EFFECT_TYPE == 5, "matrix rows must use ITEM_ENCHANTMENT_TYPE_STAT (5)"`
  so a wrong constant fails loudly.
- Do NOT change: the ID formula, STATS table (ITEM_MOD values all match
  ItemTemplate.h), BANDS, TIER_MULTIPLIERS, rung ladder, or the sanity checks.

### 2. `modules/mod-random-enchants/data/sql/db-world/002_mod_re_enchant_matrix.sql` (regenerated)

- Back up the current file (plain `cp` — not a git op), then run from the module dir:
  `python3 tools/generate_enchant_matrix.py`
- Confirm the diff is ONLY `Effect_1` 6 → 5:
  - `grep -cE "^\([0-9]+,0,5," 002_mod_re_enchant_matrix.sql` == 2625
  - `grep -cE "^\([0-9]+,0,6," 002_mod_re_enchant_matrix.sql` == 0
  - `diff <old backup> <new file>` shows only the Effect_1 token changed
    (EffectPointsMin/Max, EffectArg, Name, tail columns identical).

### 3. Re-apply the matrix to the live DB + restart

- `mysql -u acore -pacore acore_world < modules/mod-random-enchants/data/sql/db-world/002_mod_re_enchant_matrix.sql`
  (REPLACE INTO — idempotent; overwrites all 2625 rows in place).
- Verify in SQL:
  `SELECT COUNT(*), MIN(Effect_1), MAX(Effect_1) FROM spellitemenchantment_dbc WHERE ID BETWEEN 100000 AND 102624;`
  → `2625, 5, 5`.
- Restart worldserver. DBC stores are loaded once at startup
  (`LoadDBC` → `DBCDatabaseLoader` overrides/appends from the DB mirror); there is NO
  `.reload` for spellitemenchantment in this fork. Find the process (`pgrep -af worldserver`)
  and restart it the same way it was started. The module is already compiled into
  `env/dist/bin/worldserver` (verified via strings) — **no rebuild needed**.

## Verification (must all pass before "done")

Server-side character sheet checks (the enchant application path is the SAME core code for
every stat; the deterministic test below covers each stat individually):

1. **Existing pre-fix items (cleanest end-to-end)**: character DB already contains items
   with matrix enchants in PROP slot 7 (e.g. Narlesia / Drymen / Gykipus / Thicunk /
   Ohlum bag items; query:
   `SELECT c.name, ii.itemEntry FROM character_inventory ci JOIN item_instance ii ON ii.guid=ci.item JOIN characters c ON c.guid=ci.guid WHERE ii.enchantments LIKE '%10000%';`).
   Log in as such a character, equip the item → the stat(s) now appear on the character
   sheet (was 0 before the fix).
2. **Deterministic per-stat test (all 15 stats)**:
   - `.additem <any eligible base item>` (e.g. 25), get the new guid
     (`SELECT guid FROM item_instance ORDER BY guid DESC LIMIT 1` in acore_characters).
   - The `item_instance.enchantments` column is 36 space-separated tokens
     (12 slots × [id, duration, charges]); PROP slot 7 = tokens 21,22,23 (id,0,0).
     Set the enchant: read the current string, replace token 21 with the matrix ID,
     `UPDATE item_instance SET enchantments = '<36 tokens>' WHERE guid = <guid>;`
   - Relog the character, equip the item, check the sheet; unequip → stat gone;
     re-equip → applied exactly once (no double); relog while equipped → still applied.
   - Band-1/tier-1/rung-0 IDs (amount 10; verify the sheet shows the stat):
     INT 100000, SPI 100025, STA 100050, STR 100075, AGI 100100, SP 100125, AP 100150,
     MP5 100175, CRIT 100200, HASTE 100225, HIT 100250, EXP 100275, DEF 100300,
     DODGE 100325, PARRY 100350.
     Ratings (CRIT/HASTE/HIT/EXP/DEF/DODGE/PARRY) show as rating values on the sheet;
     MP5 shows in the mana-regen tooltip.
3. **Regression — roll/quality unchanged**: loot/`create` flow still fires the chat
   messages ("... received N random enchantment(s)"), variant swaps still happen,
   enchant count roll (70/65/60 chain, no cap) unchanged. `pickEnchant` still validates
   via `sSpellItemEnchantmentStore.LookupEntry` — rows still exist.
4. **Tooltip**: the enchant name still shows; after the client patch is regenerated the
   client will also render the green "+X <Stat>" line (server-side works regardless).

## Client-patch requirement (document only — OUT of builder scope)

`client-resources/generate_enchant_dbc_patch.py` reads the matrix rows from the live
mirror (`SELECT ... WHERE ID >= 100000`) and appends them to the client
SpellItemEnchantment.dbc patch. Because the row DATA changed (Effect_1 6 → 5), the
shipped client patch (`client-resources/SpellItemEnchantment.dbc`) MUST be regenerated
before release so client tooltips show the stat lines:
`python3 client-resources/generate_enchant_dbc_patch.py` (needs mysql creds; re-run after
the DB update). The script copies Effect_1 verbatim (`or 6` fallback only applies to
falsy DB values — our rows always carry 5), so no script change is needed. Per the task,
regenerating the client DBC patch is out of scope THIS run; record the requirement in
the summary/notes.

## Out of scope / guardrails

- NO core changes: `src/server/game/` untouched.
- NO git operations at all (no add/commit/push/pull/checkout/reset/clean). Everything
  stays in the working tree; plain file ops (cp/diff) are fine.
- NO changes to `src/random_enchants.cpp`, `src/random_enchants.h`,
  `conf/random_enchants.conf.dist` (module logic is already correct), loot tables,
  quality/variant system, or the client DBC patches.

## Files touched

- `modules/mod-random-enchants/tools/generate_enchant_matrix.py` — edited (type constant
  6 → 5, comments).
- `modules/mod-random-enchants/data/sql/db-world/002_mod_re_enchant_matrix.sql` —
  regenerated (Effect_1 6 → 5 on all 2625 rows).
- Live DB `spellitemenchantment_dbc` (rows 100000..102624) — re-applied; worldserver
  restarted to reload the store.
