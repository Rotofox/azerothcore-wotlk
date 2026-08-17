# Fury System (account-wide progression) + NexusFrames addon — implement the locked design

Implement the Fury system and its NexusFrames addon **exactly as specified** in `specs/fury-nexusframes-design.md` — that document is the authoritative, complete design (status: **ready to build**, every decision confirmed by the engineer). Translate it into a build plan and code; do **NOT** re-design, re-litigate, or invent alternatives. Also read `documentation/fury-nexusframes-handoff.md` for the verified-facts summary and the gotchas that bit us; then **re-verify every line number in the code before relying on it** (the repo may have moved since the design was written).

Required reading before planning (in order): the design spec, the handoff, `documentation/` onboarding docs, `client-resources/README.md` (the client-patch pipeline), and `modules/mod-random-enchants/` (the module shape reference — the Fury module must mirror its layout). Config style reference: `env/dist/etc/modules/random_enchants.conf` + `modules/mod-random-enchants/conf/random_enchants.conf.dist`.

**THIS RUN MUST NOT COMMIT, PUSH, PULL, OR OTHERWISE MUTATE GIT IN ANY WAY** — no git add, git commit, git push, git pull, git checkout, git reset, git clean, or any other git command that changes repository state. The run is in `--no-commit` mode: every work product stays in the working tree, uncommitted, when the run ends.

**DO NOT BUILD THE PROJECT.** The engineer compiles and runs the server manually, and packs the MPQ manually. Concretely forbidden: no cmake/make/ninja, no C++ compile or syntax-check via any toolchain invocation, no starting worldserver/authserver, no applying SQL to any live database, no MPQ packing or DBC regeneration, no client-side verification. Note: the deterministic test phase in this repo is a **placeholder** (`adws/adw_modules/quality.py` ships echo commands that exit 0) — so treat "done" as *coherent code + the reviewer's approval*, not a successful compile. If you want a sanity check on your C++, do it by reading the code against the core APIs it uses, never by compiling.

---

## Deliverable 1 — Server module (new: `modules/mod-fury/`)

Model the layout on `modules/mod-random-enchants/`: `src/` (module implementation + loader file like `RE_loader.cpp`), `conf/fury.conf.dist`, `data/sql/db-auth/` (the new table lives in **acore_auth**), `data/sql/db-world/` (only if world data is actually needed — the design needs none), plus the standard module README/installer bits. No commits ever (see above).

**Earning — hook `PlayerScript::OnPlayerKilledByCreature(Player*, Creature*)`** (`src/server/game/Scripting/ScriptDefines/PlayerScript.h:255`), fires per creature kill.
- **Gate = XP-eligible, NOT XP-awarded:** the victim must be non-grey relative to the killer (within the XP range), *not* whether XP was actually awarded — at max level no XP is ever awarded, so a strict gate starves max-level players. Find the fork's grey-level/XP-eligibility formula (see how `RewardPlayerAndGroupAtKill`/`GiveXP` — `Player.cpp:12764/2385` — decide XP eligibility) and use that exact mechanism.
- **Formula:** `fury = (victimLevel × 5 + 10) × bossMultiplier` per eligible kill, awarded **per party member** — in a group/raid/dungeon every member (including the killer) gains as if they killed alone. Iterate the group's player list the same way `RewardPlayerAndGroupAtKill` does.
- **Boss multiplier:** dungeon/raid bosses award ×5 (config). Detect via `CREATURE_FLAG_EXTRA_DUNGEON_BOSS` (`CreatureData.h:73`, 0x10000000, set dynamically by the core) and/or creature rank. Use the creature's actual `minlevel/maxlevel` (skull bosses have real levels — verified in the live DB: Lich King = 83).

**Level curve:** `threshold(n) = 100 × n` → 0→1 = 100, 1→2 = 200, …, 299→300 = 30,000; total to reach level 300 = **4,515,000**. CurveBase = 100, CurveIncrement = 100 (the +100 per level is flat; only the percentage tapers).

**Storage — new table in acore_auth** (`data/sql/db-auth/`, e.g. `001_mod_fury_account_fury.sql`):

```sql
CREATE TABLE IF NOT EXISTS `account_fury` (
  `account_id` INT UNSIGNED NOT NULL,
  `fury` BIGINT UNSIGNED NOT NULL DEFAULT 0,
  `level` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`account_id`)
) ENGINE=InnoDB;
```

Lazily inserted on first kill (`INSERT … ON DUPLICATE KEY UPDATE`). Account id via `WorldSession::GetAccountId()` (`WorldSession.h:268`); the module reads/writes **LoginDatabase** (acore_auth). Keep an **in-memory per-account cache** keyed by account id, shared across the account's online characters.

**Persistence cadence (mirrors XP/rep/honor):**
- Per kill: in-memory only — **never a DB write per kill**.
- On level-up: **immediate DB write in the level-up code path** (a crash must never eat a level).
- Periodic + logout: hook `PlayerScript::OnPlayerSave(Player*)` (`PlayerScript.h:350`; fires on the core save cadence — `PlayerSaveInterval` = 900000 ms = 15 min — plus logout). Any online character of the account persists the shared accumulator (last-writer-wins, correct).

