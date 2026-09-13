# Fury/NexusFrames v2 — Spec-Aware Roles, Empower-Not-Rewrite, Variant Prices, Addon Polish

> **STATUS: implemented — built and shipped.** This spec is retained as the design record. For
> current state see `documentation/modules.md` and `documentation/wow-handoff.md` §3.

Status: **implemented** (engineer + agent agreed; see the decision log).
Scope: mod-fury, mod-random-enchants, NexusFrames addon, variant price generator.
Authoritative existing docs: `specs/fury-nexusframes-design.md`, `specs/db8e1683_item-quality-random-enchants.md`,
`documentation/fury-nexusframes-handoff.md`.

---

## 0. Decision log (approved)

| # | Decision | Choice |
|---|---|---|
| D1 | Button | **Minimap button** (self-contained LibDBIcon-style) — micro-bar button stays as harmless bonus |
| D2 | Spec-aware scope | **Both systems** (enchants + Fury primary), from ONE matrix |
| D3 | Empower strategy | **Preserve + free slots**: keep random suffixes & existing enchants; matrix rolls only free slots; **boost the original suffix** when the quality upgrade triggers; create extra suffix tiers only where families cap |
| D4 | Variant prices | **Generator tier scaling** of SellPrice (and BuyPrice) in `generate_variants.py`, then regenerate + reapply the variant SQL |

User edge-case notes (locked):
- Feral druid: both cat and bear benefit from **AGI** as primary stat. (Guardian is NOT a 3.3.5a spec — Balance/Feral/Restoration are the three trees; cat/bear is form, and `GetShapeshiftForm()` can distinguish it for *enchant pools*.)
- Death Knight: all three specs benefit from **Strength** (Blood = TANK role for pools, Frost/Unholy = PHYSICAL; primary STR for all).
- Enhancement shaman: AGI primary.
- Shadow priest: CASTER role, INT primary; a light Spirit/MP5 weighting in the caster pool is acceptable ("if easier") but never primary.
- Holy paladin: INT primary.
- Suffix boost must NEVER touch item ilvl / RequiredLevel — a level-47 item stays equippable by the level-47 character after boost.

---

## 1. Spec → Role → Primary matrix (FINAL)

Roles: `PHYSICAL` (STR/AP melee) · `AGILITY` (AGI users) · `CASTER` (INT DPS) · `HEALER` (INT/SPI/MP5) · `TANK` (STA/mitigation).

| Class | Spec | Role (enchants) | Fury primary |
|---|---|---|---|
| Warrior | Arms / Fury | PHYSICAL | STR |
| Warrior | Protection | TANK | STR |
| Paladin | Holy | HEALER | INT |
| Paladin | Protection | TANK | STR |
| Paladin | Retribution | PHYSICAL | STR |
| Hunter | BM / MM / Surv | AGILITY | AGI |
| Rogue | Assass / Combat / Subtlety | AGILITY | AGI |
| Priest | Discipline / Holy | HEALER | INT |
| Priest | Shadow | CASTER | INT |
| Death Knight | Blood | TANK | STR |
| Death Knight | Frost / Unholy | PHYSICAL | STR |
| Shaman | Elemental | CASTER | INT |
| Shaman | Enhancement | AGILITY | AGI |
| Shaman | Restoration | HEALER | INT |
| Mage | Arcane / Fire / Frost | CASTER | INT |
| Warlock | Affl / Demo / Destr | CASTER | INT |
| Druid | Balance | CASTER | INT |
| Druid | Feral (cat) | AGILITY | AGI |
| Druid | Feral (bear) | TANK-flavoured pool, AGI still present | AGI |
| Druid | Restoration | HEALER | INT |

Per-role enchant-pool philosophy:
- PHYSICAL: STR · AP · HIT · EXPERTISE · CRIT · HASTE
- AGILITY: AGI · AP · CRIT · HASTE · HIT · EXPERTISE
- CASTER: INT · SP · HIT · HASTE · CRIT (light SPI/MP5 optional)
- HEALER: INT · SP · SPIRIT · MP5 · HASTE (crit only lightly)
- TANK: STA · STR · DEFENSE · DODGE · PARRY · HIT · EXPERTISE (block for paladin/warrior)

---

## 2. mod-fury — spec-aware primary stat

