# Fury/NexusFrames v2 — spec-aware roles, empower-not-rewrite, variant prices, addon minimap button

Implement the v2 design **exactly as specified** in `specs/fury-nexusframes-v2-design.md` — that document is the authoritative, approved design (status: ready to build; every decision confirmed by the engineer; translate it into a plan and code, do NOT re-design or re-litigate it). Also read, in order: `specs/fury-nexusframes-design.md` (v1), `specs/db8e1683_item-quality-random-enchants.md` (the quality/enchant module spec), and `documentation/fury-nexusframes-handoff.md` (verified facts + gotchas). Re-verify every line number in the live tree before relying on it.

**LOOK AT THE EXAMPLE ADDONS** — `client-resources/example-addons/` contains three real, working 3.3.5 addons (WeakAuras-WotLK, Questie, Bagnon-3.3.5). Use them as the API ground truth:
- `WeakAuras-WotLK/WeakAuras/Libs/LibDBIcon-1.0/LibDBIcon-1.0.lua` (+ its `.toc`/`.xml`) — the minimap-button pattern (self-contained implementation, do NOT bundle the lib).
- `WeakAuras-WotLK/WeakAuras/Libs/AceComm-3.0/AceComm-3.0.lua` — proof that 3.3.5 receives addon messages via `CHAT_MSG_ADDON` (prefix, text, channel, sender).
- `WeakAuras-WotLK/WeakAurasOptions/Libs/AceGUI-3.0/widgets/AceGUIContainer-ScrollFrame.lua` — `EnableMouseWheel(true)` + `OnMouseWheel` scroll pattern.
- `WeakAuras-WotLK/WeakAuras/WeakAuras.lua` — `SetMovable`/`StartMoving` drag patterns.
- `WeakAuras-WotLK/WeakAuras/SubRegionTypes/SubText.lua` — `SetWordWrap(true)`.

**THIS RUN MUST NOT COMMIT, PUSH, PULL, OR OTHERWISE MUTATE GIT IN ANY WAY** — no git add/commit/push/pull/checkout/reset/clean. The run is in `--no-commit` mode: every work product stays in the working tree.

**DO NOT BUILD THE PROJECT.** The engineer compiles, restarts the server, applies SQL to the live databases, packs the MPQ, and smoke-tests — all manually. Concretely forbidden: no cmake/make/ninja, no compile or syntax-check via any toolchain, no starting worldserver/authserver, **no applying SQL to any live database**, no MPQ packing, no DBC patching. The running worldserver and live DBs are READ-ONLY for you (you may query them for verification, never modify). Note: the deterministic test phase in this repo (`adws/adw_modules/quality.py`) is a PLACEHOLDER echo that always passes — treat "done" as *coherent code + the reviewer's approval*, never a compile.

---

## Deliverable 1 — NexusFrames addon (client-only; `client-resources/NexusFrames/`)

Read the current `NexusFrames.lua` first and make **targeted changes only** — do not rewrite the file wholesale. Do NOT touch the transport (CHAT_MSG_ADDON + whisper fallback + dedup + filtered seterrorhandler), the compact bar, the reward list, tier colors, scroll, or SavedVariables keys already in use.

1. **Minimap button** (the primary window toggle):
   - 32×32 `Button` parented to `Minimap`, circular minimap-ring look (texture `Interface\\Minimap\\UI-Minimap-Background` masked, or the ring texture the LibDBIcon example uses), click calls the existing `ToggleWindow()` (there is already a single toggle path in the file — reuse it), `SetClampedToScreen(true)`, drag-to-move via `SetMovable(true)`/`EnableMouse(true)`/`RegisterForDrag("LeftButton")`/`OnDragStart`/`OnDragStop` (`StartMoving`/`StopMovingOrSizing`), position persisted in `NexusFramesDB.minimapPos` (same guarded-restore pattern as `barPos` — see the compact bar code), tooltip "NexusFrames".
   - Keep the existing micro-bar button unchanged (harmless bonus toggle).
2. **Double `%%` fix (bug):** two places render `"+0.1%% Haste"` — the level-up popup line and the reward-list haste line. Both use `string.format("+%s%% Haste", FormatPct(...))` and `FormatPct` already appends `%`. Fix both to `"+%s Haste"`.
3. **Popup border removal:** the level-up popup currently uses the tooltip backdrop (bg + edge). Change to a flat translucent background with **no border** (drop `edgeFile`; keep a dark translucent bg so the gold text stays readable; no new border elements).

---

## Deliverable 2 — mod-fury: spec-aware primary stat (`modules/mod-fury/src/fury.cpp`)