**Rewards — computed from level, never accumulated.** All bonuses derive from the account level at login; level-ups apply the **delta** (new minus old). On a level-up, apply the delta to **every online character of the account** (each with its own class primary), not just the killer. No explicit removal on logout — stat mods live on the Player object and die with it; login re-applies from the account level.

| Milestone | Reward | Application API (design-verified; re-check line numbers) |
|---|---|---|
| Every level | +0.1% Haste (×300 = +30%) | `ApplyPercentModFloatValue(UNIT_FIELD_BASEATTACKTIME+hand, pct)` per melee hand + ranged, and `ApplyPercentModFloatValue(UNIT_MOD_CAST_SPEED, pct)` — `Unit.cpp:17160/17173` (the core's own haste primitives) |
| Every 5 levels | +50 AP and +50 SP, **both FLAT** (this fork has no SP% mechanism — no `SPELL_AURA_MOD_SPELL_POWER_PCT`; per the engineer's rule, if one can't be %, both are flat) | AP: `HandleStatModifier(UNIT_MOD_ATTACK_POWER[, _RANGED], TOTAL_VALUE, …)` — `Unit.h:164–165`, percent types `BASE_PCT=1`/`TOTAL_PCT=3` at `Unit.h:128–130`; SP: `Player::ApplySpellPowerBonus(int32, bool)` — `Player.h:1945` (same API the working matrix SP enchants use) |
| Every 10 levels | +100 class-primary stat (per **character's** class: warrior→Str, mage→Int, …) | `ApplyStatBuffMod(STAT_*, float, bool)` — `PlayerStorage.cpp:4445+` (proven, used by the core enchant path) |
| Any level (extensible) | Item rewards — reward table supports `{level: [rewards]}` where a reward can be an item id; the addon renders a standard item link | **The level-300 item is NOT in scope** — but the table structure must be shaped for it |

- Compute-from-level formulas: `hastePct = 0.1×level`; `apSp = 50×⌊level/5⌋` (each); `primary = 100×⌊level/10⌋` (character's own class primary).
- Class→primary mapping: warrior→STR, paladin→STR, hunter→AGI, rogue→AGI, priest→INT, shaman→INT, mage→INT, warlock→INT, druid→INT, death knight→STR (verify against the fork's `Player` stat constants; note which classes use which — get it right per class).

**Level-up flow (design §2.6):** (1) `level = level+1` in the account cache; **write `account_fury` immediately**; (2) compute old/new reward totals and apply the delta to all online account characters; (3) push a level-up notification to the client over the addon channel so the UI popup + window update even if the window is closed.

**Config (`conf/fury.conf.dist`, all tunable — build first, balance later):** exactly these keys: `Fury.Enable`, `Fury.FuryPerLevelBase = 5`, `Fury.FuryPerLevelBonus = 10`, `Fury.BossMultiplier = 5`, `Fury.CurveBase = 100`, `Fury.CurveIncrement = 100`, `Fury.MaxLevel = 300`, `Fury.HastePerLevelPct = 0.1`, `Fury.APPerMilestone = 50`, `Fury.SPPerMilestone = 50`, `Fury.APSPEveryNLevels = 5`, `Fury.PrimaryPerMilestone = 100`, `Fury.PrimaryEveryNLevels = 10`.

**Addon-channel data protocol (design §2.8):**
- Client→server: the addon sends a `.fury`-family command over the AzerothCore addon channel. Server side: the module registers the command so `AddonChannelCommandHandler` routes it (`Chat.cpp:1050` — message starts `"AzerothCore\t"` + opcode + 4-char counter + command; dispatch at `ChatHandler.cpp:288`; config `AddonChannel = true` — `WorldConfig.cpp:146`). Response: `level, currentFury, nextThreshold, totalFury`; on level-up push a notification.
- Server→client: replies sent as LANG_ADDON whispers via the same channel.
- **WotLK receive pattern (critical):** the addon receives via `CHAT_MSG_WHISPER` with the addon-language flag and parses the body. `RegisterAddonMessagePrefix`/`CHAT_MSG_ADDON` are 4.1+/Cataclysm and do **not** exist in 3.3.5.
- Open build-time item: resolve the **exact framing constants** the fork's protocol expects (channel/target; how module commands route through `AddonChannelCommandHandler::_ParseCommands`) by reading the handler code — do not guess.

---

## Deliverable 2 — Addon source (new: `client-resources/NexusFrames/`)

**SOURCE ONLY.** Write `NexusFrames.toc` + `NexusFrames.lua` into `client-resources/NexusFrames/`. Do **NOT** pack any MPQ (the engineer packs into `patch-4.MPQ` at `Interface\AddOns\NexusFrames\` manually — same archive as the two DBC patches; MPQ changes need a client relaunch). Do not touch `Item.dbc` / `SpellItemEnchantment.dbc` / the generator scripts.

- **`NexusFrames.toc`:** `## Interface: 30300` for 3.3.5a (confirm the exact value against any existing addon/toc reference in this repo or the documentation; note it in your report).
- **Micro-menu button:** a `Button` anchored to the micro bar (`MicroButtonAndBagsBar`), right of the existing micro buttons, using `Interface\Buttons\UI-MicroButton-*` textures; tooltip "NexusFrames"; toggles the window. **Open item: resolve the exact anchor frame name + micro-button texture ids at build** by reading the client-resources docs / known 3.3.5 frame names; flag anything you couldn't verify.
- **The window:** sized **once at init**: `width = GetScreenWidth() × 0.55`, `height = GetScreenHeight() × 0.6` (≈ half screen), clamped; `SetResizable(false)`. Responsive across 720p–4k via fraction-based sizing + children anchored to frame edges. Tab strip (custom tab buttons) — first and only tab: **Fury**.
- **Fury tab (design §3.4):**
  - Top: `StatusBar` — `SetMinMaxValues(threshold[level], threshold[level+1])` (`threshold(n) = 100n`), `SetValue(currentFury)`, label "Level N — X / Y Fury"; full/MAX handling at level 300.
  - Below the bar, a disclaimer line — **exact wording, do not paraphrase:** `* Each entry shows the total bonus at that level — not an addition on top of the previous level.`
  - Below that: a **horizontal** `ScrollFrame` with one entry per level (**1, 2, 3, … 300** — every level), **multi-line rewards** (one reward per line: haste / AP·SP / primary / item link), **centered on the current level** (scroll offset = currentEntry × entryWidth − viewport/2, clamped).
  - Reward table **generated locally** from the deterministic rules (the server only sends live state).
  - **Item links:** entries can carry a standard item link (`|cff…|Hitem:…|h[name]|h|r`) — hover shows the tooltip via `GameTooltip:SetHyperlink`, click via the game's item-link machinery (`SetItemRef` hook).
- **Level-up popup (design §3.5):** transient `UIParent`-anchored frame at **top-center** (DBM-style), high strata, showing "Fury level N — +X" bonuses, fading out; shown **regardless of whether the window is open**.
- **Transport (design §3.6):** `SendAddonMessage("AzerothCore", <framed command>, …)` on the addon channel; receive via `CHAT_MSG_WHISPER` + LANG_ADDON parsing. Query on window open; server pushes level-up updates; optional slow poll (30–60 s) while open.

---

## Build-time verification items (design §5 — resolve each by reading code, then report findings in your build report)

1. Exact addon-channel framing constants + whether module commands route through `AddonChannelCommandHandler::_ParseCommands`.
2. Micro-bar anchor frame name + micro-button texture ids.
3. `NexusFrames.toc` `## Interface` value (30300 expected for 3.3.5a).
4. `OnPlayerSave` fires on logout (it fires from the save path — confirm).
5. Ranged AP mod (`UNIT_MOD_ATTACK_POWER_RANGED`) + the fork's grey-level formula for the XP-eligible gate.
6. `ApplySpellPowerBonus` behavior for flat SP (same API as the working matrix SP enchants — confirm it applies flat).

If you cannot verify an item by reading the code, implement per the design's stated assumption and **flag it clearly** in your report — do not silently guess.

## Gotchas that bit us (from the handoff — respect them)

- **MySQL 8 reserved words:** a column named `rank` in a `mysql -e` query silently fails — qualify/backtick or rename. (Not currently relevant to the schema, but any ad-hoc SQL you write must backtick identifiers.)
- **SP% is impossible in this fork** (no `SPELL_AURA_MOD_SPELL_POWER_PCT`) — hence AP and SP are **both flat**.
- **Modules are gitignored clones** — never commit/push/pull (standing rule; `--no-commit` is active).
- **Client WDB cache:** not Fury-relevant (no item-template changes) unless item rewards land later.

## Done means

- `modules/mod-fury/` exists with `src/` (module implementation + loader file), `conf/fury.conf.dist` (all §2.7 keys), `data/sql/db-auth/` (acore_auth `account_fury` DDL), and mirrors the `mod-random-enchants` shape (README etc.). No world SQL unless genuinely needed.
- `client-resources/NexusFrames/` exists with `NexusFrames.toc` + `NexusFrames.lua` implementing design §3 fully, including the **exact disclaimer line**.
- Code is coherent C++17 (AzerothCore module conventions) and valid Lua for the WoW 3.3.5 client environment; no changes to `src/server/game/`; no git operations; nothing compiled, built, packed, or applied to any DB.
- The reviewer confirms the build matches the plan and the design spec.

## Out of scope

Balance tuning (build first, balance later); the level-300 item reward (structure only); honor-based Fury; **any change to core `src/server/game/`**; the client DBC patches (`Item.dbc`, `SpellItemEnchantment.dbc`) and their generator scripts — do not regenerate or touch them; MPQ packing; applying SQL to live databases; running or compiling the server; and **ANY git operation**.