- `PrimaryStatForClass(Player*)` becomes `PrimaryStatForSpec(Player*)`: primary = STR/AGI/INT from the matrix, driven by `player->GetSpec(player->GetActiveSpec())` (talent-tree id).
- Applied per-character in `ApplyFullRewards` / `ApplyRewardDelta` (already per-character) at login, level-up, and every gain — the spec is read fresh each time, so no spec-change hook is required for correctness (a mid-session respec self-corrects on the next login/level-up/gain).
- Class fallback when the tree id is unknown: warrior→STR, paladin→STR, hunter/rogue→AGI, priest/mage/warlock/shaman/druid→INT, death knight→STR (the old per-class map).
- Optional config override key: `Fury.SpecPrimaryTable` (future) — not required in this pass.
- Addon display: the reward-list label stays CLASS-LEVEL fallback (it cannot cheaply read the server-side spec). The APPLIED stat is spec-correct server-side. No addon change needed for this.

WotLK TalentTab ids (VERIFY against `TalentTab.dbc` at build — canonical values):
Warrior 161/163/164 · Paladin 381/382/383 · Hunter 361/363/362 · Rogue 182/181/183 ·
Priest 201/202/203 · DK 398/399/400 · Shaman 261/263/262 · Mage 81/41/61 · Warlock 302/303/301 · Druid 283/281/282.

---

## 3. mod-random-enchants — spec-aware archetype + form-aware feral

- `getArchetype(Player*)` becomes spec-aware. Resolution order:
  1. New DB table `mod_re_spec_archetype` (`spec_id INT UNSIGNED PK`, `archetype VARCHAR`) — seed rows = matrix. Lookup: `spec_id = player->GetSpec(player->GetActiveSpec())`. **Gated by `RandomEnchants.SpecAware = 1` (kill-switch, default enabled): `0` skips this step → class-level behaviour.**
  2. Fallback: existing `mod_re_class_archetype` (class-level).
  3. Fallback: hard-coded map (current).
- Archetype string values must match the existing `ArchetypeFromString` vocabulary (PHYSICAL/AGILITY/CASTER/HEALER/TANK — verify the enum names in `random_enchants.cpp`; the pools already distinguish AGILITY-style pools for hunter/rogue).
- **Feral druid form-awareness (enchant pools only):** when class == DRUID and the resolved role is AGILITY, check `player->GetShapeshiftForm()`: `FORM_BEAR`/`FORM_DIREBEAR` → TANK-flavoured pool (ensure AGI remains a present stat in the feral-bear pool); `FORM_CAT` or none → AGILITY pool. Fury primary stays AGI regardless.
- The pools themselves (`ARMOR_POOLS` / `WEAPON_POOLS` / `JEWELRY_POOLS` / `RELIC_POOLS`) need a fifth archetype entry where the pool arrays are indexed by archetype — verify how `poolIndex = uint32(archetype)` indexes the arrays and extend them to 5 roles (or map AGILITY onto an existing AGI pool if the arrays are 4-wide — but the cleaner fix is a 5th slot; keep weights consistent with the per-role philosophy above).
- New SQL file: `data/sql/db-world/004_mod_re_spec_archetype.sql` (DDL + seed rows per the matrix).

---

## 4. Empower-not-rewrite (enchant roll on RandomProperty/RandomSuffix items)

### 4.1 Enchant-slot facts (verified in this fork)
- `enum EnchantmentSlot`: PERM=0, TEMP=1, SOCK=2..4, BONUS=5, PRISMATIC=6, **PROP_ENCHANTMENT_SLOT_0..4 = 7..11** (Item.h:178-181 — "used with RandomSuffix and RandomProperty").
- `Item::SetItemRandomProperties` (Item.cpp:668) writes a RandomProperty's enchant ids into **all of slots 7..11** (`for i = PROP_ENCHANTMENT_SLOT_0; i < MAX_ENCHANTMENT_SLOT; ++i`); RandomSuffix (negative id) uses the same range with the suffix factor.
- Suffix potency = per-entry fixed amounts (`ItemRandomProperties.dbc` / `ItemRandomSuffix.dbc`) × suffix factor (`GenerateEnchSuffixFactor(GetEntry())`, Item.cpp:708 — derived from the **item template level**, never touched by rank swaps).
- Current module behaviour (the bug): `swapToVariant` (random_enchants.cpp) actively zeroes `ITEM_FIELD_RANDOM_PROPERTIES_ID`, `ITEM_FIELD_PROPERTY_SEED`, and clears **all** PROP slots 7..11 — destroying the item's random suffix ("of the Eagle") on upgrade.