- Replace the class-only primary map with the spec matrix from the v2 design (§1, §2): primary = STR/AGI/INT per spec, driven by `player->GetSpec(player->GetActiveSpec())` (talent-tree id). Keep a class fallback for unknown trees (warrior→STR, paladin→STR, hunter/rogue→AGI, priest/mage/warlock/shaman/druid→INT, death knight→STR).
- Apply per-character in `ApplyFullRewards` and `ApplyRewardDelta` (they are already per-character). The spec is read fresh at login/level-up/gain, so no spec-change hook is required.
- Verify the TalentTab ids against the fork's `TalentTab.dbc` (env/dist/bin/dbc/ or the DBC store headers) — canonical WotLK ids are listed in the v2 spec §2; confirm before finalizing the map.
- No config key required in this pass (optional `Fury.SpecPrimaryTable` is future work).
- The addon's reward-list label stays class-level fallback — no addon change for this.

## Deliverable 3 — mod-random-enchants: spec-aware archetype + form-aware feral (`modules/mod-random-enchants/src/random_enchants.cpp` + new SQL)

- `getArchetype(Player*)` resolution order:
  1. New DB table `mod_re_spec_archetype` (`spec_id INT UNSIGNED PK`, `archetype VARCHAR`) — seed rows = the matrix (all 30 specs → PHYSICAL/AGILITY/CASTER/HEALER/TANK). Lookup `spec_id = player->GetSpec(player->GetActiveSpec())`.
  2. Fallback: existing `mod_re_class_archetype` (class-level).
  3. Fallback: the current hard-coded map.
- New SQL file `data/sql/db-world/004_mod_re_spec_archetype.sql` (CREATE TABLE IF NOT EXISTS + INSERT seed rows, idempotent).
- **Feral druid form-awareness (pools only):** class == DRUID and role == AGILITY → check `player->GetShapeshiftForm()`; `FORM_BEAR`/`FORM_DIREBEAR` → TANK-flavoured pool (with AGI still present); `FORM_CAT`/none → AGILITY pool. Fury primary stays AGI regardless of form.
- **Pools:** the pool arrays (`ARMOR_POOLS` / `WEAPON_POOLS` / `JEWELRY_POOLS` / `RELIC_POOLS`) are indexed by `uint32(archetype)` — verify the Archetype enum order/names (`ArchetypeFromString`) and extend the arrays to 5 roles so AGILITY and TANK resolve to distinct, correctly-weighted pools per the v2 design's per-role philosophy (§1). Keep weights reasonable; no balance pass is required but pools must exist for every role.
- `conf/random_enchants.conf.dist`: add a comment-only or gated option if useful (e.g. `RandomEnchants.SpecAware = 1` default enabled) — keep it minimal.

## Deliverable 4 — empower-not-rewrite (`random_enchants.cpp` + new tool + new SQL)

Slot facts (verified in the fork): `PROP_ENCHANTMENT_SLOT_0..4 = 7..11`; `Item::SetItemRandomProperties` writes property/suffix enchant ids into ALL of 7..11; suffix potency = DBC per-entry amounts × suffix factor (`GenerateEnchSuffixFactor(GetEntry())`, derived from item template level — never touched by rank swaps).

1. `swapToVariant`: **remove the destructive block** that zeroes `ITEM_FIELD_RANDOM_PROPERTIES_ID`, `ITEM_FIELD_PROPERTY_SEED`, and clears PROP slots 7..11. The variant swap must PRESERVE the instance's random property/suffix and all enchant slots.
2. `rollQualityAndEnchant`: when `item->GetItemRandomPropertyId() != 0` (random property or suffix present), **skip the matrix enchant roll on slots 7..9** (the suffix owns 7..11). Empowerment for these items = variant stat upgrade + suffix rank boost. Suffix-free items keep the current chained roll on 7..9.
3. **Suffix rank boost** — on a successful variant upgrade of a RandomProperty/RandomSuffix item:
   - New DB table `mod_re_suffix_boost` (`from_id INT NOT NULL`, `to_id INT NOT NULL`, PRIMARY KEY (from_id)) — DDL in `data/sql/db-world/005_mod_re_suffix_boost.sql` (idempotent; the SEED is produced by the generator below, do not hand-write ranks).
   - Module boost logic: look up `from_id = |GetItemRandomPropertyId()|` → `to_id`; re-apply with the same sign (`SetItemRandomProperties(sign * to_id)` — positive = RandomProperty, negative = RandomSuffix); `SetState(ITEM_CHANGED, player)` so it persists. If no ladder row (capped family): skip + LOG via the module's logger — never error, never invent data.
   - **Never change ilvl or RequiredLevel** — the rank swap only touches the property/suffix id.