### 4.2 Target behaviour
1. `swapToVariant`: **remove the destructive clear block.** Preserve the instance's random property/suffix + all enchant slots across the entry swap.
2. `rollQualityAndEnchant`: if the item has a random property/suffix (`item->GetItemRandomPropertyId() != 0`), **skip the matrix enchant roll on slots 7..9** (the suffix owns 7..11). The empowerment for these items = variant stat upgrade + suffix rank boost.
3. Suffix-free items: matrix enchants roll slots 7..9 exactly as today (chained 70/65/60 %).
4. **Suffix rank boost** — triggered by a successful quality upgrade (variant swap) on a RandomProperty/RandomSuffix item:
   - New DB table `mod_re_suffix_boost` (`from_id INT`, `to_id INT`, PK(from_id)) — an explicit ladder.
   - The module, at boost time: look up `from_id = |GetItemRandomPropertyId()|` → `to_id`; re-apply via `SetItemRandomProperties(sign * to_id)` (same sign as the original — positive = RandomProperty, negative = RandomSuffix); preserve the item state change so it persists.
   - If no ladder row (capped family): skip the boost and LOG (module log) the capped family — do not error, do not invent data.
   - **Never change ilvl or RequiredLevel.** Rank swap only touches the property/suffix id.
5. **Ladder generation:** new tool `modules/mod-random-enchants/tools/generate_suffix_boost.py` — reads `ItemRandomProperties.dbc` + `ItemRandomSuffix.dbc` (paths configurable; default `env/dist/bin/dbc/`), groups entries into families (same stat layout/name family — use the DBC name + enchant signature), emits:
   - `data/sql/db-world/005_mod_re_suffix_boost.sql` (INSERT rows: each rank → next higher rank of the same family, by total stat weight),
   - a report of families that cap (no higher rank) — printed to stdout and saved as `tools/suffix_boost_capped_families.txt`.
   The engineer runs the script against the client DBCs and applies the SQL (the factory must NOT run it against the live DB).
6. **Reviewer note 1 — RESOLVED (generator fix, data-only):** the suffix-factor-on-relog caveat is fixed at the root in `generate_variants.py`: variant rows for suffix-bearing bases (`RandomSuffix != 0`) now PRESERVE the base's `RandomSuffix` instead of zeroing it. `GenerateEnchSuffixFactor` gates on `RandomSuffix != 0` and derives the factor from ItemLevel + InventoryType (both copied from the base), so the variant computes the SAME factor as the base on every `LoadFromDB` (login / mail / trade / guild bank) — correct applied stats, tooltip, and combat, seamlessly, with no runtime code and no core change. A login-time module fix was rejected as NOT seamless: no `ItemScript::OnLoad` hook exists in this fork, the seed is never persisted (`SaveToDB` writes only enchant ids + the random-property id), and every load path recomputes the factor — so a login hook cannot cover mail/trade-loaded items.
6. **Extended suffix tiers** (only where families cap): OUT OF SCOPE for this pass — the capped-family report feeds a follow-up DBC-patch data task (the fork's DBC patch pipeline lives in `client-resources/`, e.g. `generate_enchant_dbc_patch.py`; a separate design is needed before patching `ItemRandomProperties.dbc`/`ItemRandomSuffix.dbc`).

---

## 5. Variant vendor prices (generator tier scaling)

- `modules/mod-random-enchants/tools/generate_variants.py` currently copies every base field verbatim (`out = list(base.fields)`) → variants inherit base BuyPrice/SellPrice. Confirmed live: 15356 Buy 19678 / Sell 3935.
- Change: apply a per-tier price multiplier to the variant row's `BuyPrice` and `SellPrice`. Suggested defaults (configurable constants at the top of the script):
  - TIER_1 (Uncommon) ×1.5, TIER_2 (Rare) ×2.5, TIER_3 (Epic) ×4, TIER_4 (Legendary) ×6, TIER_5 (Legendary) ×8.
- Regenerate the variant SQL by RUNNING the script (deterministic, file output only — never against the live DB). The factory may run the generator to refresh `data/sql/db-world/003_mod_re_variants.sql`; the ENGINEER applies it.
- ⚠️ WDB cache: any item-template change requires players to delete `Cache\WDB` with the game closed, or tooltips show stale stats (standing gotcha).

---

## 6. NexusFrames addon v2

Client-only changes to `client-resources/NexusFrames/` (NexusFrames.lua; toc unchanged unless needed).

1. **Minimap button** (primary toggle): self-contained LibDBIcon-style button —
   - 32×32 `Button` parented to `Minimap`, circular backdrop (`Interface\\Minimap\\UI-Minimap-Background` masked ring, or the classic `BackdropTemplate`-less circle: a texture with the minimap-ring texture), click toggles the window (`ToggleWindow()` — reuse the existing single toggle path), `SetClampedToScreen(true)`, drag-to-move (`SetMovable`/`RegisterForDrag("LeftButton")`/`OnDragStart`/`OnDragStop`), position saved to `NexusFramesDB.minimapPos` (same pattern as the compact bar), tooltip "NexusFrames".
   - Reference the bundled lib for the exact pattern: `client-resources/example-addons/WeakAuras-WotLK/WeakAuras/Libs/LibDBIcon-1.0/LibDBIcon-1.0.lua` (and its `.toc`/`.xml` siblings) — but implement self-contained, no lib bundling.
   - Keep the existing micro-bar button code unchanged (harmless bonus toggle).
2. **Double `%%` fix** — two places render `"+0.1%% Haste"`: the level-up popup line and the reward-list haste line. Both use `string.format("+%s%% Haste", FormatPct(...))` where `FormatPct` already appends `%`. Fix both to `"+%s Haste"`.
3. **Popup border removal** — the level-up popup currently uses a tooltip backdrop (bg + edge). Change to a flat translucent background with **no border** (drop `edgeFile`; keep a dark translucent bg so the gold text stays readable; optionally a thin gold underline instead of a full border — keep it simple: bg only).
4. Do NOT touch: the transport (CHAT_MSG_ADDON + whisper fallback + dedup + filtered seterrorhandler), the compact bar, the reward-list logic, the tier colors, the scroll, SavedVariables keys already in use.

---

## 7. Out of scope (this pass)

- Extended suffix DBC tiers (follow-up data task; capped-family report is the handoff).
- Client-side spec display in the reward list (class-level fallback only).
- Balance pass on weights/rates.
- Any core (`src/server/game/`) change — all hooks/APIs are existing module surfaces.
- Building/compiling, running the server, applying SQL to live DBs, packing MPQs (engineer does all of these manually).
- Git operations (modules are gitignored clones; --no-commit mode).

---

## 8. Verify-at-build items

1. TalentTab ids against `TalentTab.dbc` (or the fork's DBC store headers) — the tree ids above are canonical WotLK but MUST be confirmed.
2. The exact Archetype enum names/vocabulary in `random_enchants.cpp` (`ArchetypeFromString`) and the pool-array indexing (`ARMOR_POOLS[4]` etc.) — extending to a 5th role must keep `poolIndex = uint32(archetype)` consistent.
3. `Player::GetSpec(int8 spec = -1)` / `GetActiveSpec()` / `GetShapeshiftForm()` signatures in this fork.
4. `GenerateEnchSuffixFactor` + suffix re-apply path (SetItemRandomProperties) semantics for the boost.
5. All line numbers in the referenced docs vs the live tree.

---

## Appendix A — Learned lessons (share with any new agent)

### Addon / 3.3.5 client
1. **Receive path is `CHAT_MSG_ADDON`** (args: prefix, text, channel, sender). `RegisterAddonMessagePrefix` is 4.1+/Cataclysm — the original design's claim that the event doesn't exist in 3.3.5 was WRONG (proven by the bundled AceComm-3.0). The server's messages are `"AzerothCore\t" + opcode + 4-char counter + payload`; the client splits the prefix off.
2. **Off-by-one:** `"levelup:"` is 8 chars — match with `string.sub(payload, 1, 8)`; `"furygain:"`/`"fury:"` are 9/5. The level-up branch used sub(1,9) vs an 8-char string and was dead code (popup never fired) until fixed.
3. Micro buttons: stock textures `UI-MicroButton-<Name>-Up/-Down/-Disabled` + the SHARED `UI-MicroButton-Hilight` (**one 'l'**). Achievement uses name `"Achievement"` (no 's'). Buttons are 28×58, chained `BOTTOMLEFT → prev BOTTOMRIGHT, -3`, parent `MainMenuBarArtFrame`, `SetHitRectInsets(0,0,18,0)`.
4. Combat log in 3.3.5 is the chat frame global `COMBATLOG` (a.k.a. `CombatLogFrame`) — `CombatLog_Print_Combat_Message` does NOT exist (Cata-era); write via `COMBATLOG:AddMessage(msg, r, g, b)`.
5. `seterrorhandler` is session-global — it catches EVERY addon's errors (e.g. a broken BonusScanner). Filter by addon name in the message, drop the rest.
6. ScrollFrame: `EnableMouseWheel(true)` + `OnMouseWheel` + `SetHorizontalScroll` (AceGUI pattern).
7. Draggable frames: `SetMovable(true)` + `EnableMouse(true)` + `RegisterForDrag("LeftButton")` + `OnDragStart`/`OnDragStop` (`StartMoving`/`StopMovingOrSizing`) + `SetClampedToScreen(true)`; persist `GetPoint()` in SavedVariables; GUARD the restore (nil fields).
8. Long FontStrings: `SetWordWrap(true)`; anchor to the parent's width, not a sibling's text width (the disclaimer was clipped).
9. Button text color: `GetFontString():SetTextColor(...)` is the safe form; direct `Button:SetTextColor` is a FontInstance mixin with version variance.
10. A StatusBar child covering a draggable Button must `EnableMouse(false)` or it swallows clicks/drags.
11. Progress bar semantics: `currentFury` is the accumulator toward the next level → `SetMinMaxValues(0, threshold(level+1))` (min=threshold(level) renders empty bars at level ≥ 1).
12. `UIPanelWindowTemplate` provides `$parentTitle` + `$parentCloseButton` for a native window.
13. Give the bar label an initial value + call the update at load (blank until the first reply).
14. Center the reward list on open/level-up, NOT on every gain (view yank).
15. Compute totalFury locally (deterministic curve) instead of trusting server pushes to keep it fresh.

### Server / workflow
16. Modules are gitignored clones — never commit/push/pull; runs use `--no-commit`.
17. MySQL 8 reserved words — backtick identifiers in ad-hoc SQL.
18. WDB cache: after any item-template change, players must delete `Cache\WDB` with the game closed.
19. No SP% in this fork (no `SPELL_AURA_MOD_SPELL_POWER_PCT`) — flat AP/SP.
20. The factory's deterministic "test" phase (`adws/adw_modules/quality.py`) is a PLACEHOLDER echo that always passes — "done" = coherent code + reviewer approval, never a compile.
21. NEVER build/compile/run the server, apply SQL to live DBs, or pack MPQs — the engineer does all of that manually; the running worldserver and live DB are read-only for agents.
22. Enchant slot layout: PERM=0, TEMP=1, SOCK=2-4, BONUS=5, PRISMATIC=6, PROP 0-4 = 7-11 (suffix-owned).
23. `SetItemRandomProperties` writes property enchants into slots 7..11; suffix factor derives from the item template level (`GenerateEnchSuffixFactor`).
24. Spec detection: `Player::GetSpec(GetActiveSpec())` → tree id; `GetShapeshiftForm()` for forms. Tree ids must be verified against `TalentTab.dbc`.
25. Line numbers in the specs/handoff are pre-verified but MUST be re-verified against the live tree.
26. The module reads `mod_re_class_archetype` (DB) with a hard-coded fallback; paladin → HEALER is the current class-only behaviour causing INT/SPI/MP5 on retribution paladins.
27. `swapToVariant` currently DESTROYS random suffixes + clears PROP slots 7..11 (the "replace not empower" bug).
28. Variant generator copies all fields verbatim (prices inherit base); quality tiers T1..T5 → visible quality 2,3,4,5,5.
29. Enchant chances chain 70/65/60 % on PROP slots 7..9.