4. **Ladder generator** — new tool `modules/mod-random-enchants/tools/generate_suffix_boost.py`:
   - Reads `ItemRandomProperties.dbc` + `ItemRandomSuffix.dbc` (paths configurable via `--input-dbc` args; defaults to `env/dist/bin/dbc/` — check whether those files exist there; if not, take the paths from the repo's `client-resources/` DBC copies if present, and document the required input in the script header).
   - Groups entries into families (same stat layout / same name family — e.g. "of the Eagle" ranks), orders ranks by total stat weight, and emits:
     a. `data/sql/db-world/005_mod_re_suffix_boost.sql` (INSERT rows: each rank → the next higher rank of its family),
     b. a report of capped families (no higher rank) printed to stdout AND saved to `modules/mod-random-enchants/tools/suffix_boost_capped_families.txt`.
   - The engineer runs this script against the client DBCs and applies the SQL — **the factory must NOT run it against the live DB** (running the script itself to produce the SQL file is fine and expected; running it against a live database is forbidden).
5. Extended suffix DBC tiers (where families cap) are OUT OF SCOPE — the capped-family report is the handoff to a follow-up DBC-patch task.

## Deliverable 5 — variant vendor prices (`tools/generate_variants.py` + regenerated SQL)

- `generate_variants.py` currently copies every base field verbatim → variants inherit base BuyPrice/SellPrice. Add a per-tier price multiplier applied to the variant row's `BuyPrice` and `SellPrice` (constants at the top of the script, tunable): TIER_1 ×1.5, TIER_2 ×2.5, TIER_3 ×4, TIER_4 ×6, TIER_5 ×8.
- REGENERATE the variant SQL by running the script (deterministic, file output only): refresh `data/sql/db-world/003_mod_re_variants.sql`. Do NOT apply it anywhere.
- Note in your build report: the engineer must re-apply 003 (and players must clear `Cache\WDB` with the game closed, per the standing WDB gotcha).

---

## Build-time verification items (report findings in your build report)

1. TalentTab ids vs `TalentTab.dbc` (canonical WotLK ids listed in the v2 spec §2).
2. The Archetype enum order/names and pool-array indexing in `random_enchants.cpp` (5-role extension).
3. `Player::GetSpec` / `GetActiveSpec` / `GetShapeshiftForm` signatures in this fork.
4. `GenerateEnchSuffixFactor` semantics + the suffix re-apply path for the boost.
5. Whether `ItemRandomProperties.dbc`/`ItemRandomSuffix.dbc` exist at `env/dist/bin/dbc/` or `client-resources/` (for the generator).
6. All line numbers in the referenced docs vs the live tree.

If you cannot verify an item by reading the code/data, implement per the v2 spec's stated assumption and FLAG it clearly — do not silently guess.

## Gotchas that bit us (respect them)

- **Modules are gitignored clones** — never commit/push/pull (standing rule; `--no-commit` is active).
- **MySQL 8 reserved words:** backtick identifiers in ad-hoc SQL.
- **WDB cache:** item-template changes require players to delete `Cache\WDB` with the game closed.
- **SP% is impossible in this fork** (no `SPELL_AURA_MOD_SPELL_POWER_PCT`) — AP/SP stay flat.
- **The factory test phase is a placeholder** — "done" is coherent code + reviewer approval, never a compile.
- **Line numbers in docs are pre-verified but may drift** — re-verify in the live tree.
- **The live worldserver + DBs are read-only for you** — query for verification only, modify nothing.

## Done means

- `client-resources/NexusFrames/NexusFrames.lua`: minimap button added (drag + persisted position + toggles window), both `%%` spots fixed, popup borderless; transport and existing features untouched.
- `modules/mod-fury/src/fury.cpp`: spec-aware primary per the matrix, class fallback intact.
- `modules/mod-random-enchants/src/random_enchants.cpp`: spec-aware `getArchetype` (spec table → class table → hard-coded), 5-role pools, feral form-awareness, `swapToVariant` no longer destroys suffixes/enchants, matrix skipped on random-suffix items, suffix rank boost with `mod_re_suffix_boost` lookup + capped-family logging.
- New SQL: `004_mod_re_spec_archetype.sql` (seeded), `005_mod_re_suffix_boost.sql` (DDL; seed via generator).
- New tool: `generate_suffix_boost.py` (reads DBCs, emits ladder SQL + capped-family report).
- `generate_variants.py`: tier price multipliers; `003_mod_re_variants.sql` regenerated with scaled prices.
- Coherent C++17 / Python3 / Lua 5.1 (WoW 3.3.5 environment); no core changes; no git operations; nothing compiled, built, packed, or applied to any DB.
- The reviewer confirms the build matches the plan and the v2 design.

## Out of scope

Extended suffix DBC tiers (follow-up), client-side spec display in the reward list, balance tuning, ANY change to core `src/server/game/`, the client DBC patch generators (`client-resources/generate_*.py` — do not touch), MPQ packing, applying SQL to live databases, running/compiling the server, and ANY git operation.
